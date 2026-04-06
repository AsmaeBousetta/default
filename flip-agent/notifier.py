"""Envoi d'alertes par email SMTP et/ou webhook Discord."""
from __future__ import annotations

import json
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

import requests
from loguru import logger

import config
import database


# ── Formatage du message ──────────────────────────────────────────────────────

def _format_lot_summary(lot: dict[str, Any], analysis: dict[str, Any]) -> dict[str, str]:
    """Construit les versions texte et HTML du message d'alerte."""
    nom = lot.get("nom", "Lot inconnu")
    prix_actuel = lot.get("prix_actuel")
    prix_str = f"{prix_actuel:.0f}€" if prix_actuel is not None else "N/A"
    achat_max = analysis.get("achat_max")
    achat_max_str = f"{achat_max:.0f}€" if achat_max is not None else "N/A"
    marge = analysis.get("marge_pct")
    marge_str = f"{marge:.0f}%" if marge is not None else "N/A"
    url = lot.get("url", "")
    localisation = lot.get("localisation", "N/A")
    date_cloture = lot.get("date_cloture", "N/A")
    liquidite = analysis.get("liquidite", "N/A")
    risque = analysis.get("risque", "N/A")
    notes = analysis.get("notes", "")

    # Décotes
    decotes_raw = analysis.get("decotes_appliquees", [])
    if isinstance(decotes_raw, str):
        try:
            decotes = json.loads(decotes_raw)
        except (json.JSONDecodeError, TypeError):
            decotes = []
    else:
        decotes = decotes_raw or []
    decotes_str = ", ".join(decotes) if decotes else "aucune"

    # ── Texte brut ────────────────────────────────────────────────────────────
    text = (
        f"🎯 OPPORTUNITÉ D'ACHAT DÉTECTÉE\n"
        f"{'─' * 50}\n"
        f"Lot     : {nom}\n"
        f"Prix    : {prix_str}  →  Achat max recommandé : {achat_max_str}\n"
        f"Marge   : {marge_str} | Liquidité : {liquidite} | Risque : {risque}\n"
        f"Clôture : {date_cloture}  |  Lieu : {localisation}\n"
        f"Décotes : {decotes_str}\n"
        f"\nNotes   : {notes}\n"
        f"\nLien    : {url}\n"
    )

    # ── HTML ──────────────────────────────────────────────────────────────────
    html = f"""
<html><body style="font-family:Arial,sans-serif;max-width:600px;margin:auto">
  <h2 style="color:#e74c3c">🎯 Opportunité d'achat — {nom}</h2>
  <table style="width:100%;border-collapse:collapse">
    <tr style="background:#f8f9fa">
      <td style="padding:8px;font-weight:bold">Prix actuel</td>
      <td style="padding:8px">{prix_str}</td>
    </tr>
    <tr>
      <td style="padding:8px;font-weight:bold">Achat max recommandé</td>
      <td style="padding:8px;color:#27ae60;font-weight:bold">{achat_max_str}</td>
    </tr>
    <tr style="background:#f8f9fa">
      <td style="padding:8px;font-weight:bold">Marge estimée</td>
      <td style="padding:8px">{marge_str}</td>
    </tr>
    <tr>
      <td style="padding:8px;font-weight:bold">Liquidité</td>
      <td style="padding:8px">{liquidite}</td>
    </tr>
    <tr style="background:#f8f9fa">
      <td style="padding:8px;font-weight:bold">Risque</td>
      <td style="padding:8px">{risque}</td>
    </tr>
    <tr>
      <td style="padding:8px;font-weight:bold">Clôture</td>
      <td style="padding:8px">{date_cloture}</td>
    </tr>
    <tr style="background:#f8f9fa">
      <td style="padding:8px;font-weight:bold">Localisation</td>
      <td style="padding:8px">{localisation}</td>
    </tr>
    <tr>
      <td style="padding:8px;font-weight:bold">Décotes appliquées</td>
      <td style="padding:8px">{decotes_str}</td>
    </tr>
  </table>
  <p style="margin-top:16px;padding:12px;background:#fffde7;border-left:4px solid #f39c12">
    <strong>Notes :</strong> {notes}
  </p>
  <p>
    <a href="{url}" style="
      display:inline-block;padding:12px 24px;
      background:#2980b9;color:white;text-decoration:none;border-radius:4px;
      font-weight:bold
    ">Voir le lot →</a>
  </p>
</body></html>
"""
    return {"text": text, "html": html, "subject": f"[FlipAgent] ACHETER : {nom[:60]}"}


