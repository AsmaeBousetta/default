#!/usr/bin/env python3
"""
MosaScout · daily_brief_generator.py
Génère un rapport HTML gaming HUD quotidien depuis state.json + ranking.

Usage :
    python3 daily_brief_generator.py [output_path.html]

Si pas d'output_path donné, génère un fichier daté dans le dossier projet.
"""
import json
import sys
from datetime import datetime
from pathlib import Path

# Import du moteur de ranking
sys.path.insert(0, str(Path(__file__).parent))
from ranking_engine import rank_pipeline  # noqa: E402


STATE_PATH = Path(__file__).parent.parent / "state.json"
DEFAULT_OUTPUT_DIR = Path(__file__).parent.parent.parent  # arbitrage/


HTML_TEMPLATE = r"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<title>MOSASCOUT // BRIEF {DATE}</title>
<style>
  @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;600;800;900&family=JetBrains+Mono:wght@400;600;700&family=Rajdhani:wght@500;600;700&display=swap');
  :root {{
    --bg-deep: #050818; --bg-card: rgba(15, 25, 60, 0.65);
    --grid-line: rgba(0, 217, 255, 0.08);
    --cyan: #00d9ff; --magenta: #ff00aa; --green: #00ff88;
    --amber: #ffaa00; --red: #ff3355; --gold: #ffd700;
    --ink: #e6f0ff; --ink-dim: #8fa8d6; --ink-mute: #5a6e96;
  }}
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{
    font-family: 'Rajdhani', sans-serif; color: var(--ink); line-height: 1.5;
    padding: 28px 18px 60px; min-height: 100vh;
    background:
      radial-gradient(ellipse at 20% 0%, rgba(0, 217, 255, 0.12) 0%, transparent 50%),
      radial-gradient(ellipse at 80% 100%, rgba(255, 0, 170, 0.10) 0%, transparent 50%),
      linear-gradient(135deg, #050818 0%, #0a1230 50%, #050818 100%);
    background-attachment: fixed;
  }}
  body::before {{
    content: ''; position: fixed; inset: 0;
    background-image:
      linear-gradient(var(--grid-line) 1px, transparent 1px),
      linear-gradient(90deg, var(--grid-line) 1px, transparent 1px);
    background-size: 40px 40px; pointer-events: none; z-index: 0;
  }}
  .wrap {{ max-width: 1280px; margin: 0 auto; position: relative; z-index: 1; }}
  .hud-header {{
    background: linear-gradient(135deg, rgba(10, 18, 48, 0.95) 0%, rgba(20, 30, 70, 0.9) 100%);
    border: 1px solid var(--cyan); border-radius: 4px;
    padding: 22px 28px; margin-bottom: 22px; position: relative;
    box-shadow: 0 0 30px rgba(0, 217, 255, 0.25);
  }}
  .hud-header::before, .hud-header::after {{ content: ''; position: absolute; width: 30px; height: 30px; border: 2px solid var(--magenta); }}
  .hud-header::before {{ top: -2px; left: -2px; border-right: none; border-bottom: none; }}
  .hud-header::after {{ bottom: -2px; right: -2px; border-left: none; border-top: none; }}
  .hud-label {{ font-family: 'JetBrains Mono', monospace; font-size: 0.78em; letter-spacing: 0.3em; color: var(--cyan); text-transform: uppercase; margin-bottom: 8px; }}
  h1 {{
    font-family: 'Orbitron', sans-serif; font-weight: 900; font-size: 2em; letter-spacing: 0.04em;
    background: linear-gradient(90deg, var(--cyan) 0%, #fff 50%, var(--magenta) 100%);
    -webkit-background-clip: text; background-clip: text; -webkit-text-fill-color: transparent;
    margin-bottom: 8px;
  }}
  .hud-sub {{ font-family: 'JetBrains Mono', monospace; font-size: 0.85em; color: var(--ink-dim); }}
  h2 {{ font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 1.25em; letter-spacing: 0.08em; text-transform: uppercase; color: var(--cyan); margin: 36px 0 14px; padding-left: 18px; position: relative; text-shadow: 0 0 16px rgba(0, 217, 255, 0.3); }}
  h2::before {{ content: ''; position: absolute; left: 0; top: 50%; transform: translateY(-50%); width: 8px; height: 75%; background: var(--cyan); box-shadow: 0 0 10px var(--cyan); }}

  .meta-strip {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 14px; margin: 18px 0 24px; }}
  .stat-tile {{
    background: var(--bg-card); border: 1px solid rgba(0, 217, 255, 0.3);
    border-radius: 4px; padding: 14px 16px; position: relative;
  }}
  .stat-tile::before {{ content: ''; position: absolute; top: 0; left: 0; height: 2px; width: 30%; background: var(--cyan); box-shadow: 0 0 8px var(--cyan); }}
  .stat-label {{ font-family: 'JetBrains Mono', monospace; font-size: 0.7em; color: var(--ink-mute); letter-spacing: 0.2em; text-transform: uppercase; margin-bottom: 6px; }}
  .stat-value {{ font-family: 'Orbitron', sans-serif; font-weight: 700; font-size: 1.5em; color: var(--cyan); text-shadow: 0 0 12px rgba(0, 217, 255, 0.4); }}
  .stat-value.green {{ color: var(--green); }}
  .stat-value.amber {{ color: var(--amber); }}
  .stat-value.red {{ color: var(--red); }}
  .stat-sub {{ font-family: 'JetBrains Mono', monospace; font-size: 0.72em; color: var(--ink-mute); margin-top: 4px; }}

  .data-table {{
    width: 100%; border-collapse: separate; border-spacing: 0;
    margin: 12px 0 18px; font-family: 'Rajdhani', sans-serif; font-size: 0.9em;
    background: rgba(5, 8, 24, 0.6); border: 1px solid rgba(0, 217, 255, 0.2);
    border-radius: 4px; overflow: hidden;
  }}
  .data-table thead {{ background: linear-gradient(90deg, rgba(0, 217, 255, 0.15), rgba(255, 0, 170, 0.10)); }}
  .data-table th {{ font-family: 'JetBrains Mono', monospace; font-size: 0.7em; letter-spacing: 0.18em; text-transform: uppercase; color: var(--cyan); text-align: left; padding: 11px 12px; border-bottom: 1px solid rgba(0, 217, 255, 0.4); font-weight: 600; }}
  .data-table td {{ padding: 10px 12px; border-bottom: 1px solid rgba(0, 217, 255, 0.08); color: var(--ink); vertical-align: top; }}
  .data-table tbody tr.gold-row {{ background: linear-gradient(90deg, rgba(255, 215, 0, 0.12), rgba(255, 215, 0, 0.04)); border-left: 4px solid var(--gold); }}
  .data-table tbody tr.go-row {{ background: rgba(0, 255, 136, 0.05); border-left: 3px solid var(--green); }}
  .data-table tbody tr.warn-row {{ background: rgba(255, 170, 0, 0.05); border-left: 3px solid var(--amber); }}
  .data-table tbody tr.skip-row {{ background: rgba(255, 51, 85, 0.05); border-left: 3px solid var(--red); opacity: 0.82; }}

  .lot-id {{ font-family: 'JetBrains Mono', monospace; font-size: 0.82em; color: var(--cyan); }}
  a.lot-id {{ border-bottom: 1px dashed rgba(0, 217, 255, 0.5); padding-bottom: 1px; text-decoration: none; }}
  a.lot-id:hover {{ color: var(--magenta); border-color: var(--magenta); }}

  .price-cell {{ font-family: 'JetBrains Mono', monospace; font-weight: 700; color: var(--green); }}
  .score {{ font-family: 'Orbitron', sans-serif; font-weight: 800; font-size: 1.15em; color: var(--cyan); }}
  .tag {{ display: inline-block; padding: 3px 10px; border-radius: 2px; font-family: 'JetBrains Mono', monospace; font-size: 0.7em; letter-spacing: 0.15em; font-weight: 700; text-transform: uppercase; }}
  .tag.b2b {{ background: rgba(0, 217, 255, 0.15); color: var(--cyan); border: 1px solid var(--cyan); }}
  .tag.b2c {{ background: rgba(255, 0, 170, 0.15); color: var(--magenta); border: 1px solid var(--magenta); }}
  .footer {{ font-family: 'JetBrains Mono', monospace; font-size: 0.74em; color: var(--ink-mute); margin-top: 40px; padding-top: 20px; border-top: 1px solid rgba(0, 217, 255, 0.15); }}
