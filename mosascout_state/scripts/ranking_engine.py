#!/usr/bin/env python3
"""
MosaScout · ranking_engine.py
Calcule le score composite v4 pour chaque candidat dans state.json
et retourne la liste classée.

Score v4 = ROI_cycle × Cycles_par_an × Demand_factor

Utilisable indépendamment :
    python3 ranking_engine.py state.json
"""
import json
import sys
from pathlib import Path


DEMAND_FACTOR_BY_LEVEL = {
    "premium": 1.2,    # >30 ventes/90j sur ≥2 marchés EU
    "excellent": 1.0,  # 15-30 ventes/90j
    "bon": 0.7,        # 8-15 ventes/90j
    "modere": 0.5,     # 4-8 ventes/90j
    "faible": 0.3,     # 1-4 ventes/90j (risque Pathfinder)
    "mort": 0.0,       # 0-1 ventes/90j (SKIP auto)
}


def demand_level_from_sold_count(sold_90j: int) -> str:
    """Détermine le niveau de demande depuis le nombre de ventes 90j."""
    if sold_90j > 30:
        return "premium"
    if sold_90j >= 15:
        return "excellent"
    if sold_90j >= 8:
        return "bon"
    if sold_90j >= 4:
        return "modere"
    if sold_90j >= 1:
        return "faible"
    return "mort"


def saturation_penalty(ratio_new_sold: float) -> int:
    """Calcule la pénalité en niveaux à appliquer au demand factor.

    Retourne 0 (pas de pénalité), -1 (un niveau down) ou -2 (deux down).
    """
    if ratio_new_sold is None:
        return 0
    if ratio_new_sold > 5:
        return -2
    if ratio_new_sold > 3:
        return -1
    return 0


def apply_saturation_penalty(level: str, penalty: int) -> str:
    """Dégrade le demand level de N niveaux."""
    levels = ["mort", "faible", "modere", "bon", "excellent", "premium"]
    idx = levels.index(level)
    new_idx = max(0, idx + penalty)
    return levels[new_idx]


def compute_score(candidate: dict) -> dict:
    """Calcule les scores v4 B2B et B2C pour un candidat.

    score_b2b = applique la pénalité saturation neuf (revendeur B2B sensible)
    score_b2c = pas de pénalité saturation (B2C eBay individuel, marché distinct)
    score_best = max(b2b, b2c) — pour le ranking pratique
    """
    calib = candidate.get("calibration_ebay_v4", {})
    sold_90j = calib.get("ebay_de_sold_90j", 0) or 0
    new_active = calib.get("ebay_de_new_active", 0) or 0
    ratio = calib.get("ratio_new_sold")

    # Demand level base sur le volume de ventes
    base_level = demand_level_from_sold_count(sold_90j)
    penalty = saturation_penalty(ratio)

    # B2B : pénalité saturation appliquée (revendeur connaît le marché neuf)
    b2b_level = apply_saturation_penalty(base_level, penalty)
    b2b_demand_factor = DEMAND_FACTOR_BY_LEVEL[b2b_level]

    # B2C : pas de pénalité saturation (acheteur final indépendant du marché neuf)
    b2c_demand_factor = DEMAND_FACTOR_BY_LEVEL[base_level]

    # ROI cycles
    capital = candidate.get("capital_max_eur", 1)
    profit_b2b = candidate.get("profit_b2b_estime_eur", 0) or 0
    profit_b2c = candidate.get("profit_b2c_estime_eur", 0) or 0
    roi_b2b = profit_b2b / capital if capital > 0 else 0
    roi_b2c = profit_b2c / capital if capital > 0 else 0

    # Cycles par an (B2B court, B2C plus long)
    cycle_mois = candidate.get("cycle_mois") or 2.0
    cycles_b2b = 12 / cycle_mois if cycle_mois > 0 else 0
    cycles_b2c = 12 / (cycle_mois * 2) if cycle_mois > 0 else 0  # B2C ×2 cycle (plus lent)

    # Scores composites
    score_b2b = roi_b2b * cycles_b2b * b2b_demand_factor
    score_b2c = roi_b2c * cycles_b2c * b2c_demand_factor

    # Score best = celui sur lequel on doit miser
    if score_b2c > score_b2b:
        best_mode = "B2C"
        score_best = score_b2c
    else:
        best_mode = "B2B"
        score_best = score_b2b

    return {
        "lot_id": candidate.get("lot_id"),
        "article": candidate.get("article"),
        "auction": candidate.get("auction_title"),
        "closes_at": candidate.get("closes_at"),
        "plafond_marteau": candidate.get("plafond_marteau_eur"),
        "capital": capital,
        "profit_b2b": profit_b2b,
        "profit_b2c": profit_b2c,
        "roi_b2b": round(roi_b2b, 2),
        "roi_b2c": round(roi_b2c, 2),
        "demand_level_base": base_level,
        "saturation_penalty": penalty,
        "b2b_demand_factor": b2b_demand_factor,
        "b2c_demand_factor": b2c_demand_factor,
        "score_b2b": round(score_b2b, 1),
        "score_b2c": round(score_b2c, 1),
        "score_best": round(score_best, 1),
        "best_mode": best_mode,
        "confidence": candidate.get("confidence", "MED"),
        "status": candidate.get("status"),
        "url": candidate.get("url"),
    }


