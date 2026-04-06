#!/usr/bin/env python3
"""
FlipAgent — Veille d'enchères Troostwijk/Vavato
Point d'entrée principal + scheduler.

Usage:
    python main.py            # Mode normal (tourne en continu)
    python main.py --dry-run  # Mode test sans alertes
    python main.py --once     # Exécution unique puis arrêt
    python main.py --stats    # Affiche les statistiques et quitte
"""
from __future__ import annotations

import argparse
import sys

import schedule
import time

from loguru import logger

import config
import database
from analyzer import analyse_lot
from filter import filter_lots
from notifier import notify
from scraper import scrape_with_retry


# ── Configuration des logs ────────────────────────────────────────────────────

logger.remove()  # Supprimer le handler par défaut
logger.add(
    sys.stderr,
    level="INFO",
    format=(
        "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> — <level>{message}</level>"
    ),
    colorize=True,
)
logger.add(
    "flip_agent.log",
    level="DEBUG",
    rotation="10 MB",
    retention="30 days",
    compression="gz",
    encoding="utf-8",
)


# ── Cycle principal ────────────────────────────────────────────────────────────

def run_cycle(dry_run: bool = False) -> None:
    """Exécute un cycle complet : scraping → filtrage → analyse → alertes."""
    logger.info("═" * 60)
    logger.info("Début du cycle FlipAgent")
    logger.info("═" * 60)

    # 1. Scraping
    logger.info("Phase 1/4 : Scraping Troostwijk...")
    raw_lots = scrape_with_retry()
    if not raw_lots:
        logger.warning("Aucun lot récupéré lors de ce cycle")
        return

    # 2. Filtrage
    logger.info("Phase 2/4 : Filtrage ({} lots bruts)...", len(raw_lots))
    filtered_lots = filter_lots(raw_lots)
    if not filtered_lots:
        logger.info("Aucun lot dans le scope après filtrage")
        return

    # 3. Sauvegarde + détection nouveaux lots
    logger.info("Phase 3/4 : Sauvegarde en base ({} lots filtrés)...", len(filtered_lots))
    new_lots: list[dict] = []
    for lot in filtered_lots:
        is_new = database.upsert_lot(lot)
        if is_new and not database.is_lot_analysed(lot["url"]):
            new_lots.append(lot)

    logger.info(
        "{} nouveaux lots à analyser (déjà vus ignorés)",
        len(new_lots),
    )

    if not new_lots:
        logger.info("Aucun nouveau lot à analyser dans ce cycle")
        _log_stats()
        return

    # 4. Analyse + Alertes
    logger.info("Phase 4/4 : Analyse Claude + Alertes...")
    acheter_count = 0
    for i, lot in enumerate(new_lots, 1):
        nom = (lot.get("nom") or "?")[:60]
        logger.info(
            "Analyse {}/{} : {}", i, len(new_lots), nom
        )

        analysis = analyse_lot(lot)
        if analysis is None:
            logger.warning("Analyse échouée pour : {}", nom)
            continue

        # Sauvegarder l'analyse
        database.save_analysis(lot["url"], analysis)

        decision = analysis.get("decision", "PASSER")
        logger.info(
            "  → {} | marge {:.0f}% | achat_max {:.0f}€",
            decision,
            analysis.get("marge_pct", 0),
            analysis.get("achat_max", 0),
        )

        # Alerter si décision = ACHETER
        if decision == "ACHETER":
            acheter_count += 1
            notify(lot, analysis, dry_run=dry_run)

    logger.info(
        "Cycle terminé : {} analysés, {} à acheter",
        len(new_lots),
        acheter_count,
    )
    _log_stats()


def _log_stats() -> None:
    stats = database.get_stats()
    logger.info(
        "Stats DB : {} lots | {} analyses | {} ACHETER | {} alertes envoyées",
        stats["lots"],
        stats["analyses"],
        stats["acheter"],
        stats["alertes_envoyees"],
    )


# ── CLI ───────────────────────────────────────────────────────────────────────

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="FlipAgent — Veille d'enchères Troostwijk/Vavato"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mode test : ne pas envoyer d'alertes réelles",
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Exécution unique puis arrêt (sans scheduler)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        help="Afficher les statistiques de la base de données et quitter",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # Initialiser la base de données
    database.init_db()

    # ── Mode stats ────────────────────────────────────────────────────────────
    if args.stats:
        stats = database.get_stats()
        print("\n── Statistiques FlipAgent ──────────────────────────")
        for key, val in stats.items():
            print(f"  {key:<25} : {val}")
        print()
        return

    dry_run = args.dry_run or config.DRY_RUN
    if dry_run:
        logger.info("⚠ Mode DRY-RUN activé — aucune alerte ne sera envoyée")

    logger.info(
        "FlipAgent démarré | modèle={} | intervalle={}h | dry_run={}",
        config.ANTHROPIC_MODEL,
        config.CHECK_INTERVAL_HOURS,
        dry_run,
    )

    # ── Mode exécution unique ─────────────────────────────────────────────────
    if args.once:
        run_cycle(dry_run=dry_run)
        return

    # ── Mode scheduler (boucle infinie) ──────────────────────────────────────
    interval_hours = config.CHECK_INTERVAL_HOURS

    # Premier run immédiat
    run_cycle(dry_run=dry_run)

    # Planification des runs suivants
    schedule.every(interval_hours).hours.do(run_cycle, dry_run=dry_run)
    logger.info("Prochain run dans {}h", interval_hours)

    while True:
        schedule.run_pending()
        time.sleep(60)  # Vérifie toutes les minutes


if __name__ == "__main__":
    main()