</style>
</head>
<body>
<div class="wrap">

<div class="hud-header">
  <div class="hud-label">// MOSASCOUT.OPS // DAILY BRIEF // AUTO-GEN</div>
  <h1>BRIEF · {DATE_HUMAN}</h1>
  <div class="hud-sub">Auto-généré depuis <code>state.json</code> · {N_CANDIDATES} candidats en pipeline · last_updated {LAST_UPDATED}</div>
</div>

<div class="meta-strip">
  <div class="stat-tile">
    <div class="stat-label">Budget total</div>
    <div class="stat-value">€{BUDGET_TOTAL}</div>
    <div class="stat-sub">capital disponible</div>
  </div>
  <div class="stat-tile">
    <div class="stat-label">Engagé</div>
    <div class="stat-value green">€{ENGAGED}</div>
    <div class="stat-sub">{N_ARMED} lots ARMED</div>
  </div>
  <div class="stat-tile">
    <div class="stat-label">Réserve</div>
    <div class="stat-value amber">€{RESERVE}</div>
    <div class="stat-sub">disponible</div>
  </div>
  <div class="stat-tile">
    <div class="stat-label">Profit max</div>
    <div class="stat-value">€{TOTAL_PROFIT_MAX}</div>
    <div class="stat-sub">si tous wins</div>
  </div>
</div>

<h2>// Ranking v4 · classé par score_best</h2>

<table class="data-table">
<thead>
<tr><th>#</th><th>Lot</th><th>Article</th><th>Clôture</th><th>Plafond</th><th>Cap</th><th>Profit · mode</th><th>ROI</th><th>Confidence</th><th>SCORE</th></tr>
</thead>
<tbody>
{RANKING_ROWS}
</tbody>
</table>

