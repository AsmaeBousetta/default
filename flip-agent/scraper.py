"""Scraper Troostwijk/Vavato via Playwright.

Troostwijk utilise une SPA React ; Playwright est nécessaire pour rendre le JS.
Stratégie :
  1. Chercher par mots-clés sur troostwijkauctions.com
  2. Parcourir les pages de résultats
  3. Extraire les informations de chaque lot visible
"""
from __future__ import annotations

import asyncio
import random
import re
import time
from datetime import datetime
from typing import Any

from loguru import logger
from playwright.async_api import (
    Browser,
    BrowserContext,
    Page,
    async_playwright,
)

import config

# ── Constantes ────────────────────────────────────────────────────────────────

BASE_URL = "https://www.troostwijkauctions.com"
SEARCH_URL = f"{BASE_URL}/en/search/"

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) "
    "Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]


# ── Helpers ───────────────────────────────────────────────────────────────────

async def _random_delay() -> None:
    delay = random.uniform(config.REQUEST_DELAY_MIN, config.REQUEST_DELAY_MAX)
    await asyncio.sleep(delay)


def _clean_price(text: str) -> float | None:
    """Extrait un montant numérique depuis un texte genre '€ 1.234,56' ou '1234.56'."""
    if not text:
        return None
    # Supprimer symboles monétaires et espaces
    cleaned = re.sub(r"[€$£\s]", "", text)
    # Format européen : 1.234,56 → 1234.56
    if re.search(r"\d\.\d{3},", cleaned):
        cleaned = cleaned.replace(".", "").replace(",", ".")
    # Format avec virgule décimale : 1234,56 → 1234.56
    elif "," in cleaned and "." not in cleaned:
        cleaned = cleaned.replace(",", ".")
    # Supprimer points séparateurs de milliers restants
    cleaned = re.sub(r"\.(?=\d{3})", "", cleaned)
    try:
        return float(re.sub(r"[^\d.]", "", cleaned))
    except (ValueError, TypeError):
        return None


def _parse_date(text: str) -> str | None:
    """Tente de parser une date relative ou absolue → ISO 8601."""
    if not text:
        return None
    # Retourner tel quel si déjà ISO
    if re.match(r"\d{4}-\d{2}-\d{2}", text):
        return text
    # Date DD/MM/YYYY HH:MM
    m = re.search(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})\s*(\d{2}:\d{2})?", text)
    if m:
        day, month, year = m.group(1), m.group(2), m.group(3)
        time_part = m.group(4) or "00:00"
        try:
            dt = datetime.strptime(f"{day}/{month}/{year} {time_part}", "%d/%m/%Y %H:%M")
            return dt.isoformat()
        except ValueError:
            pass
    return text  # Retourner brut si on ne peut pas parser


def _extract_lot_id(url: str) -> str:
    """Extrait l'ID du lot depuis l'URL."""
    # https://www.troostwijkauctions.com/en/lot/12345678/...
    m = re.search(r"/lot/(\d+)", url)
    if m:
        return m.group(1)
    # Fallback : dernière partie de l'URL
    parts = url.rstrip("/").split("/")
    return parts[-1] if parts else url


# ── Sélecteurs CSS / XPath ────────────────────────────────────────────────────
# Ces sélecteurs sont indicatifs et peuvent nécessiter adaptation selon
# la version du site Troostwijk au moment du scraping.

LOT_CARD_SELECTORS = [
    "[data-testid='lot-card']",
    ".lot-card",
    ".LotCard",
    "[class*='LotCard']",
    "[class*='lot-card']",
    "article[class*='lot']",
]

TITLE_SELECTORS = [
    "[data-testid='lot-title']",
    "h2[class*='title']",
    "h3[class*='title']",
    ".lot-title",
    "[class*='LotTitle']",
]

PRICE_SELECTORS = [
    "[data-testid='current-bid']",
    "[data-testid='lot-price']",
    "[class*='CurrentBid']",
    "[class*='current-bid']",
    "[class*='price']",
]

CLOSING_DATE_SELECTORS = [
    "[data-testid='closing-date']",
    "[data-testid='end-date']",
    "[class*='ClosingDate']",
    "[class*='closing-date']",
    "time",
]


