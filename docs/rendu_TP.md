- [x] Modelisation du probleme sous forme de contraintes -> choix et raisons.

Algorithme A* pondéré : f = g + w* h (g : cout du chemin, h : heuristique, w : pondération que l'on cherche à optimiser)

Score = (cout/cout minimum) + (durée/durée minimum) . On cherche à se rapprocher de la valeur 2.

Le coût étant le nombre de cases du meilleur chemin trouvé et la durée étant le temps mis par l'algorithme pour trouver ce chemin.

On choisit de ne pas pondérer car les deux métriques sont d'importance égale, et on choisit de ne pas prendre en compte la mémoire pour simplifier le problème.

- [x] Resolution du probleme d'optimisation sur configuration fixe (configuration par defaut) -> presentation de la solution, des raisons et analyse des resultats (pourquoi vous avez ces resultats? qu'est-ce que ca donne de modifier la function de cout, les parametres de recherche? Quelle strategie employee? Quelles sont les avantages et les inconvenients d'une telle recherche?)

Grille fixe avec un obstacle et des poids sur un des chemins (voir fichier grille_fixe.png)

On commence par implémenter un algorithme qui commence par une recherche du plafond au delà duquel on n'a plus d'amélioration possible, à l'aide de la formule :
plafond = poids maximum × (nombre de cases franchissables − 1), ce qui nous permet de limiter l'espace de recherche. Puis on applique un gridsearch sur l'intervalle [1 - plafond] de manière à obtenir une centaine de scores. Enfin on appllique un hill climbing sur les 10 scores les plus bas de façon à chercher des minimums locaux autour de ces points bas. On conserve le score le plus bas obtenu parmis ces scores locaux. (voir fichier resultat_recherche_1.png)

Lors de notre premier test on obtient le meilleur score pour w = 171. Cependant on constate des fluctuations importantes entre les runs, que l'on peut peut-être expliquer par le bruit lié au calcul de la durée.ily a également un problème auniveaudu calcul du score car il ne permet pas de faire de comparaison entre les runs.

Dans un second temps (recherche2), on corrige le calcul du score de façon à comparer avec une valeur de référence fixe et on essaye de limiter le bruit lié à la durée, en utilisant une valeur médiane sur 3 tentatives de recherche.

- [x] Prendre la solution trouvee et la tester sur une configuration variable. Qu'est-ce que ca donne? Comment les resultats variant? Pourquoi?

- [x] Quelles solutions proposez-vous pour gerer la recherche de parametres (a, b, c, w, h) lorsque la configuration change?