<h2>// Action items du jour</h2>

<div style="background: var(--bg-card); border: 1px solid var(--cyan); border-radius: 4px; padding: 18px 22px;">
<ol>
{ACTION_ITEMS}
</ol>
</div>

<div class="footer">
// MOSASCOUT.OPS · BRIEF_AUTO · GENERATED {NOW_ISO}<br>
// Method: prompt_MosaScout_OPTIMAL_v4.txt · script: daily_brief_generator.py
</div>

</div>
</body>
</html>
"""


def get_medal(rank: int) -> str:
    medals = ["🥇", "🥈", "🥉"]
    return medals[rank] if rank < 3 else f"{rank+1}"


def row_class(rank: int, status: str) -> str:
    if status and "SKIP" in status.upper():
        return "skip-row"
    if status and "OVERBID" in status.upper():
        return "skip-row"
    if rank == 0:
        return "gold-row"
    if rank < 3:
        return "go-row"
    return "warn-row"


def format_ranking_rows(ranked: list) -> str:
    rows = []
    for i, c in enumerate(ranked):
        cls = row_class(i, c.get("status", ""))
        mode = c.get("best_mode", "B2B")
        profit = c["profit_b2c"] if mode == "B2C" else c["profit_b2b"]
        roi = c["roi_b2c"] if mode == "B2C" else c["roi_b2b"]
        closes = c.get("closes_at", "")[:10] if c.get("closes_at") else "?"
        rows.append(f"""<tr class="{cls}">
  <td>{get_medal(i)}</td>
  <td><a class="lot-id" href="{c.get('url', '#')}" target="_blank">{c['lot_id']}</a></td>
  <td>{c['article'][:50]}</td>
  <td>{closes}</td>
  <td class="price-cell">€{c['plafond_marteau']}</td>
  <td>€{c['capital']}</td>
  <td class="price-cell">+€{profit} <span class="tag {'b2c' if mode == 'B2C' else 'b2b'}">{mode}</span></td>
  <td>×{roi}</td>
  <td>{c.get('confidence', 'MED')}</td>
  <td class="score">{c['score_best']}</td>
</tr>""")
    return "\n".join(rows)


def format_action_items(state: dict, ranked: list) -> str:
    items = []
    for c in ranked:
        action = None
        # Trouver le lot dans state pour avoir le next_action
        for lot in state.get("pipeline_active", []):
            if lot["lot_id"] == c["lot_id"]:
                action = lot.get("next_action")
                break
        if action and "SKIP" not in c.get("status", "").upper():
            items.append(f"<li><strong>{c['lot_id']}</strong> ({c['article'][:40]}) : {action}</li>")
    if not items:
        items.append("<li>Pas d'action pending — soit tout en réserve, soit toutes les fenêtres déjà closes.</li>")
    return "\n".join(items)


def generate_brief(state_path: Path, output_path: Path) -> None:
    with open(state_path, "r", encoding="utf-8") as f:
        state = json.load(f)

    ranked = rank_pipeline(state_path)
    ranked.sort(key=lambda x: x["score_best"], reverse=True)

    bs = state.get("budget_status", {})
    total_profit_max = sum(
        max(c.get("profit_b2b_estime_eur", 0) or 0, c.get("profit_b2c_estime_eur", 0) or 0)
        for c in state.get("pipeline_active", [])
        if "SKIP" not in (c.get("status", "") or "").upper()
    )

    now = datetime.now().astimezone()
    html = HTML_TEMPLATE.format(
        DATE=now.strftime("%Y-%m-%d"),
        DATE_HUMAN=now.strftime("%A %d %B %Y"),
        NOW_ISO=now.isoformat(timespec="seconds"),
        LAST_UPDATED=state.get("last_updated", "?"),
        N_CANDIDATES=len(state.get("pipeline_active", [])),
        N_ARMED=sum(1 for c in state.get("pipeline_active", []) if "ARM" in (c.get("status", "") or "").upper()),
        BUDGET_TOTAL=bs.get("total_budget_eur", 0),
        ENGAGED=bs.get("engaged_eur", 0),
        RESERVE=bs.get("reserve_eur", 0),
        TOTAL_PROFIT_MAX=total_profit_max,
        RANKING_ROWS=format_ranking_rows(ranked),
        ACTION_ITEMS=format_action_items(state, ranked),
    )

    output_path.write_text(html, encoding="utf-8")
    print(f"✅ Brief HTML généré : {output_path}")
    print(f"   {len(ranked)} candidats classés · top score = {ranked[0]['score_best']}")


def main():
    if len(sys.argv) >= 2:
        output_path = Path(sys.argv[1])
    else:
        date_str = datetime.now().strftime("%Y-%m-%d")
        output_path = DEFAULT_OUTPUT_DIR / f"{date_str}_BRIEF-AUTO_mosascout.html"

    generate_brief(STATE_PATH, output_path)


if __name__ == "__main__":
    main()