# ── Extraction d'un lot depuis sa card ────────────────────────────────────────

async def _extract_lot_from_card(card, base_page_url: str) -> dict[str, Any] | None:
    """Extrait les données d'une card de lot."""
    try:
        # URL du lot
        link = await card.query_selector("a[href*='/lot/']")
        if not link:
            return None
        href = await link.get_attribute("href") or ""
        if not href:
            return None
        lot_url = href if href.startswith("http") else f"{BASE_URL}{href}"

        # Titre
        nom = ""
        for sel in TITLE_SELECTORS:
            el = await card.query_selector(sel)
            if el:
                nom = (await el.inner_text()).strip()
                break
        if not nom:
            nom = (await card.inner_text()).split("\n")[0].strip()[:200]

        # Prix
        prix_actuel = None
        for sel in PRICE_SELECTORS:
            el = await card.query_selector(sel)
            if el:
                prix_text = (await el.inner_text()).strip()
                prix_actuel = _clean_price(prix_text)
                if prix_actuel is not None:
                    break

        # Date de clôture
        date_cloture = None
        for sel in CLOSING_DATE_SELECTORS:
            el = await card.query_selector(sel)
            if el:
                date_text = await el.get_attribute("datetime") or await el.inner_text()
                date_cloture = _parse_date(date_text.strip())
                if date_cloture:
                    break

        # Localisation
        localisation = ""
        loc_el = await card.query_selector(
            "[data-testid='location'], [class*='location'], [class*='Location']"
        )
        if loc_el:
            localisation = (await loc_el.inner_text()).strip()

        # Favoris
        favoris = 0
        fav_el = await card.query_selector(
            "[data-testid='favorites'], [class*='favorite'], [class*='Favorite']"
        )
        if fav_el:
            fav_text = (await fav_el.inner_text()).strip()
            try:
                favoris = int(re.sub(r"[^\d]", "", fav_text) or "0")
            except ValueError:
                pass

        lot_id = _extract_lot_id(lot_url)

        return {
            "lot_id": lot_id,
            "url": lot_url,
            "nom": nom,
            "marque": "",
            "modele": "",
            "prix_actuel": prix_actuel,
            "devise": "EUR",
            "date_cloture": date_cloture,
            "localisation": localisation,
            "favoris": favoris,
            "description": "",
            "categorie": "",
            "scrape_at": datetime.utcnow().isoformat(),
        }
    except Exception as exc:
        logger.warning("Erreur extraction card : {}", exc)
        return None


# ── Enrichissement depuis la page de détail ───────────────────────────────────

async def _enrich_lot_detail(page: Page, lot: dict[str, Any]) -> dict[str, Any]:
    """
    Visite la page de détail du lot pour extraire description + infos manquantes.
    Retourne le lot enrichi.
    """
    try:
        await page.goto(lot["url"], wait_until="domcontentloaded", timeout=20_000)
        await _random_delay()

        # Description
        for sel in [
            "[data-testid='lot-description']",
            "[class*='description']",
            "[class*='Description']",
            ".lot-description",
        ]:
            el = await page.query_selector(sel)
            if el:
                lot["description"] = (await el.inner_text()).strip()[:2000]
                break

        # Attributs / tableau de caractéristiques
        rows = await page.query_selector_all(
            "[class*='attribute'], [class*='Attribute'], "
            "table tr, dl dt, .property-row"
        )
        attr_text = ""
        for row in rows[:20]:
            attr_text += (await row.inner_text()).strip() + " | "
        if attr_text:
            lot["description"] = f"{lot.get('description', '')} | Attributs: {attr_text[:500]}"

        # Localisation si manquante
        if not lot.get("localisation"):
            for sel in [
                "[data-testid='auction-location']",
                "[class*='location']",
                "[class*='Location']",
            ]:
                el = await page.query_selector(sel)
                if el:
                    lot["localisation"] = (await el.inner_text()).strip()
                    break

        # Catégorie depuis le breadcrumb
        breadcrumbs = await page.query_selector_all(
            "[class*='breadcrumb'] a, nav[aria-label*='breadcrumb'] a"
        )
        if breadcrumbs:
            crumbs = [await b.inner_text() for b in breadcrumbs]
            lot["categorie"] = " > ".join(crumbs[1:])  # skip "Home"

    except Exception as exc:
        logger.warning(
            "Enrichissement détail échoué pour {} : {}", lot.get("url", "?"), exc
        )
    return lot


