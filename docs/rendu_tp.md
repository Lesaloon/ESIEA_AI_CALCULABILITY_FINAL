# Rendu de TP — Optimisation de A* pondéré

## 1. Modélisation du problème sous forme de contraintes

- Algorithme A* pondéré : `f = g + w × h`
  - `g` : coût du chemin parcouru depuis le départ
  - `h` : heuristique (estimation du coût restant jusqu'à l'arrivée)
  - `w` : pondération que l'on cherche à optimiser
- Score à minimiser : `score = (coût / coût minimum) + (durée / durée minimum)`
  - Le coût est le nombre de cases du meilleur chemin trouvé, la durée le temps mis par l'algorithme pour le trouver.
  - Chaque terme vaut au minimum 1 : on cherche donc à se rapprocher de la valeur 2.
- Choix :
  - Pas de pondération entre les deux termes : les deux métriques ont la même importance.
  - Pas de prise en compte de la mémoire, pour simplifier le problème.
- Contraintes :
  - `w ≥ 1` : en dessous, on garde un chemin optimal mais on explore plus qu'A*, donc aucun gain.
  - `w ≤ plafond` (voir partie 2) : au-delà, plus aucune amélioration n'est possible.
  - Le chemin doit être valide : du départ à l'arrivée, sans traverser d'obstacle.

## 2. Résolution du problème d'optimisation sur configuration fixe

- Configuration : grille fixe avec un obstacle et des poids sur un des chemins (voir `grille_fixe.png`).
- Stratégie de recherche, en trois étapes :
  1. **Recherche du plafond** au-delà duquel on n'a plus d'amélioration possible :
     `plafond = poids maximum × (nombre de cases franchissables − 1)`.
     C'est le coût maximal d'un chemin : au-delà, `w × h` écrase `g` et l'ordre d'exploration ne change plus. Cela limite l'espace de recherche.
  2. **Grid search** sur l'intervalle `[1, plafond]`, pour obtenir une centaine de scores et une vue globale de la courbe.
  3. **Hill climbing** autour des 10 scores les plus bas, pour chercher les minimums locaux autour de ces points. On conserve le score le plus bas parmi ces minimums locaux.
- Résultat : meilleur score obtenu pour **w = 171** (voir `resultat_recherche_1.png`).
- Analyse :
  - Avec un `w` aussi grand, `h` domine `g` : A* pondéré se comporte presque comme un Greedy. Il fonce vers l'arrivée, ce qui réduit fortement la durée de recherche.
  - Le coût du chemin reste proche du minimum sur cette grille : le gain de temps l'emporte, d'où un score minimal à grand `w`.
  - On constate des fluctuations importantes, que l'on explique par le bruit lié à la mesure de la durée (quelques microsecondes sur une petite grille, sensibles à la charge de la machine).
- Effet d'une modification de la fonction de coût :
  - Donner plus de poids au coût du chemin ferait baisser le `w` optimal vers 1 (A* classique, chemin optimal).
  - Donner plus de poids à la durée pousserait `w` vers le plafond (comportement Greedy).
  - Ajouter la mémoire favoriserait aussi les grands `w`, qui ouvrent moins de pistes.
- Effet des paramètres de recherche :
  - Un pas de grid search plus fin donne une meilleure précision mais plus d'évaluations.
  - Le nombre de points de départ du hill climbing (10) limite le risque de rester bloqué dans un mauvais minimum local.
- Avantages de cette stratégie :
  - Le plafond borne l'espace de recherche de façon justifiée.
  - Le grid search donne une vue globale, le hill climbing affine localement.
  - Partir de plusieurs points limite le piège des optimums locaux.
- Inconvénients :
  - Coûteux : une centaine d'évaluations, plus le hill climbing.
  - Sensible au bruit de mesure : deux lancements peuvent donner des `w` différents.
  - Le hill climbing peut s'arrêter sur un plateau, là où le score ne varie plus.

## 3. Test de la solution sur une configuration variable

- On reprend `w = 171` et on l'applique à d'autres grilles (autres obstacles, autres poids, autre taille).
- Ce qu'on observe :
  - Le score varie selon la grille : `w = 171` reste rapide, mais le coût du chemin peut s'éloigner du minimum.
  - Le `w` optimal n'est plus le même d'une grille à l'autre.
- Pourquoi :
  - Avec un grand `w`, l'algorithme se comporte comme un Greedy. Sur une grille avec un obstacle en U ou des poids élevés sur le chemin direct, il se fait piéger et le coût augmente.
  - Le plafond dépend du poids maximum et du nombre de cases franchissables : il change avec la grille, donc la plage utile de `w` aussi.
  - L'équilibre entre `g` et `h` dépend de la taille de la grille, des poids et de l'heuristique.
- Conclusion : la solution trouvée sur la grille fixe n'est pas universelle.

## 4. Gérer la recherche de paramètres (a, b, c, w, h) quand la configuration change

- `a`, `b`, `c` (poids de la fonction de coût) : ce sont nos priorités (temps, coût, mémoire). On les fixe selon l'usage, on ne les optimise pas.
- `h` : on la choisit selon la connectivité, avec une heuristique admissible (L∞ en 8 voisins, L1 en 4 voisins) pour garder une garantie sur le coût.
- `w` :
  - Relancer la recherche (plafond, puis grid search, puis hill climbing) à chaque nouvelle configuration. Le plafond se recalcule automatiquement.
  - Ou optimiser `w` sur un ensemble de grilles variées et garder le meilleur `w` en moyenne : moins optimal sur chaque grille, mais robuste.
  - Ou apprendre une règle qui donne un bon `w` à partir des caractéristiques de la grille (taille, densité d'obstacles, poids).
  - Ou faire varier `w` pendant la recherche : grand au début pour avancer vite, puis plus petit pour affiner.
- Garde-fou : imposer une contrainte de coût maximal (par exemple ≤ 1,2 × le coût minimum), pour qu'un `w` mal adapté ne donne jamais un chemin trop mauvais.
- Réduire le bruit : répéter chaque mesure de durée et garder la médiane.
