"""Gestion SQLite : lots, analyses, alertes."""
from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Generator

from loguru import logger

import config


# ── Connexion ─────────────────────────────────────────────────────────────────

@contextmanager
def _conn() -> Generator[sqlite3.Connection, None, None]:
    db_path = Path(config.DATABASE_PATH)
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# ── Initialisation ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Crée les tables si elles n'existent pas."""
    with _conn() as con:
        con.executescript("""
        CREATE TABLE IF NOT EXISTS lots (
            id            INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_id        TEXT    NOT NULL,          -- ID interne Troostwijk
            url           TEXT    NOT NULL UNIQUE,
            nom           TEXT    NOT NULL,
            marque        TEXT,
            modele        TEXT,
            prix_actuel   REAL,
            devise        TEXT    DEFAULT 'EUR',
            date_cloture  TEXT,
            localisation  TEXT,
            favoris       INTEGER DEFAULT 0,
            description   TEXT,
            categorie     TEXT,
            scrape_at     TEXT    NOT NULL,
            updated_at    TEXT    NOT NULL
        );

        CREATE TABLE IF NOT EXISTS analyses (
            id                  INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_url             TEXT    NOT NULL REFERENCES lots(url),
            prix_revente_moyen  REAL,
            achat_cible         REAL,
            achat_max           REAL,
            marge_pct           REAL,
            liquidite           TEXT,
            risque              TEXT,
            decision            TEXT,
            decotes_appliquees  TEXT,   -- JSON array serialisé
            notes               TEXT,
            analysed_at         TEXT    NOT NULL,
            model_used          TEXT
        );

        CREATE TABLE IF NOT EXISTS alertes (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            lot_url     TEXT NOT NULL,
            canal       TEXT NOT NULL,   -- 'email' | 'discord'
            sent_at     TEXT NOT NULL,
            status      TEXT NOT NULL    -- 'ok' | 'error'
        );

        CREATE INDEX IF NOT EXISTS idx_lots_url      ON lots(url);
        CREATE INDEX IF NOT EXISTS idx_lots_cloture  ON lots(date_cloture);
        CREATE INDEX IF NOT EXISTS idx_analyses_url  ON analyses(lot_url);
        CREATE INDEX IF NOT EXISTS idx_alertes_url   ON alertes(lot_url);
        """)
    logger.debug("Base de données initialisée : {}", config.DATABASE_PATH)


# ── Lots ──────────────────────────────────────────────────────────────────────

def upsert_lot(lot: dict[str, Any]) -> bool:
    """
    Insère ou met à jour un lot.
    Retourne True si c'est une nouvelle insertion, False si mise à jour.
    """
    now = datetime.utcnow().isoformat()
    lot["updated_at"] = now
    lot.setdefault("scrape_at", now)

    with _conn() as con:
        existing = con.execute(
            "SELECT id FROM lots WHERE url = ?", (lot["url"],)
        ).fetchone()

        if existing:
            con.execute(
                """
                UPDATE lots SET
                    prix_actuel  = :prix_actuel,
                    favoris      = :favoris,
                    updated_at   = :updated_at
                WHERE url = :url
                """,
                lot,
            )
            return False
        else:
            con.execute(
                """
                INSERT INTO lots
                    (lot_id, url, nom, marque, modele, prix_actuel, devise,
                     date_cloture, localisation, favoris, description,
                     categorie, scrape_at, updated_at)
                VALUES
                    (:lot_id, :url, :nom, :marque, :modele, :prix_actuel, :devise,
                     :date_cloture, :localisation, :favoris, :description,
                     :categorie, :scrape_at, :updated_at)
                """,
                lot,
            )
            return True


def is_lot_analysed(url: str) -> bool:
    """Vérifie si un lot a déjà été analysé."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM analyses WHERE lot_url = ?", (url,)
        ).fetchone()
    return row is not None


def get_lot(url: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute("SELECT * FROM lots WHERE url = ?", (url,)).fetchone()
    return dict(row) if row else None


def get_unanalysed_lots(limit: int = 50) -> list[dict[str, Any]]:
    """Retourne les lots non encore analysés."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT l.* FROM lots l
            LEFT JOIN analyses a ON l.url = a.lot_url
            WHERE a.id IS NULL
            ORDER BY l.scrape_at DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Analyses ──────────────────────────────────────────────────────────────────

def save_analysis(lot_url: str, result: dict[str, Any]) -> None:
    """Sauvegarde le résultat d'une analyse Claude."""
    import json

    decotes = result.get("decotes_appliquees", [])
    if isinstance(decotes, list):
        decotes = json.dumps(decotes, ensure_ascii=False)

    with _conn() as con:
        con.execute(
            """
            INSERT INTO analyses
                (lot_url, prix_revente_moyen, achat_cible, achat_max,
                 marge_pct, liquidite, risque, decision,
                 decotes_appliquees, notes, analysed_at, model_used)
            VALUES
                (:lot_url, :prix_revente_moyen, :achat_cible, :achat_max,
                 :marge_pct, :liquidite, :risque, :decision,
                 :decotes_appliquees, :notes, :analysed_at, :model_used)
            """,
            {
                "lot_url": lot_url,
                "prix_revente_moyen": result.get("prix_revente_moyen"),
                "achat_cible": result.get("achat_cible"),
                "achat_max": result.get("achat_max"),
                "marge_pct": result.get("marge_pct"),
                "liquidite": result.get("liquidite"),
                "risque": result.get("risque"),
                "decision": result.get("decision"),
                "decotes_appliquees": decotes,
                "notes": result.get("notes"),
                "analysed_at": datetime.utcnow().isoformat(),
                "model_used": config.ANTHROPIC_MODEL,
            },
        )


def get_analysis(lot_url: str) -> dict[str, Any] | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM analyses WHERE lot_url = ? ORDER BY id DESC LIMIT 1",
            (lot_url,),
        ).fetchone()
    return dict(row) if row else None


# ── Alertes ───────────────────────────────────────────────────────────────────

def was_alerted(lot_url: str, canal: str) -> bool:
    """Vérifie si une alerte a déjà été envoyée pour ce lot sur ce canal."""
    with _conn() as con:
        row = con.execute(
            "SELECT id FROM alertes WHERE lot_url = ? AND canal = ? AND status = 'ok'",
            (lot_url, canal),
        ).fetchone()
    return row is not None


def save_alert(lot_url: str, canal: str, status: str) -> None:
    with _conn() as con:
        con.execute(
            """
            INSERT INTO alertes (lot_url, canal, sent_at, status)
            VALUES (?, ?, ?, ?)
            """,
            (lot_url, canal, datetime.utcnow().isoformat(), status),
        )


# ── Stats ─────────────────────────────────────────────────────────────────────

def get_stats() -> dict[str, int]:
    with _conn() as con:
        total_lots = con.execute("SELECT COUNT(*) FROM lots").fetchone()[0]
        total_analyses = con.execute("SELECT COUNT(*) FROM analyses").fetchone()[0]
        acheter = con.execute(
            "SELECT COUNT(*) FROM analyses WHERE decision = 'ACHETER'"
        ).fetchone()[0]
        surveiller = con.execute(
            "SELECT COUNT(*) FROM analyses WHERE decision = 'SURVEILLER'"
        ).fetchone()[0]
        alertes_ok = con.execute(
            "SELECT COUNT(*) FROM alertes WHERE status = 'ok'"
        ).fetchone()[0]
    return {
        "lots": total_lots,
        "analyses": total_analyses,
        "acheter": acheter,
        "surveiller": surveiller,
        "alertes_envoyees": alertes_ok,
    }
