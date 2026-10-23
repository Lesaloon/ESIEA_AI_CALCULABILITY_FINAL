# Modelisation du probleme sous forme de contraintes -> choix et raisons.

**Problème** : trouver un chemin entre 2 point ( départ / arriver ) dans un grille pondéré de taille $n \times n$.

**Algorithme** : $A^\ast$ pondéré $f = g + w \times h$ ($g$ : cout du chemin, $h$ : heuristique, $w$ : pondération que l'on cherche à optimiser)

**Modélisation de la Grille** :
- Chaque case accessible est un sommet de graphe.
- Des arête relie les cases voisines ; les déplacement sont autorisés dans 8 **direction** ( convexiter à 8 )
- Le coût d'un déplacement correspond au poids de la case d'arrivée, compris entre **1 et 9**, même en diagonale.
- les **Obstacle** sont modéliser par l'absence de sommet.
- **Raison** : représenter des difficultés de passage différentes et permettre à l'algorithme de choisir entre un chemin direct coûteux et un détour moins cher.

**Contraintes sur le chemin** :
- Relier le départ à l'arrivée.
- Se déplacer uniquement entre cases voisines accessibles

**Variable de décision** :
- Le poid $w$ et l'heuristique $h$ utilisés par $A^\ast$ pondéré :

$$
f(n) = g(n) + w \times h(n)
$$

- Nous bornons $w \in [0; 1000]$ dans l’application et choisissons un intervalle de recherche à l’intérieur de ces bornes.
- **Raison** : disposer d'un espace de recherche fini et configurable, allant d'un comportement équivalent a Dijkstra quand $w = 0$ à une recherche fortement guidée par l'heuristique.

**Contrainte sur l’heuristique pour garantir l’optimalité**:
- Avec nos déplacements à 8 voisins, $L_\infty$, définie par $\max(|\Delta x|, |\Delta y|)$, est admissible.
- Avec cette heuristique et $0 \leq w \leq 1$, $A^\ast$ conserve une garantie de coût optimal.
- **Raison** : mesurer le bénéfice éventuel d’une recherche plus rapide lorsque l’on accepte un chemin plus coûteux.

**fonctione objectif**
- Maximiser un score combinant le **temps**, la **mémoire** et la **qualité du chemin**, avec des pondération défini par $a, b, c$
- Les critères sont normalisés par rapport à Dijkstra sur la même carte.
- **Raison** : comparer les grandeur d'unités différentes et rendre exàplicites nos priorités.

# Resolution du probleme d'optimisation sur configuration fixe

(configuration par defaut) -> presentation de la solution, des raisons et analyse des resultats (pourquoi vous avez ces resultats? qu'est-ce que ca donne de modifier la function de cout, les parametres de recherche? Quelle strategie employee? Quelles sont les avantages et les inconvenients d'une telle recherche?)

- On fige la grille, les obstacles ... pour que tout les réglage ait le même problème
- On utilise **Dijktra** comme référence pour connaitre le cout optimal du chemin
- ensuite on cherche un coupe $(h, w)$ avec les méthodes suivante :
    - **Grid search** : tester toutes les combinaisons des heuristiques et des valeur de $w$ sélectionnées
    - **Random search** : tester un nombre limité de combinaisons tirés aléatoirement dans la liste des valeur $w$ sélectionnées.
- Par défaut : le set de $w$ tester serra de $1$ a $50$ avec un pas de $1$, et les heuristiques, $L_1$, $L_2$ et $L_\infty$
- nous retenons le réglage de $a = 0{,}4$, $b = 0{,}4$, $c = 0{,}2$ de la **fonction objectif**.
- Pour limité l'influence du broit temporel, chaque configuration est chronométrée 3 fois après un échauffement et la moyene des messures est conservées après un filtrage

## Grille vide $10 \times 10$

**configuration**
- Nous avons d’abord testé la grille par défaut : $10 \times 10$, sans obstacle, avec tous les poids à $1$, en plaçant le départ en $(0, 0)$ et l’arrivée en $(9, 9)$.
- Nous avons ensuite fixé une configuration plus discriminante :
    - Même taille, même départ et même arrivée.
    - Un mur vertical en $x = 5$, de $y = 0$ à $y = 6$.
    - Une zone centrale de poids $9$, pour les cases accessibles entre les coordonnées $2$ et $7$ sur les deux axes ; les autres cases valent $1$.
- Nous comparons $L_1$, $L_2$ et $L_\infty$, avec :
- Grid Search : 150 combinaisons, correspondant à 3 heuristiques et 50 valeurs de $w$ entre $1$ et $50$.
- Random Search : 8 combinaisons, avec la graine 42.
- Pour les mesures principales, nous avons augmenté le nombre de répétitions à 15 par configuration, après échauffement, avec le filtrage temporel de l’application.
- Le score utilisé par défaut privilégie 40 % temps, 40 % mémoire et 20 % qualité.

**Résultats sur la grille vide**
- Dijkstra trouve un chemin de coût $9$, en développant $100$ noeuds.
- Toutes les combinaisons $A^\ast$ testées trouvent également un coût de $9$, mais développent seulement $10$ nœuds.
- La mémoire mesurée est d’environ $25{,}05\,\mathrm{KiB}$ pour $A^\ast$, contre $45{,}77\,\mathrm{KiB}$ pour Dijkstra.
- Les poids donnent donc ici le même coût et le même nombre d’expansions. Le meilleur $w$ affiché change entre les expériences à cause des différences de temps mesurées.

**Analyse** : cette grille est trop simple pour départager les valeurs de $w$ sur la qualité du chemin. Elle montre surtout l’intérêt de l’heuristique pour éviter les explorations inutiles. Un meilleur score temporel ponctuel ne permet pas d’affirmer qu’un $w$ précis est réellement supérieur.

## Grille non vide $10 \times 10$
**Résultats sur la grille avec mur et terrain coûteux**

Les valeurs suivantes proviennent d’une même expérience, avec 15 mesures temporelles par configuration :

| Réglage                    | Coût du chemin | Nœuds développés | Temps lissé (ms) | Pic mémoire Python (KiB) | Score /100 |
| -------------------------- | -------------- | ---------------- | ---------------- | ------------------------ | ---------- |
| Dijkstra| 15| 54| 0,0907| 29,13| 60,00|
| $A^\ast$, $L_\infty$, $w = 1$ | 15| 35| 0,0901| 27,27| 60,73|
| $A^\ast$, $L_2$, $w = 1$ | 15| 28| 0,0738| 25,60| 63,34|
| $A^\ast$, $L_2$, $w = 4$| 15| 16| 0,0568| 24,36| 66,38|
| $A^\ast$, $L_2$, $w = 9$| 29| 14| 0,0554| 24,64| 56,84|
| $A^\ast$, $L_2$, $w = 10$| 43| 12| 0,0520| 20,93| 55,68|
| $A^\ast$, $L_2$, $w = 20$| 59| 12| 0,0496| 20,02| 54,65|

- Le meilleur score de cette expérience est obtenu avec $L_2$ et $w = 4$.
- Ce réglage conserve le coût optimal de $15$, tout en réduisant, par rapport à Dijkstra :
- Le nombre de nœuds développés d’environ 70 %.
- Le temps mesuré d’environ 37 %.
- Le pic mémoire d’environ 16 %.
- En augmentant davantage $w$, le gain de ressources devient moins intéressant face à la dégradation du chemin :
- À $w = 20$, le coût atteint $59$, soit $+293{,}3\,\%$ par rapport à l’optimum.
- Le score global baisse malgré un temps et une mémoire plus faibles.

**Explication** : avec un $w$ modéré, l’heuristique guide efficacement la recherche tout en laissant au coût accumulé une influence suffisante. Avec un grand $w$, l’algorithme privilégie davantage la direction de l’arrivée et accepte de traverser des cases coûteuses.

**Effet d’une modification de la fonction de coût** :
- Ici, nous distinguons le coût du chemin de la fonction d’évaluation utilisée pour **choisir les paramètres**.
- Augmenter l’importance de la **qualité** favorise les chemins proches du coût optimal et peut conduire à retenir un $w$ plus faible.
- Augmenter l’importance du **temps** favorise les réglages rapides, même s’ils produisent un chemin plus coûteux.
- Augmenter l’importance de la **mémoire** favorise les réglages qui conservent moins de données pendant la recherche.
- Nous pouvons recalculer les scores avec d’autres pondérations sans relancer les **recherches** : cela permet d’étudier directement l’influence de nos priorités.

# Quelle stratégie avons-nous employée ?
- Grid Search pour tester systématiquement les couples $(h, w)$.
- Random Search pour chercher un bon réglage avec moins d’essais.
- Comparaison sur la même grille, avec Dijkstra comme référence et plusieurs mesures de temps.
# Quels sont les avantages et les inconvénients ?
- **Avantages** : comparaison équitable, compromis mesurable et bons résultats avec peu d’essais en Random Search.
- **Inconvénients** : Grid Search demande beaucoup de calculs, Random Search peut manquer un bon réglage et le résultat reste sensible au bruit temporel et à la carte choisie.
