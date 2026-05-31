# Journal Post-Mortem MosaScout

Ce fichier collecte les **ventes réelles** d'Asmae pour calibrer les coefficients B2B au fil du temps.

## Pourquoi ce journal

Les coefs B2B du framework (×0,30-0,65 par catégorie) sont des heuristiques. Sans données de ventes réelles, on ne peut pas savoir si un revendeur B2B accepte vraiment 35% de la médiane sur un Sato CL4NX bulk, ou s'il négocie à 25%.

Chaque vente que tu finalises doit être consignée ici. Quand ≥5 ventes dans une catégorie, on recalcule le coef_use dans `coefs_calibrated.json`.

---

## Format type d'une entrée

```
### YYYY-MM-DD · [Lot ID] · [Brand Model]

- **Acquisition** : marteau €X · frais €Y · capital tout-inclus €Z · acheté le DD/MM
- **Médiane scout au moment** : €A
- **Médiane eBay sold vérifiée** : €B (URL : ...)
- **Mode revente** : B2B revendeur / B2C eBay unitaire / B2C Marktplaats
- **Prix initial demandé** : €C
- **Négociation** : -€D (raison)
- **Prix final** : €E
- **Délai cycle** : J0 acquisition → J+N paiement reçu (N = nombre jours)
- **Coef B2B effectif** : prix_final / médiane = X,XX
- **Note qualité** : intact / usures / DOA
- **Leçon** : ...
```

---

## Entrées (à venir)

*Aucune vente effective consignée. Première entrée attendue : Sato CL4NX si gagné 28/05.*

---

## Calibration cumulative par catégorie

| Catégorie | Coef heuristique | Coef réel calibré | n ventes |
|---|---|---|---|
| mass_market_b2b | 0,35 | — | 0 |
| test_eq_intemporel | 0,55 | — | 0 |
| outils_main_pro | 0,45 | — | 0 |
| pro_av_legacy | 0,30 | — | 0 |
| audio_hifi_legacy | 0,30 | — | 0 |
| consumables_sealed | 0,40 | — | 0 |

---

## Leçons macro (à enrichir)

- **17/05/2026 · Crestron DMPS3** : jamais estimer une revente sans ouvrir l'URL eBay sold. Ratio retail/used peut être 1:24.
- **20/05/2026 · Pathfinder 6140** : vérifier la demande ACTIVE (annonces en cours), pas seulement les ventes passées.
- **20/05/2026 · VAMATEC Eisenblätter** : volume physique = hard filter. Palette = SKIP automatique pour solo Liège.
- **20/05/2026 · sur-estimation marteau** : le marteau actuel est un FAIT, le marteau de clôture est une INCONNUE.
- **20/05/2026 · ROI double** : toujours calculer 2 scénarios B2B + B2C. Plafond se cale sur B2B conservateur.
- **27/05/2026 · CT50 10×** : alpha-window se referme dès 15-20 watchers + 5+ bids à J-1.
- **28/05/2026 · Testo Saveris 2 saturation neuf** : marché peut être détruit par l'offre neuve abondante. Ratio NEW/SOLD est aussi important que la médiane sold.
- **28/05/2026 · Lutron Pathfinder** : 0 sold sur 2 marchés EU = marché mort confirmé, blacklist permanente.
- **28/05/2026 · HP 8153A** : modèle "à modules" — médiane scout (mainframe + modules complets) peut être ×2-3 supérieure à la réalité du lot (mainframe seul).
- **28/05/2026 · Sweep Électronique 28/05** : la sous-cat Électronique d'un auction faillite est dominée par Tier C consumer (laptops HP/Apple, tablets, Oculus). Sur 37 lots Rein4ced Électronique, 0 GO nouveaux. Confirme la règle du brief : "Électronique = majorité Tier C SKIP, sauf Image et son". Note : le Sato CL4NX live en /c/imprimantes-et-photocopieurs, pas en /c/electronique — la sous-cat n'est pas une garantie de qualité.
- **28/05/2026 · Kramer VS-88V (A1-45499-181)** : nouveau candidat alpha-window découvert via brand-scan, eBay sold = 1/90j (US seller via FR), pathfinder risk MED. Décision : achat de RÉSERVE seulement (plafond €5), valable uniquement pour bundle B2B avec stock Kramer existant (VP-81 SIDN+SID+VS-41H).
- **28/05/2026 · Décision scope "pur électronique"** : Asmae confirme exclure tout l'outillage (perceuses, scies, lampes, marteaux, batteries d'outils) du sourcing. Hilti A1-46859 parking. Focus uniquement test eq / Pro AV / scanners POS / imprimantes étiquettes / network gear / audio pro. ROI seuil détendu à ×2.5 (vs ×3 strict).
- **28/05/2026 · A1-38772 IT Oisterwijk/Hedel NL clôture 02/06** : nouvelle goldmine identifiée. 3 lots Zebra alpha-window : ZM400 imprimante (€10/0bid/5w, médiane €150, plafond €17), MC330K mobile ×2 (€10/0bid/4w, médiane €350, plafond €39 — TOP score 16), TC210K scanner Android (€10/1bid/18w, médiane €200, plafond €22).
- **28/05/2026 · A1-45815 Faillite IT Barneveld NL clôture 01/06** : 175 lots IT enterprise. Cisco Catalyst 9300 PoE switches médiane €900 used, mais déjà escalated (€70+/12+bids). Sous-cat Électronique 133 lots — beaucoup de Tier C consumer (MacBook Pro M4 €600/18bids) à filtrer.

