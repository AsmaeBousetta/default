"""Analyse de chaque lot via l'API Anthropic Claude."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

import anthropic
from loguru import logger

import config

# ── Chargement du prompt système ──────────────────────────────────────────────

_PROMPT_PATH = Path(__file__).parent / "prompts" / "flip_analyzer.txt"
_SYSTEM_PROMPT: str = _PROMPT_PATH.read_text(encoding="utf-8")

# Client Anthropic (singleton)
_client = anthropic.Anthropic(api_key=config.ANTHROPIC_API_KEY)

# Rate-limiting : timestamp du dernier appel
_last_call_ts: float = 0.0


def _rate_limit_wait() -> None:
    """Respecte le délai minimum entre deux appels API."""
    global _last_call_ts
    elapsed = time.monotonic() - _last_call_ts
    if elapsed < config.ANTHROPIC_RATE_LIMIT_DELAY:
        time.sleep(config.ANTHROPIC_RATE_LIMIT_DELAY - elapsed)
    _last_call_ts = time.monotonic()


def _build_user_message(lot: dict[str, Any]) -> str:
    """Construit le message utilisateur JSON à envoyer à Claude."""
    payload = {
        "nom": lot.get("nom", ""),
        "marque": lot.get("marque", ""),
        "modele": lot.get("modele", ""),
        "prix_actuel": lot.get("prix_actuel"),
        "date_cloture": lot.get("date_cloture", ""),
        "localisation": lot.get("localisation", ""),
        "url": lot.get("url", ""),
        "favoris": lot.get("favoris", 0),
        "description": (lot.get("description", "") or "")[:1500],  # tronquer si long
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def _extract_json_from_response(text: str) -> dict[str, Any]:
    """
    Extrait le JSON de la réponse Claude.
    Claude peut parfois entourer le JSON de backticks malgré les instructions.
    """
    # Supprimer éventuels blocs markdown ```json ... ```
    text = re.sub(r"```(?:json)?\s*", "", text).strip()
    text = re.sub(r"```\s*$", "", text).strip()

    # Trouver le premier { ... } complet
    start = text.find("{")
    if start == -1:
        raise ValueError("Aucun objet JSON trouvé dans la réponse")

    # Trouver la accolade fermante correspondante
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                json_str = text[start : i + 1]
                return json.loads(json_str)

    raise ValueError("JSON incomplet dans la réponse Claude")


def _validate_analysis(data: dict[str, Any]) -> dict[str, Any]:
    """Valide et normalise les champs obligatoires de l'analyse."""
    required = {
        "prix_revente_moyen": float,
        "achat_cible": float,
        "achat_max": float,
        "marge_pct": float,
        "liquidite": str,
        "risque": str,
        "decision": str,
        "notes": str,
    }

    for field, ftype in required.items():
        val = data.get(field)
        if val is None:
            logger.warning("Champ manquant dans l'analyse : {}", field)
            data[field] = ftype() if ftype != str else ""
        else:
            try:
                data[field] = ftype(val)
            except (ValueError, TypeError):
                logger.warning("Champ {} invalide : {}", field, val)
                data[field] = ftype()

    # Normaliser les valeurs catégorielles
    data["liquidite"] = data["liquidite"].upper()
    if data["liquidite"] not in ("HAUTE", "MOYENNE", "FAIBLE"):
        data["liquidite"] = "MOYENNE"

    data["risque"] = data["risque"].upper()
    if data["risque"] not in ("FAIBLE", "MOYEN", "ELEVE"):
        data["risque"] = "MOYEN"

    data["decision"] = data["decision"].upper()
    if data["decision"] not in ("ACHETER", "SURVEILLER", "PASSER"):
        data["decision"] = "PASSER"

    data.setdefault("decotes_appliquees", [])

    return data


def analyse_lot(lot: dict[str, Any], max_retries: int = 3) -> dict[str, Any] | None:
    """
    Analyse un lot via Claude API.

    Args:
        lot: dictionnaire avec les informations du lot
        max_retries: nombre de tentatives en cas d'erreur

    Returns:
        Dictionnaire de résultats ou None si échec définitif
    """
    user_message = _build_user_message(lot)
    nom_court = (lot.get("nom") or "lot inconnu")[:60]

    for attempt in range(1, max_retries + 1):
        try:
            _rate_limit_wait()

            logger.debug(
                "Analyse Claude ({}/{}) : {}",
                attempt,
                max_retries,
                nom_court,
            )

            response = _client.messages.create(
                model=config.ANTHROPIC_MODEL,
                max_tokens=1024,
                system=_SYSTEM_PROMPT,
                messages=[
                    {"role": "user", "content": user_message}
                ],
            )

            raw_text = response.content[0].text
            logger.debug("Réponse brute : {}", raw_text[:300])

            data = _extract_json_from_response(raw_text)
            data = _validate_analysis(data)

            logger.info(
                "✓ Analyse OK | {} | décision={} | marge={:.0f}% | achat_max={:.0f}€",
                nom_court,
                data["decision"],
                data.get("marge_pct", 0),
                data.get("achat_max", 0),
            )
            return data

        except anthropic.RateLimitError as exc:
            retry_after = int(getattr(exc.response, "headers", {}).get("retry-after", "60"))
            logger.warning(
                "Rate limit Anthropic (tentative {}/{}) — attente {}s",
                attempt,
                max_retries,
                retry_after,
            )
            if attempt < max_retries:
                time.sleep(retry_after)

        except anthropic.APIStatusError as exc:
            if exc.status_code >= 500:
                wait = 2 ** attempt
                logger.warning(
                    "Erreur serveur Anthropic {} (tentative {}/{}) — attente {}s",
                    exc.status_code,
                    attempt,
                    max_retries,
                    wait,
                )
                if attempt < max_retries:
                    time.sleep(wait)
            else:
                logger.error("Erreur API Anthropic {} : {}", exc.status_code, exc.message)
                return None

        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning(
                "JSON invalide dans la réponse Claude (tentative {}/{}) : {}",
                attempt,
                max_retries,
                exc,
            )
            if attempt >= max_retries:
                return None

        except Exception as exc:
            logger.error(
                "Erreur inattendue lors de l'analyse (tentative {}/{}) : {}",
                attempt,
                max_retries,
                exc,
            )
            if attempt < max_retries:
                time.sleep(2 ** attempt)
            else:
                return None

    logger.error("Analyse abandonnée après {} tentatives : {}", max_retries, nom_court)
    return None