# ── Email SMTP ────────────────────────────────────────────────────────────────

def send_email(lot: dict[str, Any], analysis: dict[str, Any]) -> bool:
    """
    Envoie une alerte par email SMTP.
    Retourne True si succès.
    """
    if not all([config.SMTP_HOST, config.SMTP_USER, config.SMTP_PASSWORD, config.SMTP_TO]):
        logger.debug("Email désactivé (config SMTP incomplète)")
        return False

    content = _format_lot_summary(lot, analysis)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = content["subject"]
    msg["From"] = config.SMTP_FROM or config.SMTP_USER
    msg["To"] = config.SMTP_TO

    msg.attach(MIMEText(content["text"], "plain", "utf-8"))
    msg.attach(MIMEText(content["html"], "html", "utf-8"))

    try:
        with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=10) as server:
            server.ehlo()
            server.starttls()
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
            server.sendmail(config.SMTP_FROM or config.SMTP_USER, config.SMTP_TO, msg.as_string())
        logger.info("✉ Email envoyé : {}", content["subject"])
        return True
    except Exception as exc:
        logger.error("Erreur envoi email : {}", exc)
        return False


# ── Discord Webhook ───────────────────────────────────────────────────────────

def send_discord(lot: dict[str, Any], analysis: dict[str, Any]) -> bool:
    """
    Envoie une alerte via webhook Discord.
    Retourne True si succès.
    """
    if not config.DISCORD_WEBHOOK_URL:
        logger.debug("Discord désactivé (webhook non configuré)")
        return False

    nom = lot.get("nom", "Lot inconnu")
    prix_actuel = lot.get("prix_actuel")
    prix_str = f"{prix_actuel:.0f}€" if prix_actuel is not None else "N/A"
    achat_max = analysis.get("achat_max")
    achat_max_str = f"{achat_max:.0f}€" if achat_max is not None else "N/A"
    marge = analysis.get("marge_pct")
    marge_str = f"{marge:.0f}%" if marge is not None else "N/A"
    url = lot.get("url", "")
    localisation = lot.get("localisation", "N/A")
    date_cloture = lot.get("date_cloture", "N/A")
    notes = (analysis.get("notes") or "")[:300]

    embed = {
        "title": f"🎯 {nom[:200]}",
        "url": url,
        "color": 0x27AE60,  # vert
        "fields": [
            {"name": "Prix actuel", "value": prix_str, "inline": True},
            {"name": "Achat max", "value": f"**{achat_max_str}**", "inline": True},
            {"name": "Marge estimée", "value": marge_str, "inline": True},
            {
                "name": "Liquidité / Risque",
                "value": f"{analysis.get('liquidite','N/A')} / {analysis.get('risque','N/A')}",
                "inline": True,
            },
            {"name": "Clôture", "value": date_cloture, "inline": True},
            {"name": "Lieu", "value": localisation, "inline": True},
        ],
        "description": f"**Notes :** {notes}" if notes else "",
        "footer": {"text": "FlipAgent Troostwijk"},
    }

    payload = {
        "username": "FlipAgent",
        "embeds": [embed],
    }

    try:
        resp = requests.post(
            config.DISCORD_WEBHOOK_URL,
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        logger.info("🔔 Discord envoyé : {}", nom[:60])
        return True
    except Exception as exc:
        logger.error("Erreur Discord webhook : {}", exc)
        return False


# ── Dispatcher ────────────────────────────────────────────────────────────────

def notify(lot: dict[str, Any], analysis: dict[str, Any], dry_run: bool = False) -> None:
    """
    Envoie les alertes sur tous les canaux configurés si la décision est ACHETER.
    Gère la déduplication (ne renvoie pas si déjà alerté).
    """
    url = lot.get("url", "")
    decision = analysis.get("decision", "PASSER")

    if decision != "ACHETER":
        return

    nom = (lot.get("nom") or "?")[:60]

    if dry_run or config.DRY_RUN:
        logger.info("[DRY-RUN] Alerte simulée pour : {}", nom)
        return

    # ── Email ──────────────────────────────────────────────────────────────
    if config.SMTP_HOST and not database.was_alerted(url, "email"):
        success = send_email(lot, analysis)
        database.save_alert(url, "email", "ok" if success else "error")

    # ── Discord ────────────────────────────────────────────────────────────
    if config.DISCORD_WEBHOOK_URL and not database.was_alerted(url, "discord"):
        success = send_discord(lot, analysis)
        database.save_alert(url, "discord", "ok" if success else "error")
