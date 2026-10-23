# Optimisation de w — Rendu commun

## 1. Définition du problème

- Nous cherchons un chemin entre un départ et une arrivée dans une grille comportant des obstacles et des cases de poids différents.
- La carte est entièrement connue avant la recherche. Les déplacements sont autorisés dans **8 directions** et coûtent le poids de la case d’arrivée, y compris en diagonale. Le départ ne coûte rien.
- Nous utilisons **A* pondéré** : `f = g + w × h`.
  - `g` : coût accumulé depuis le départ.
  - `h` : estimation du coût restant jusqu’à l’arrivée.
  - `w` : poids donné à cette estimation, que nous cherchons à optimiser.
- **w = 0** correspond à une recherche par coût accumulé, comme Dijkstra ; **w = 1** correspond à A* classique.
- Un grand w peut accélérer la recherche en privilégiant la direction de l’arrivée, mais produire un chemin plus coûteux.
- Notre objectif est de trouver un compromis entre **temps de recherche, mémoire utilisée et qualité du chemin**.
- La version rendue, sur **`guillian`**, compare les couples **(heuristique, w)** avec Grid Search et Random Search, sur une carte fixe ou plusieurs cartes aléatoires partagées entre tous les candidats.
- La plage proposée par défaut dans l’interface est **w de 1 à 50, par pas de 1** ; elle reste configurable. Une graine permet de reproduire les cartes et les tirages de paramètres.

## 2. Comment nous évaluons les réglages

- **Dijkstra est notre référence sur chaque carte** : il fournit le coût optimal ainsi que des mesures de temps, de mémoire et de nœuds développés.
- Nous calculons des **sous-scores sans unité, sur 100**, puis un score global à **maximiser**.
- Pour le temps, la mémoire et les nœuds développés :
  - `score = 100 × valeur Dijkstra / (valeur Dijkstra + valeur mesurée)`.
  - Une consommation égale à Dijkstra donne **50/100** ; une consommation inférieure donne un score supérieur.
  - Si les deux valeurs sont nulles, le score vaut 50.
- Pour la qualité du chemin :
  - `score qualité = min(100, 100 × coût optimal / coût trouvé)`.
  - Un chemin optimal donne **100/100** ; un chemin deux fois plus coûteux donne **50/100**. Un chemin réussi de coût nul donne 100.
- Un échec de recherche donne **0 sur tous les sous-scores**.
- Le score global est une moyenne pondérée, avec les priorités suivantes par défaut :
  - **40 % temps**, **40 % mémoire**, **20 % qualité**, **0 % nœuds développés**.
  - `score global = 0,4 × score temps + 0,4 × score mémoire + 0,2 × score qualité`.
  - Ces pondérations sont modifiables, y compris après les mesures, sans relancer les recherches.
- Sur plusieurs cartes, nous faisons la moyenne des scores. Le classement privilégie d’abord le **taux de réussite**, puis le critère choisi.
- Pour limiter le bruit, nous effectuons un échauffement puis **3 mesures de temps par configuration et par carte** par défaut. Le temps retenu est la moyenne après filtrage des valeurs aberrantes.
- La mémoire est le **pic d’allocations Python pendant la recherche**, mesuré dans une exécution supplémentaire et un processus dédié. Elle exclut la carte d’entrée et ne représente pas la RAM totale du programme.
- Le temps de recherche exclut la création de la carte, le réseau et l’animation. Les mesures brutes et les paramètres sont exportables en CSV/JSON.

## 3. Résultats

### Premiers essais du groupe

- Sur une grille fixe avec obstacle et poids variables, une première recherche combine environ **100 valeurs de w**, puis un Hill Climbing autour des **10 meilleurs points**.
- Avec un score donnant autant d’importance au coût qu’à la durée, le **meilleur résultat rapporté est w = 171**. Ce résultat fluctue entre les lancements, ce qui met en évidence la sensibilité aux mesures de temps.
- Sur cette même grille, en donnant **10 fois plus d’importance au coût qu’à la durée**, le **meilleur résultat rapporté devient w = 1**, décrit comme plus stable.
- Ces essais, consignés dans les rendus de `pauline_recherche` et `theo`, montrent que le meilleur w dépend des priorités du score. Ils ont motivé l’utilisation de pondérations ajustables et de mesures répétées dans notre version finale.
- Les scores de ces premiers essais diffèrent du score final sur 100 : leurs valeurs ne sont donc pas directement comparables.

### Résultats vérifiés dans la version finale

- Sur notre scénario contrôlé **3 × 3**, toutes les cases valent 1 sauf le centre qui vaut 9. Le départ et l’arrivée sont deux coins opposés.
  - **L∞, w = 1** : A* contourne le centre ; **coût du chemin = 3**.
  - **L∞, w = 20** : A* traverse le centre ; **coût du chemin = 10**, soit environ **+233,3 %** par rapport à l’optimum et un **score qualité de 30/100**.
  - **w = 0** : A* retrouve le coût et le nombre de nœuds développés de Dijkstra sur ce scénario.
- Ces résultats sont vérifiés par les tests de `agent/test_experiments.py` ; ils illustrent la dégradation possible du coût lorsque w augmente.
- Avec nos pondérations par défaut, **Dijkstra obtient 60/100 sur une carte accessible** : 50 pour le temps, 50 pour la mémoire et 100 pour la qualité.
- Nous n’avons pas de meilleur w global établi par une campagne multi-cartes conservée dans ce rendu. Les résultats ci-dessus ne permettent pas de conclure à une valeur universelle.
- **Bilan :** le choix de w dépend de la carte, de l’heuristique et des priorités retenues. Notre outil permet de comparer ces réglages dans les mêmes conditions et de conserver les résultats pour justifier le compromis choisi.
