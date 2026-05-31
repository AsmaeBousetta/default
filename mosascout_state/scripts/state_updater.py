#!/usr/bin/env python3
"""
MosaScout · state_updater.py
Utilitaire pour mettre à jour state.json avec de nouvelles données
(check de marteau live, ajout d'un candidat, calibration eBay, etc.)

Usage :
    python3 state_updater.py update-bid <lot_id> <marteau> <bids> [watchers]
    python3 state_updater.py update-calibration <lot_id> <sold_90j> <new_active> <mediane_sold> <mediane_neuf>
    python3 state_updater.py mark-status <lot_id> <status>
    python3 state_updater.py append-watchlist <lot_id> <marteau> <bids> [watchers] [note]
    python3 state_updater.py budget-update <engaged> <armed_pending>
"""
import json
import sys
import csv
from datetime import datetime
from pathlib import Path


STATE_PATH = Path(__file__).parent.parent / "state.json"
WATCHLIST_PATH = Path(__file__).parent.parent / "watchlist.csv"


def load_state() -> dict:
    with open(STATE_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def save_state(state: dict) -> None:
    state["last_updated"] = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2, ensure_ascii=False)
    print(f"✅ state.json mis à jour à {state['last_updated']}")


def find_lot(state: dict, lot_id: str) -> dict | None:
    for pool_key in ("pipeline_active", "pipeline_future"):
        for lot in state.get(pool_key, []):
            if lot["lot_id"] == lot_id:
                return lot
    return None


def update_bid(lot_id: str, marteau, bids, watchers=None) -> None:
    """Met à jour le marteau live et l'historique watchlist."""
    marteau = float(marteau)
    bids = int(bids)
    state = load_state()
    lot = find_lot(state, lot_id)
    if not lot:
        print(f"❌ Lot {lot_id} introuvable", file=sys.stderr)
        sys.exit(1)

    now = datetime.now().astimezone().isoformat(timespec="seconds")
    lot["last_check"] = {
        "timestamp": now,
        "marteau_eur": marteau,
        "bids": bids,
        "watchers": int(watchers) if watchers and watchers != "None" else None,
    }

    # Détection overbid automatique
    plafond = lot.get("plafond_marteau_eur", 0)
    if plafond and marteau > plafond:
        ratio = marteau / plafond
        print(f"⚠️  OVERBID détecté : marteau €{marteau} > plafond €{plafond} (×{ratio:.2f})")
        if lot.get("status") not in ("OVERBID_SKIP", "SKIP_DEFAULT"):
            lot["status_history"] = lot.get("status_history", []) + [
                {"timestamp": now, "from": lot.get("status"), "to": "OVERBID_SKIP", "reason": f"marteau ×{ratio:.2f} plafond"}
            ]
            lot["status"] = "OVERBID_SKIP"

    save_state(state)
    print(f"✅ {lot_id} : marteau €{marteau} · {bids} bids · watchers {watchers}")
    append_watchlist(lot_id, marteau, bids, watchers, "auto-update")


def update_calibration(lot_id: str, sold_90j: int, new_active: int, mediane_sold: float, mediane_neuf: float = None) -> None:
    """Met à jour la calibration eBay v4 d'un lot."""
    state = load_state()
    lot = find_lot(state, lot_id)
    if not lot:
        print(f"❌ Lot {lot_id} introuvable", file=sys.stderr)
        sys.exit(1)

    sold_90j = int(sold_90j)
    new_active = int(new_active)
    mediane_sold = float(mediane_sold) if mediane_sold else None
    mediane_neuf = float(mediane_neuf) if mediane_neuf else None

    ratio = (new_active / sold_90j) if sold_90j > 0 else None

    # Médiane B2B v4 = min(sold, 0.65 × neuf)
    if mediane_sold and mediane_neuf:
        mediane_b2b = min(mediane_sold, 0.65 * mediane_neuf)
    elif mediane_sold:
        mediane_b2b = mediane_sold
    else:
        mediane_b2b = None

    lot["calibration_ebay_v4"] = {
        "timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
        "ebay_de_sold_90j": sold_90j,
        "ebay_de_new_active": new_active,
        "ratio_new_sold": round(ratio, 2) if ratio else None,
        "saturation_neuf": "HIGH" if (ratio and ratio > 3) else "LOW",
        "mediane_sold_used_eur": mediane_sold,
        "prix_neuf_entry_eur": mediane_neuf,
        "mediane_B2B_v4_eur": round(mediane_b2b, 1) if mediane_b2b else None,
    }

    # Si Pathfinder détecté → flag SKIP
    if sold_90j == 0:
        lot["status"] = "PATHFINDER_BLACKLIST"
        print(f"🚨 PATHFINDER détecté : {lot_id} · 0 ventes → blacklist auto")

    save_state(state)
    print(f"✅ Calibration {lot_id} : sold={sold_90j} · new={new_active} · ratio={ratio:.2f if ratio else 'N/A'} · médiane B2B v4 = €{mediane_b2b}")


def append_watchlist(lot_id: str, marteau: float, bids: int, watchers=None, note="") -> None:
    """Append une ligne à watchlist.csv."""
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with open(WATCHLIST_PATH, "a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([now, lot_id, marteau, bids, watchers or "", note])


def mark_status(lot_id: str, status: str) -> None:
    state = load_state()
    lot = find_lot(state, lot_id)
    if not lot:
        print(f"❌ Lot {lot_id} introuvable", file=sys.stderr)
        sys.exit(1)
    old_status = lot.get("status")
    lot["status"] = status
    lot["status_history"] = lot.get("status_history", []) + [
        {"timestamp": datetime.now().astimezone().isoformat(timespec="seconds"),
         "from": old_status, "to": status}
    ]
    save_state(state)
    print(f"✅ {lot_id} : {old_status} → {status}")


def budget_update(engaged: float, armed_pending: float) -> None:
    state = load_state()
    bs = state.get("budget_status", {})
    total = bs.get("total_budget_eur", 800)
    bs["engaged_eur"] = float(engaged)
    bs["armed_pending_eur"] = float(armed_pending)
    bs["reserve_eur"] = total - float(engaged) - float(armed_pending)
    state["budget_status"] = bs
    save_state(state)
    print(f"✅ Budget : engagé €{engaged} · armed €{armed_pending} · réserve €{bs['reserve_eur']}")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)
    cmd = sys.argv[1]
    args = sys.argv[2:]
    try:
        if cmd == "update-bid":
            update_bid(*args)
        elif cmd == "update-calibration":
            update_calibration(*args)
        elif cmd == "append-watchlist":
            append_watchlist(*args)
        elif cmd == "mark-status":
            mark_status(*args)
        elif cmd == "budget-update":
            budget_update(*args)
        else:
            print(f"❌ Commande inconnue : {cmd}")
            print(__doc__)
            sys.exit(1)
    except TypeError as e:
        print(f"❌ Arguments invalides : {e}")
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
