# Optimisation de w — Synthèse des démarches du groupe

- Cette synthèse présente d’abord mon travail sur `guillian`, puis les autres démarches du groupe et les valeurs rapportées dans leurs rendus.

## Objectif

- Nous cherchons un bon compromis entre la qualité du chemin et les ressources nécessaires pour le trouver.
- Nous utilisons A* pondéré : `f = g + w × h`.
  - `g` : coût du chemin déjà parcouru.
  - `h` : estimation du coût restant jusqu’à l’arrivée.
  - `w` : importance accordée à cette estimation, que nous cherchons à régler.
- `w = 1` correspond à A* classique.
- Un grand `w` privilégie la direction de l’arrivée : la recherche peut être plus rapide, mais le chemin plus coûteux.
- Le coût du chemin est la **somme des poids des cases traversées**, sans compter la case de départ. Il ne correspond au nombre de déplacements que si tous les poids valent 1.

## 1. Mon travail sur la branche `guillian`

### Préparer une comparaison contrôlée

- J’ai fait évoluer l’agent pour qu’il connaisse **toute la carte avant de chercher un chemin** : la recherche est séparée des déplacements d’exploration.
- J’ai ajouté le réglage de **w dans A***, utilisable dans l’onglet Agent et dans les expériences : `f = g + w × h`.
- J’ai ajouté un onglet **Expériences** pour comparer les heuristiques et les poids avec **Grid Search** et **Random Search**.
- Les valeurs de w sont définies par une liste ou par **A = début, B = fin, C = pas**. Par défaut, l’interface propose **1 à 50, par pas de 1** ; les poids acceptés vont de **0 à 1000**.
- Grid Search teste toutes les combinaisons ; Random Search tire des combinaisons sans remise dans la grille, ou des valeurs dans un intervalle continu.
- Je compare les réglages sur la carte actuelle ou sur plusieurs cartes aléatoires, avec **les mêmes cartes, départs et arrivées pour tous les réglages**.
- Une graine rend les tirages reproductibles. Modifier le budget de recherche ne change pas les cartes générées.
- **Dijkstra est toujours mesuré une fois par carte** comme référence de coût optimal, même si seul A* est sélectionné.

### Choisir les critères de performance

- Je relève le taux de réussite, le coût, la longueur, les nœuds développés, le temps et le pic d’allocations Python.
- Je calcule l’écart au coût optimal : `100 × (coût − coût Dijkstra) / coût Dijkstra`.
- J’ai ajouté un **score global sur 100 à maximiser**, avec des priorités modifiables :
  - **40 % temps**, **40 % mémoire**, **20 % qualité du chemin**, **0 % nœuds développés** par défaut.
  - Pour le temps, la mémoire et les nœuds : `100 × référence / (référence + valeur)` ; faire aussi bien que Dijkstra donne **50/100** sur le critère.
  - Pour la qualité : `100 × coût optimal / coût du chemin`, plafonné à 100 ; un chemin optimal donne **100/100**.
  - Le score global est la moyenne pondérée de ces critères. Avec les poids par défaut, Dijkstra obtient donc **60/100** comme référence.
- Le classement privilégie d’abord le taux de réussite, puis le critère choisi. Les pondérations du score peuvent être changées **sans relancer les recherches**.

### Réduire le bruit des mesures et conserver les résultats

- J’exécute un échauffement, puis **3 mesures de temps par configuration et par carte** par défaut.
- J’utilise la **moyenne des mesures conservées après filtrage des valeurs aberrantes**, tout en conservant les mesures brutes pour l’export.
- Je mesure la mémoire lors d’une exécution supplémentaire, séparée des mesures de temps pour éviter le surcoût du traçage mémoire.
- Les benchmarks tournent dans un **processus dédié**, sans inclure l’animation ni les échanges réseau dans le temps de recherche.
- L’interface affiche la progression, des tableaux triables et des courbes selon w ou le numéro d’essai ; les résultats sont exportables en **CSV/JSON**, et le JSON conserve aussi les cartes.
- J’ai ajouté des tests sur les tirages reproductibles, les coûts, les scores, les mesures, l’annulation et les exports, ainsi que des commentaires dans le code pour expliquer la démarche.

### Valeurs vérifiées sur ma branche

- Sur le scénario de test **3 × 3**, les cases valent 1 sauf le centre qui vaut 9 ; le départ et l’arrivée sont dans deux coins opposés, avec déplacements diagonaux autorisés.
- Avec **L∞ et w = 1**, A* contourne la case chère : **coût = 3**.
- Avec **L∞ et w = 20**, A* prend le chemin direct par le centre : **coût = 10**, soit environ **+233,3 %** par rapport à l’optimum.
- Avec **w = 0**, A* retrouve le coût et le nombre d’expansions de Dijkstra sur ce test.
- Ces valeurs sont vérifiées dans `agent/test_experiments.py` ; elles illustrent l’effet de w sur un cas contrôlé. Le meilleur w global reste à établir à partir des résultats exportés sur plusieurs cartes.

## 2. Base commune du groupe

- Branches `main`, `guillian`, `pauline_algo` et `jonathan` : mise en place de la grille, des poids, des obstacles et des algorithmes de parcours.
- Comparaison possible entre BFS, DFS, Greedy, Dijkstra et A*, selon les branches.
- Dijkstra sert de référence pour connaître le coût optimal.
- La version de `guillian` intégrée dans `main` donne à l’agent la carte complète : on peut mesurer la recherche du chemin indépendamment des déplacements d’exploration.
- `jonathan` ajoute A* pondéré avec un **w par défaut de 1,5** : c’est un réglage initial, pas un optimum mesuré.

## 3. Première recherche sur une grille fixe

