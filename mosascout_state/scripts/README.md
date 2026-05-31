# MosaScout · scripts Python

Scripts utilitaires qui s'exécutent dans le sandbox Linux. Ils manipulent les fichiers de la base persistante (`state.json`, `watchlist.csv`, etc.) sans nécessiter d'accès internet.

**Important** : ces scripts ne scrapent PAS Troostwijk ou eBay (le sandbox bloque ces domaines). Le scraping reste fait via Chrome MCP (manuel ou via scheduled task). Les scripts gèrent la logique pure : ranking, formatage, mise à jour d'état.

---

## 1. `ranking_engine.py` — moteur de score v4

Calcule le score composite pour chaque candidat dans `state.json`.

```bash
python3 scripts/ranking_engine.py
# Affiche le ranking en console (Markdown)

python3 scripts/ranking_engine.py state.json ranked_output.json
# Sauvegarde aussi le JSON détaillé
```

**Formule** : `score = ROI_cycle × Cycles_par_an × Demand_factor`

Calcule à la fois `score_b2b` (avec pénalité saturation neuf) et `score_b2c` (sans pénalité), retient `score_best = max(b2b, b2c)`. Tri par `score_best` décroissant.

---

## 2. `state_updater.py` — utilitaires de mise à jour

Modifie `state.json` et alimente `watchlist.csv` automatiquement.

```bash
# Mettre à jour le marteau live d'un lot
python3 scripts/state_updater.py update-bid A1-45182-34 47 3 5
# (lot_id, marteau, bids, watchers)
# → détecte automatiquement les overbid et change le statut

# Mettre à jour la calibration eBay d'un lot
python3 scripts/state_updater.py update-calibration A1-45182-99 0 0 0 0
# (lot_id, sold_90j, new_active, mediane_sold, mediane_neuf)
# → calcule ratio, médiane B2B v4, et marque Pathfinder auto si sold=0

# Marquer un statut manuellement
python3 scripts/state_updater.py mark-status A1-45182-139 OVERBID_SKIP

# Append manuel à watchlist
python3 scripts/state_updater.py append-watchlist A1-12345 100 5 12 "live J-0"

# Mettre à jour le budget
python3 scripts/state_updater.py budget-update 161 0
# (engaged, armed_pending) — calcule la réserve automatiquement
```

---

## 3. `daily_brief_generator.py` — rapport HTML quotidien

Génère un brief HTML gaming HUD depuis `state.json` + le ranking.

```bash
python3 scripts/daily_brief_generator.py
# Crée un fichier daté dans arbitrage/ : YYYY-MM-DD_BRIEF-AUTO_mosascout.html

python3 scripts/daily_brief_generator.py /path/to/output.html
# Sauvegarde au chemin spécifié
```

Le brief inclut :
- Hero avec budget + engagé + réserve + profit max
- Table ranking complet (B2B + B2C + score_best)
- Action items du jour (next_action de chaque candidat actif)
- Lien direct sur chaque lot-ID

---

## Workflow type

**Matin (manuel ou via Claude)** :
1. Ouvrir Chrome MCP, scraper les marteaux live des lots du `pipeline_active`
2. Pour chaque check : `python3 state_updater.py update-bid <lot> <marteau> <bids>`
3. Lancer `python3 daily_brief_generator.py`
4. Lire le brief HTML

**Soir** :
1. Re-scraper si fenêtres de clôture imminentes
2. Update budget si auto-bids placés
3. Re-générer brief

**Après chaque vente effective** :
1. Ajouter une entrée à `journal_postmortem.md`
2. Si ≥5 ventes dans une catégorie, recalculer `coef_use` dans `coefs_calibrated.json`

---

## Limites

- Pas de scraping autonome (sandbox bloque Troostwijk/eBay) — passer par Chrome MCP
- Pas d'exécution programmée native — utiliser `mcp__scheduled-tasks` pour invoquer Claude qui lance les scripts
- Les calculs ROI sont sensibles aux médianes eBay : si la calibration est fausse, le score l'est aussi

---

## Phase 3 à venir

- Scheduled task quotidienne qui invoque Claude pour : scraper Chrome → update_state → generate brief → envoyer brief par email
- Alertes Gmail/Slack via connecteurs quand un lot passe au-dessus de son plafond
- Pre-clôture re-scan h-2 avant chaque auction major close
