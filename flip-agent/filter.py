"""Filtrage des lots : marques cibles, catégories hors-scope, marques sans valeur."""
from __future__ import annotations

import re

from loguru import logger

import config

# ── Mots-clés hors-scope (catégories à ignorer) ───────────────────────────────
_EXCLUDED_KEYWORDS: list[str] = [
    # Mobilier / bureau
    "chaise", "bureau", "armoire", "table de réunion", "étagère",
    "canapé", "fauteuil", "meuble",
    # Engins de chantier
    "pelleteuse", "bulldozer", "chariot élévateur", "forklift",
    "grue", "compresseur chantier", "nacelle",
    # Piscine / loisirs
    "piscine", "spa", "jacuzzi", "robot piscine",
    "tapis roulant", "vélo elliptique", "home gym",
    # Grand public
    "smartphone", "tablette", "laptop gaming", "console de jeux",
    "television", "téléviseur", "lave-linge", "lave-vaisselle",
    "réfrigérateur", "climatiseur domestique",
    # Vêtements / divers
    "vêtement", "textile", "chaussure",
    # Cuisine
    "four à convection ménager", "micro-onde ménager",
]

# Marques sans valeur de revente connue
_EXCLUDED_BRANDS: frozenset[str] = frozenset(
    [
        "tes",
        "unbranded",
        "no brand",
        "sans marque",
        "generic",
        "inconnu",
        "unknown",
        "divers",
        "various",
    ]
)


def _normalize(text: str) -> str:
    """Minuscules + suppression accents basiques."""
    text = text.lower()
    text = re.sub(r"[àâä]", "a", text)
    text = re.sub(r"[éèêë]", "e", text)
    text = re.sub(r"[îï]", "i", text)
    text = re.sub(r"[ôö]", "o", text)
    text = re.sub(r"[ùûü]", "u", text)
    text = re.sub(r"[ç]", "c", text)
    return text


def _text_contains_any(text: str, terms: list[str]) -> str | None:
    """Retourne le premier terme trouvé dans text, ou None."""
    norm = _normalize(text)
    for term in terms:
        if _normalize(term) in norm:
            return term
    return None


def is_lot_in_scope(lot: dict) -> tuple[bool, str]:
    """
    Vérifie si un lot doit être conservé pour analyse.

    Returns:
        (True, "") si le lot est dans le scope
        (False, reason) si le lot doit être ignoré
    """
    nom = lot.get("nom", "") or ""
    marque = lot.get("marque", "") or ""
    description = lot.get("description", "") or ""
    full_text = f"{nom} {marque} {description}"

    # 1. Vérifier hors-scope par mots-clés
    excluded = _text_contains_any(full_text, _EXCLUDED_KEYWORDS)
    if excluded:
        return False, f"hors-scope : mot-clé '{excluded}'"

    # 2. Vérifier marques sans valeur
    if marque:
        norm_marque = _normalize(marque.strip())
        if norm_marque in _EXCLUDED_BRANDS:
            return False, f"marque exclue : '{marque}'"

    # 3. Vérifier si marque cible présente (dans nom, marque ou description)
    norm_full = _normalize(full_text)
    for brand in config.TARGET_BRANDS:
        if brand in norm_full:
            return True, ""

    # 4. Aucune marque cible trouvée → ignorer
    return False, "aucune marque cible détectée"


def extract_brand(text: str) -> str:
    """
    Tente d'extraire la marque cible depuis un texte.
    Retourne la marque normalisée ou chaîne vide.
    """
    norm = _normalize(text)
    # Tri par longueur décroissante pour éviter les faux positifs (ex: "r&s" vs "rohde & schwarz")
    for brand in sorted(config.TARGET_BRANDS, key=len, reverse=True):
        if brand in norm:
            # Retourner le nom en casse correcte (capitalisé)
            return brand.title()
    return ""


def filter_lots(lots: list[dict]) -> list[dict]:
    """
    Filtre une liste de lots et retourne uniquement ceux dans le scope.
    Ajoute le champ `marque` si manquant.
    """
    kept: list[dict] = []
    for lot in lots:
        # Enrichir la marque si absente
        if not lot.get("marque"):
            detected = extract_brand(f"{lot.get('nom', '')} {lot.get('description', '')}")
            if detected:
                lot["marque"] = detected

        in_scope, reason = is_lot_in_scope(lot)
        if in_scope:
            kept.append(lot)
        else:
            logger.debug("Lot ignoré [{}] → {}", lot.get("nom", "?")[:60], reason)

    logger.info(
        "Filtrage : {}/{} lots conservés",
        len(kept),
        len(lots),
    )
    return kept