# ── Scraping d'une page de résultats ──────────────────────────────────────────

async def _scrape_search_page(
    page: Page, query: str, page_num: int
) -> list[dict[str, Any]]:
    """Scrape une page de résultats de recherche."""
    url = f"{SEARCH_URL}?q={query.replace(' ', '+')}&page={page_num}"
    logger.debug("Scraping : {}", url)

    try:
        await page.goto(url, wait_until="networkidle", timeout=30_000)
    except Exception as exc:
        logger.warning("Timeout chargement {} : {}", url, exc)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20_000)
        except Exception as exc2:
            logger.error("Échec chargement {} : {}", url, exc2)
            return []

    await _random_delay()

    # Tenter différents sélecteurs de card
    cards = []
    for sel in LOT_CARD_SELECTORS:
        cards = await page.query_selector_all(sel)
        if cards:
            logger.debug("Sélecteur '{}' → {} cards trouvées", sel, len(cards))
            break

    if not cards:
        logger.debug("Aucune card trouvée sur {} (fin de pagination ?)", url)
        return []

    lots: list[dict[str, Any]] = []
    for card in cards:
        lot = await _extract_lot_from_card(card, url)
        if lot:
            lots.append(lot)

    logger.info(
        "Recherche '{}' page {} → {} lots bruts", query, page_num, len(lots)
    )
    return lots


# ── Point d'entrée principal ──────────────────────────────────────────────────

async def scrape_all() -> list[dict[str, Any]]:
    """
    Lance le scraping pour toutes les requêtes configurées.
    Retourne la liste de tous les lots (non filtrés).
    """
    all_lots: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    async with async_playwright() as pw:
        browser: Browser = await pw.chromium.launch(
            headless=config.PLAYWRIGHT_HEADLESS,
            args=[
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
            ],
        )

        context: BrowserContext = await browser.new_context(
            user_agent=random.choice(USER_AGENTS),
            viewport={"width": 1280, "height": 900},
            locale="en-GB",
            timezone_id="Europe/Paris",
            extra_http_headers={
                "Accept-Language": "en-GB,en;q=0.9,fr;q=0.8",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            },
        )

        # Page de navigation principale
        search_page: Page = await context.new_page()
        # Page de détail (réutilisée)
        detail_page: Page = await context.new_page()

        try:
            for query in config.SEARCH_QUERIES:
                for page_num in range(1, config.MAX_PAGES_PER_RUN + 1):
                    lots = await _scrape_search_page(search_page, query, page_num)

                    if not lots:
                        break  # Fin de pagination pour cette requête

                    # Dédupliquer par URL
                    new_lots = [l for l in lots if l["url"] not in seen_urls]
                    for l in new_lots:
                        seen_urls.add(l["url"])

                    # Enrichir les nouveaux lots avec la page de détail
                    for i, lot in enumerate(new_lots):
                        logger.debug(
                            "Enrichissement {}/{} : {}",
                            i + 1,
                            len(new_lots),
                            lot["nom"][:60],
                        )
                        enriched = await _enrich_lot_detail(detail_page, lot)
                        all_lots.append(enriched)
                        await _random_delay()

                    await _random_delay()

        finally:
            await browser.close()

    logger.info("Scraping terminé : {} lots collectés au total", len(all_lots))
    return all_lots


def scrape_with_retry(max_retries: int = 3) -> list[dict[str, Any]]:
    """
    Lance le scraping avec retry x3 en cas d'erreur.
    Interface synchrone pour le scheduler.
    """
    for attempt in range(1, max_retries + 1):
        try:
            return asyncio.run(scrape_all())
        except Exception as exc:
            logger.warning(
                "Scraping échoué (tentative {}/{}) : {}", attempt, max_retries, exc
            )
            if attempt < max_retries:
                wait = 2 ** attempt
                logger.info("Réessai dans {}s...", wait)
                time.sleep(wait)

    logger.error("Scraping abandonné après {} tentatives", max_retries)
    return []
