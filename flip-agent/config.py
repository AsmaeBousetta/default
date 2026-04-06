"""Chargement et validation de la configuration depuis .env"""
from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

# Charge .env depuis le dossier du projet
_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path)


def _require(key: str) -> str:
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Variable d'environnement manquante : {key}")
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ── Anthropic ─────────────────────────────────────────────────────────────────
ANTHROPIC_API_KEY: str = _require("ANTHROPIC_API_KEY")
ANTHROPIC_MODEL: str = "claude-sonnet-4-20250514"
ANTHROPIC_RATE_LIMIT_DELAY: float = 2.0  # secondes entre appels API

# ── Scheduler ─────────────────────────────────────────────────────────────────
CHECK_INTERVAL_HOURS: float = float(_optional("CHECK_INTERVAL_HOURS", "4"))

# ── Notifications ─────────────────────────────────────────────────────────────
SMTP_HOST: str = _optional("SMTP_HOST")
SMTP_PORT: int = int(_optional("SMTP_PORT", "587"))
SMTP_USER: str = _optional("SMTP_USER")
SMTP_PASSWORD: str = _optional("SMTP_PASSWORD")
SMTP_FROM: str = _optional("SMTP_FROM")
SMTP_TO: str = _optional("SMTP_TO")

DISCORD_WEBHOOK_URL: str = _optional("DISCORD_WEBHOOK_URL")

# ── Mode ──────────────────────────────────────────────────────────────────────
DRY_RUN: bool = _optional("DRY_RUN", "false").lower() in ("true", "1", "yes")

# ── Base de données ───────────────────────────────────────────────────────────
DATABASE_PATH: str = _optional("DATABASE_PATH", "flip_agent.db")

# ── Scraping ──────────────────────────────────────────────────────────────────
PLAYWRIGHT_HEADLESS: bool = _optional("PLAYWRIGHT_HEADLESS", "true").lower() in (
    "true",
    "1",
    "yes",
)
REQUEST_DELAY_MIN: float = float(_optional("REQUEST_DELAY_MIN", "2"))
REQUEST_DELAY_MAX: float = float(_optional("REQUEST_DELAY_MAX", "5"))
MAX_PAGES_PER_RUN: int = int(_optional("MAX_PAGES_PER_RUN", "10"))

# ── Catégories cibles (mots-clés de recherche Troostwijk) ────────────────────
SEARCH_QUERIES: list[str] = [
    # Instruments de mesure
    "oscilloscope",
    "multimeter",
    "spectrum analyzer",
    "signal generator",
    "power supply lab",
    "LCR meter",
    "network analyzer",
    # Équipement laboratoire
    "centrifuge",
    "spectrophotometer",
    "HPLC",
    "chromatograph",
    "balance laboratory",
    "pipette",
    "autoclave",
    # Médical
    "ultrasound",
    "ECG monitor",
    "patient monitor",
    "infusion pump",
    "defibrillator",
    # Audio professionnel
    "mixing console",
    "audio amplifier professional",
    "studio microphone",
    "digital audio",
    # Topographie
    "total station",
    "theodolite",
    "GPS surveying",
    "level surveying",
    "Leica",
    "Trimble",
]

# ── Marques cibles ────────────────────────────────────────────────────────────
TARGET_BRANDS: frozenset[str] = frozenset(
    [
        # Instruments de mesure
        "keysight",
        "agilent",
        "tektronix",
        "fluke",
        "rohde & schwarz",
        "rohde and schwarz",
        "r&s",
        "anritsu",
        "yokogawa",
        "rigol",
        # Labo / médical
        "mettler-toledo",
        "mettler toledo",
        "sartorius",
        "eppendorf",
        "thermo scientific",
        "thermo fisher",
        "varian",
        "hach",
        "jenway",
        "shimadzu",
        "perkinelmer",
        "waters",
        # Topographie
        "leica",
        "trimble",
        "topcon",
        "sokkia",
        "nikon surveying",
        # Audio pro
        "neve",
        "ssl",
        "solid state logic",
        "neumann",
        "sennheiser",
        "shure",
        "genelec",
        "api audio",
        "avid",
        "digidesign",
        # IT / Code-barres
        "zebra",
        "honeywell",
        "datalogic",
        # Visualisation
        "barco",
        "christie",
        "nec display",
    ]
)