def rank_pipeline(state_path: Path) -> list:
    """Lit state.json et retourne la liste des candidats classés par score décroissant."""
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    pipeline = state.get("pipeline_active", [])
    scored = [compute_score(c) for c in pipeline]

    # Tri par score_best décroissant
    scored.sort(key=lambda x: x["score_best"], reverse=True)

    return scored


def print_ranking(ranked: list) -> None:
    """Affiche le ranking dans la console (Markdown-friendly)."""
    print("\n# MosaScout · ranking v4 (B2B + B2C)\n")
    print(f"{len(ranked)} candidats classés par score_best (max B2B, B2C)\n")
    print("| # | Lot | Article | Plafond | Cap | Profit | ROI | Mode | Score B2B | Score B2C | BEST |")
    print("|---|---|---|---|---|---|---|---|---|---|---|")
    medals = ["🥇", "🥈", "🥉"]
    for i, c in enumerate(ranked):
        medal = medals[i] if i < 3 else f"{i+1}"
        if c["best_mode"] == "B2B":
            profit_str = f"+€{c['profit_b2b']}"
            roi_str = f"×{c['roi_b2b']}"
        else:
            profit_str = f"+€{c['profit_b2c']}"
            roi_str = f"×{c['roi_b2c']}"
        print(
            f"| {medal} | `{c['lot_id']}` | {c['article'][:38]} | "
            f"€{c['plafond_marteau']} | €{c['capital']} | "
            f"{profit_str} | {roi_str} | **{c['best_mode']}** | "
            f"{c['score_b2b']} | {c['score_b2c']} | "
            f"**{c['score_best']}** |"
        )


def main():
    if len(sys.argv) < 2:
        # Cherche automatiquement state.json dans le dossier parent
        default_path = Path(__file__).parent.parent / "state.json"
        state_path = default_path
    else:
        state_path = Path(sys.argv[1])

    if not state_path.exists():
        print(f"❌ Fichier introuvable : {state_path}", file=sys.stderr)
        sys.exit(1)

    ranked = rank_pipeline(state_path)
    # Re-tri sur score_best (le plus pertinent stratégiquement)
    ranked.sort(key=lambda x: x["score_best"], reverse=True)
    print_ranking(ranked)

    # Optionnel : écrire le ranking dans un fichier JSON
    if len(sys.argv) >= 3:
        out_path = Path(sys.argv[2])
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(ranked, f, indent=2, ensure_ascii=False)
        print(f"\n✅ Ranking sauvegardé : {out_path}")


if __name__ == "__main__":
    main()
