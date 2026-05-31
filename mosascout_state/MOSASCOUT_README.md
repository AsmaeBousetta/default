# MosaScout · base persistante

**Objectif** : transformer MosaScout d'un assistant qui démarre à zéro à chaque conversation, en un agent qui maintient une mémoire de business entre les sessions.

Ce dossier contient **8 fichiers de référence** que je dois lire au démarrage de chaque session. Ils sont la "mémoire long terme" du business.

---

## Les 8 fichiers — ordre de lecture

### 1. `prompt_MosaScout_OPTIMAL_v4.txt` — méthode
La méthode actuelle. À copier-coller au début de chaque session pour cadrer mon travail. Évolue avec les leçons apprises.

### 2. `state.json` — pipeline en cours
Tous les candidats actuellement en watchlist ou ARMED. C'est ma "todo list" inter-session. Format JSON avec :
- `pipeline` : liste de candidats actifs
- `armed` : auto-bids en cours
- `last_scan` : timestamp du dernier scan
- `budget_status` : capital engagé / réserve / disponible

### 3. `watchlist.csv` — historique bid
Append-only log. Chaque ligne = un check d'un lot à un instant. Permet de tracer la pente d'escalade et détecter les "signal pro alerté".

Colonnes : `timestamp`, `lot_id`, `marteau`, `bids`, `watchers`, `notes`

### 4. `pathfinder_blacklist.json` — marchés morts confirmés
Liste des modèles/marques où eBay sold = 0-1 résultats sur ≥2 marchés. Permet de SKIP automatiquement sans re-vérifier.

### 5. `whitelist_extended.json` — marques Tier 1 + Tier 2
Tier 1 : 30 marques du brief original (scan systématique)
Tier 2 : marques découvertes viables par calibration v4 (Sato confirmé, Marantz B2C-only, etc.)
Tier 2-Blacklisted : marques testées et rejetées (Lutron, Testo Saveris2 saturé)

### 6. `coefs_calibrated.json` — coefficients B2B
Démarrage : valeurs heuristiques du brief original.
Évolution : recalibrés à partir du `journal_postmortem.md` à chaque ≥5 ventes effectives.

### 7. `journal_postmortem.md` — calibration ventes réelles
À chaque revente effective, Asmae note : marteau final, prix revente, délai, négo, lessons.
Format markdown libre. Source de vérité pour recalibrer les coefs B2B au fil du temps.

### 8. Ce fichier (`MOSASCOUT_README.md`)
La méta-doc qui explique comment tout fonctionne.

---

## Workflow type pour démarrer une session

1. **Lire** les 7 fichiers dans l'ordre : `prompt_v4`, `state.json`, `watchlist.csv` (tail 20), `pathfinder_blacklist.json`, `whitelist_extended.json`, `coefs_calibrated.json`, `journal_postmortem.md` (tail 5)
2. **Identifier** ce qui a changé depuis le dernier check (clôtures passées, nouveaux candidats à scanner, post-mortems à intégrer)
3. **Demander** à Asmae la fenêtre + budget + mode pour la session
4. **Travailler** en méthode v4 + écrire les outputs dans la base persistante (mettre à jour state.json, ajouter à watchlist.csv, journal, etc.)

---

## Phase 2-4 à venir (architecture agent)

- **Phase 2** : scripts Python qui scrapent Troostwijk + eBay et écrivent dans ces fichiers automatiquement
- **Phase 3** : scheduled tasks qui exécutent les scrapers + génèrent les briefings quotidiens
- **Phase 4** : alertes Gmail/Slack quand un lot score >10 ou qu'un bid explose un plafond

---

## Mémoire critique session 27-28 mai 2026

Ce qui a été appris cette session (pour ne pas re-découvrir) :

- **Lutron TM-947SD** = Pathfinder confirmé (0 sold .de + .fr). Blacklisté.
- **Testo Saveris 2** = saturation neuf (38 active new vs 6 sold sur 90j). Coef B2B effondré. Skip par défaut.
- **HP 8153A** = scout surestimait ×2,3. Médiane sold mainframe = €200 (pas €450).
- **Tek 2465B** + **Tek 2235** = confirmés sains (15 et 25 sold/90j, ratio new/sold <0,2).
- **Sato CL4NX** = GO B2C uniquement (65 brand new actifs écrasent la marge B2B).
- **Marantz CD6007** = overbid sur le 28/05 (€120/10 bids vs plafond €67).
- **Scanner AT-002 2D** = à calibrer (marque obscure, risque Pathfinder élevé).
- **Bezorgveiling A1-40889** = format trop liquide, Makita/Milwaukee toujours overbid à J-2.

Tous ces apprentissages doivent être consignés dans les fichiers JSON.