## Pivot méthodologique 28/05/2026 — Migration v4 → v5

**4 erreurs méthodologiques majeures identifiées par Asmae lors de la session 28/05** :

1. **Brand whitelist trop étroite (v4)** : 30 marques Tier 1 ratent les marchés industrial automation. Conséquence : auction A1-45819 Overpelt (411 lots Lenze/ABB/Siemens/Schneider) manquée — ~10 GO Siemens IPC627C/847C/427C à €100 ouverture pour médiane eBay €500/unit ratés. Profit B2C raté estimé +€1500-3000.

2. **Overgeneralization Pathfinder (v4)** : test Atlas Copco TC54S = 0 sold → "auction A1-45819 morte" → skip global. ERREUR : 1 marque Pathfinder ≠ 411 lots tous morts.

3. **Anti-watchers automatique (v4)** : Prusa MK3S+ à 148 watchers = SKIP automatique. Asmae a challengé : high-watchers = valeur confirmée. Correction v5 : armer plafond strict + walk-away discipliné, PAS SKIP automatique.

4. **Taxonomie ambigüe (v4)** : "Variateurs de vitesse / équipements industriels" mentalement classé "outillage" alors que drives/PLCs/PCs industriels = pure électronique. Correction v5 : taxonomie corrigée.

**Workflow v5 nouveau** : AUCTION-FIRST (vs brand-first v4) + universal lot inspection + Google product research pour marques inconnues + eBay sold data = critère exclusif.

**Whitelist élargie v5** : ajout industrial automation brands (Lenze · ABB ACS · Siemens Sinamics/Simatic · Schneider Altivar · Lovato · Yaskawa · Mitsubishi · Beckhoff · Omron · Bosch Rexroth · etc.) · solar (SMA · Fronius · SolarEdge) · audio HiFi premium (Klipsch · Marantz · Cambridge Audio · McIntosh) · balances lab (Kern · Sartorius · Mettler · Ohaus).

**Règles nouvelles v5** :
- Règle 10 : un Pathfinder unique ne disqualifie pas toute l'auction
- Règle 11 : high-watchers ≠ SKIP, arme plafond strict
- Règle 12 : auction-first scan obligatoire
- Règle 13 : Google research obligatoire pour marques inconnues avant SKIP

**Lesson Asmae > algo** : l'instinct produit Asmae (challenger les SKIPs prématurés, identifier IPC847C/IPC627C, demander DOA risk) dépasse l'algo agent. Workflow optimal = agent scan large + Asmae détecte gemmes + agent calibre eBay/budget.