- Démarche présente sur `pauline_recherche`, également décrite dans le rendu de `theo`.
- Configuration : une grille fixe avec un obstacle et des poids sur l’un des chemins.
- Premier score à minimiser : `coût / coût minimum observé + durée / durée minimum observée`.
  - Le coût et la durée ont la même importance.
  - La mémoire n’entre pas dans ce premier score.
  - La valeur idéale est 2, si un même réglage atteint les deux minima observés.
- Recherche en trois étapes :
  - Calcul d’une borne de recherche : `poids maximum × (nombre de cases franchissables − 1)`.
  - **Grid Search** : test d’environ **100 valeurs de w** entre 1 et cette borne.
  - **Hill Climbing** : affinement autour des **10 meilleurs points**, avec un **pas de 0,1** dans la version actuelle de Pauline.
- **Résultat rapporté : w = 171** pour le premier test sur cette grille.
- Limite constatée : le meilleur w fluctue entre les lancements, car les mesures de temps sont sensibles au bruit.
- La borne utilisée dépend de la carte ; sa justification dans le code de Pauline est liée à l’heuristique L1, et ne doit pas être généralisée automatiquement à toutes les heuristiques.

## 4. Donner davantage d’importance au coût du chemin

- Branche `pauline_recherche` : évolution vers un score comparé à une référence fixe, A* avec `w = 1` et la même heuristique.
- Formule : `a × coût/coût_ref + b × durée/durée_ref + c × mémoire/mémoire_ref`.
- Dans l’essai décrit dans le rendu, le coût compte **10 fois plus que la durée** et la mémoire est ignorée : `a = 10`, `b = 1`, `c = 0`.
- **Résultat rapporté : w = 1**, avec un résultat décrit comme plus stable sur cette grille.
- Interprétation : quand la qualité du chemin devient prioritaire, le réglage retenu revient à A* classique.
- Ces coefficients correspondent à l’essai du rendu ; le code actuel laisse les coefficients configurables et utilise par défaut `a = 1`, `b = 1`, `c = 0`.

## 5. Comparer plusieurs méthodes pour trouver w

- Branche `jonathan-optimisation` : **Grid Search**, **Random Search** et **Hill Climbing**.
- Branche `saru_v2` : ajout du **recuit simulé** et de la **recherche tabou**, avec comparaison sur une même carte.
- Branche `theo` : comparaison de ces méthodes et d’une méthode **hybride, grille grossière puis recherche tabou**.
- Principe des méthodes :
  - **Grid Search** : tester régulièrement toutes les valeurs de l’intervalle choisi ; simple, mais coûteux si le pas est petit.
  - **Random Search** : tester un nombre limité de valeurs tirées au hasard ; moins d’essais, mais possibilité de manquer une bonne zone.
  - **Hill Climbing** : améliorer progressivement un point de départ ; peut rester bloqué sur un minimum local ou un plateau.
  - **Recuit simulé** : accepter parfois une dégradation pour sortir d’un minimum local.
  - **Recherche tabou** : mémoriser les points récents pour éviter de tourner en rond.
  - **Hybride** : repérer une bonne zone avec une grille, puis affiner localement.
- Jonathan et Saru permettent aussi de chercher le couple **(heuristique, w)**, ou de verrouiller l’heuristique pour ne régler que w.
- Leurs scores combinent coût, temps et mémoire, normalisés par rapport à A* avec **L∞ et w = 1**.
- Théo utilise le coût optimal de Dijkstra pour normaliser le coût du chemin et le pic de taille de la file de priorité comme indicateur mémoire.
- Aucun autre meilleur w chiffré n’est consigné dans les rendus consultés pour ces comparaisons.

## 6. Vérifier si le réglage fonctionne sur d’autres cartes

- Le rendu de `theo` décrit la réutilisation de **w = 171** sur d’autres configurations : le réglage reste orienté vers la rapidité, mais le coût du chemin peut se dégrader. Aucun tableau chiffré de ces essais n’y est fourni.
- Branche `pauline_recherche` : recherche d’un **w global**, en évaluant les mêmes valeurs sur plusieurs cartes aléatoires et en conservant le meilleur score moyen.
- Branche `theo` : optimisation sur un ensemble comprenant un piège en U et trois cartes aléatoires pondérées.
- Branche `saru_v2` : comparaison de quatre stratégies :
  - Réutiliser le réglage trouvé sur la carte initiale.
  - Garder A* classique comme référence.
  - Choisir un seul couple `(heuristique, w)` performant en moyenne sur les cartes évaluées.
  - Refaire l’optimisation sur chaque carte.
- Aucun w global final chiffré n’est enregistré dans les rendus consultés.
- Conclusion : un bon w sur une carte n’est pas nécessairement un bon w sur une autre ; il dépend des obstacles, des poids, de la taille et de l’heuristique.

## 7. Comparer les protocoles de mesure

- Les temps très courts peuvent faire varier le classement d’un lancement à l’autre.
- `jonathan-optimisation` utilise la **médiane de 5 mesures de temps** par configuration et mesure la mémoire séparément.
- `saru_v2` partage les évaluations entre les méthodes sur la carte fixe : un même couple `(heuristique, w)` conserve le même score pendant la comparaison.
- Sur ma branche `guillian`, les réglages partagent les cartes mais chaque essai est mesuré séparément ; le lissage du temps limite l’influence des pics ponctuels.
- Les scores ne se comparent pas directement entre toutes les branches : les références, les critères mémoire et les protocoles de mesure diffèrent.
- Avec huit voisins et un coût minimal de 1 par déplacement, **L∞** est une heuristique admissible. `w = 1` ne garantit donc pas à lui seul un coût optimal si une autre heuristique surestime la distance.
