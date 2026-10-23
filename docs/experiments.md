# Recherche d’hyperparamètres

L’onglet **Expériences** compare A*, Dijkstra et les méthodes **Grid Search** et
**Random Search**. Les calculs s’exécutent dans le service Agent, indépendamment
de l’animation et du navigateur.

## Première expérience

1. Dans **Environment**, préparer la grille et placer un départ et une arrivée.
2. Ouvrir **Expériences** et conserver A*, Dijkstra, Grid Search et Random Search.
3. Choisir les heuristiques et les paramètres **A — Début**, **B — Fin** et
   **C — Pas**. Par défaut, `A = 1`, `B = 50`, `C = 1` génèrent `1, 2, …, 50`.
   Le mode liste personnalisée reste disponible (`0.5, 1, 1.5, 2`, par exemple).
4. Sélectionner **Carte actuelle** ou **Random maps**, puis lancer l’expérience.
5. Comparer le classement des algorithmes, les synthèses par méthode et le graphique `f(w)`
   et le tableau triable. Exporter les résultats avant de lancer une autre expérience.

Le poids de l’heuristique est aussi disponible dans l’onglet **Agent** pour
rejouer manuellement une configuration : `f = g + w × h`. La valeur par défaut
`w = 1` conserve le comportement précédent. `w = 0` rend A* équivalent à
Dijkstra. Dijkstra ignore toujours l’heuristique et son poids.

## Espaces de recherche

- **Grid Search** : produit cartésien des heuristiques et des poids générés par
  début/fin/pas ou fournis dans la liste.
  Trois heuristiques et quatre poids donnent douze configurations.
- **Random Search / discret** : échantillonnage uniforme sans remise dans ce même
  espace. Le nombre d’essais est limité au nombre de combinaisons disponibles.
- **Random Search / intervalle continu** : sélection uniforme d’une heuristique
  et d’un poids dans l’intervalle configuré. Si les deux bornes sont égales,
  chaque heuristique n’est évaluée qu’une fois au maximum.

Les poids d’heuristique sont compris entre 0 et 1000. Le nombre de poids dans la
grille de recherche est déterminé par le début, la fin et le pas, sans plafond
sur le nombre de valeurs. Le budget Random Search va de 1 à 180 configurations.
La graine contrôle les tirages de paramètres et les cartes, avec deux
générateurs indépendants : changer le budget ou les méthodes ne change pas les
cartes générées.

### Début, fin et pas : A, B et C

Le mode **Début / fin / pas** génère `w = A + k × C`, pour `k = 0, 1, …`
tant que `w ≤ B`. Le pas doit être strictement positif et `A ≤ B`.

| A : début | B : fin | C : pas | Poids générés |
| --- | --- | --- | --- |
| 1 | 50 | 1 | 1, 2, …, 50 |
| 0.1 | 0.3 | 0.1 | 0.1, 0.2, 0.3 |
| 1 | 2 | 0.3 | 1, 1.3, 1.6, 1.9 |

La borne finale est incluse uniquement si le pas tombe dessus. Les calculs
utilisent une arithmétique décimale pour éviter de perdre une borne à cause des
arrondis binaires. Si début et fin sont égaux, un seul poids est testé.

L’API utilise `weight_space: "range"`, `weight_start`, `weight_end` et
`weight_step`. Le mode historique `weight_space: "list"` avec `weights` reste
le mode par défaut de l’API pour préserver les requêtes existantes. L’interface
sélectionne par défaut le mode début/fin/pas. Les paramètres A/B/C sont affichés
au-dessus du graphique à partir de l’expérience enregistrée, même si le
formulaire est modifié ensuite. L’état et l’export JSON contiennent aussi
`weight_values`, la liste exacte des poids de la grille.

**Dijkstra est toujours évalué une fois par carte comme référence**, y compris
si A* seul est sélectionné. Il ne possède pas d’hyperparamètre et n’est donc
pas répété pour chaque méthode. Sélectionner uniquement Dijkstra permet de
mesurer cette référence sans rechercher de paramètres A*.

## Cartes et isolation

**Carte actuelle** : un appel gRPC lit atomiquement la grille, ses poids, le
départ et l’arrivée. Les modifications ultérieures ne changent pas l’expérience.
La lecture n’ouvre ni ne termine un run et ne déplace pas l’agent ; elle fonctionne
aussi pendant un run interactif.

**Random maps** : choisir 1 à 50 cartes, une taille de 3 à 20, une probabilité
d’obstacle de 0 à 70 % et des poids de cellules entiers de 1 à 9. Le pourcentage
est une probabilité par cellule, pas un quota exact. Les départs et arrivées sont
choisis distincts dans une même composante connexe. Si aucune composante ne
contient deux cellules, une autre carte est générée (100 tentatives maximum).

Toutes les configurations utilisent les mêmes instantanés et la même topologie
que l’agent : huit voisins, diagonales autorisées entre obstacles, coût d’entrée
égal au poids de la cellule destination. Le placement initial coûte zéro.
L’export JSON inclut les cartes réellement utilisées, leurs poids et leurs
extrémités pour conserver les conditions exactes de comparaison.

## Lecture des résultats

- **Réussite** : fraction des cartes sur lesquelles un chemin a été trouvé.
- **Coût** : somme des poids des cellules traversées, sans compter le départ.
- **Écart optimal (%)** : `100 × (coût − coût Dijkstra) / coût Dijkstra`.
  Départ égal à l’arrivée : coût et écart nuls. Carte sans chemin : coût, écart
  et longueur absents, réussite nulle.
- **Longueur** : nombre de déplacements, diagonales comprises.
- **Nœuds développés** : nombre d’expansions, y compris les réouvertures.
- **Temps (ms)** : temps de l’appel à `search`, y compris la construction des
  traces, sans le réseau, la construction de la carte ni l’animation. Une
  exécution d’échauffement précède les mesures ; chaque configuration est ensuite
  exécutée `timing_repeats` fois sur chaque carte (3 par défaut), sans
  instrumentation mémoire. La valeur utilisée est la moyenne après filtrage des
  temps aberrants, puis la moyenne sur les cartes.
- **Mémoire (KiB)** : pic d’allocations Python pendant un appel supplémentaire
  à `search`, mesuré avec `tracemalloc` dans un processus de benchmark dédié.
  Le résultat et les traces sont inclus, la carte d’entrée est construite avant
  le traçage. Ce n’est pas la RAM totale/RSS du processus ni la taille de la carte.
  Les mesures mémoire sont séparées des mesures de temps pour éviter le surcoût
  du traçage sur le temps comparé. Un seul worker mesure séquentiellement les
  configurations ; il est fermé à la fin de l’expérience.

Coût, longueur et écart sont moyennés sur les réussites ; temps, pics mémoire,
expansions et scores sont moyennés sur toutes les cartes. Le classement du meilleur réglage privilégie
le taux de réussite, puis le critère choisi, les expansions et enfin le temps.
Le score est maximisé ; coût, mémoire, temps et expansions sont minimisés.
Le tri manuel du tableau permet d’explorer les autres métriques.

### Trois exécutions et lissage du temps

Les répétitions réutilisent **exactement la même carte, le même départ, la même
arrivée et les mêmes paramètres**. L’algorithme est réinitialisé à chaque
exécution. Elles ne génèrent pas trois nouvelles cartes aléatoires. Dijkstra
bénéficie du même traitement pour conserver une référence comparable.

Pour au moins trois observations, le filtre calcule :

```text
m = médiane des temps
MAD = médiane des |temps − m|
seuil = max(3 × 1.4826 × MAD, 0.25 × m)
```

Une observation est écartée si `|temps − m| > seuil`. Le plancher de 25 % évite
de supprimer de petites variations lorsque deux mesures sont égales et que MAD
est nul. Avec une ou deux observations, aucun filtrage n’est appliqué. La valeur
finale est la **moyenne des observations conservées**, et non la médiane.

Par exemple, `10 ms, 10.5 ms, 120 ms` donnent `10.25 ms` après exclusion de
`120 ms`. La moyenne brute de `46.833… ms` est conservée séparément.
Le filtre est une règle robuste de lissage appliquée de la même manière à toutes
les configurations ; avec trois mesures, il ne constitue pas une estimation
statistique complète de la variabilité.

Le tableau et le graphique distinguent **Temps lissé** et **Temps brut moyen**.
Le temps lissé alimente les scores et le classement. Les cartes du classement,
les synthèses et le tableau indiquent combien de mesures sont conservées ou
écartées. Une configuration sur dix cartes et trois répétitions contient
30 observations de temps. La progression continue de compter les évaluations
configuration/carte, chaque évaluation comprenant ses répétitions.

Les exports CSV et JSON contiennent, pour chaque évaluation :

- `time_samples_ms` : toutes les observations, dans l’ordre d’exécution ;
- `time_used_samples_ms` : observations conservées ;
- `time_outlier_indices` : indices des observations écartées, à partir de zéro ;
- `time_mean_raw_ms` : moyenne brute ; `time_ms` : moyenne lissée ;
- `time_std_ms` : écart-type de population des observations conservées ;
- `time_min_ms`, `time_max_ms` : minimum et maximum conservés ;
- `timing_runs`, `timing_outliers` : nombre total d’observations et de rejets.

La mesure mémoire supplémentaire et l’échauffement ne sont pas inclus dans les
trois observations chronométrées. Les anciennes expériences doivent être
relancées pour obtenir ces nouveaux résultats.

### Score d’efficacité sur 100

Le score global combine des **sous-scores sans unité**, calculés carte par carte
par rapport à Dijkstra. Les millisecondes, les KiB et le coût ne sont pas
additionnés directement.

Pour le temps, la mémoire ou les expansions, avec `r` la mesure Dijkstra et `v`
la mesure de la configuration sur la même carte :

```text
score_ressource = 100 × r / (r + v)
```

Dijkstra vaut 50 sur chaque ressource. Un score au-dessus de 50 indique une
consommation inférieure à Dijkstra ; au-dessous de 50, une consommation supérieure.
Deux valeurs nulles donnent 50. La référence est fixe : ajouter des essais ne
change pas les scores déjà calculés.

La qualité utilise le coût optimal fourni par Dijkstra :

```text
score_qualité = min(100, 100 × coût_optimal / coût_trouvé)
```

Un chemin optimal vaut 100. Un coût double de l’optimal vaut 50. Lorsque départ
et arrivée coïncident, la qualité vaut 100. Un échec vaut **0 sur tous les
sous-scores et sur le score global**, même si l’algorithme s’arrête rapidement.

Les pondérations par défaut sont :

| Dimension | Poids relatif |
| --- | --- |
| Temps | 40 |
| Mémoire | 40 |
| Qualité du chemin | 20 |
| Nœuds développés | 0 |

```text
score = somme(poids × sous-score) / somme(poids)
```

La moyenne finale inclut toutes les cartes, donc les échecs. Les coefficients
peuvent être modifiés : par exemple `temps=1, mémoire=0, qualité=0, nœuds=0`
classe uniquement la vitesse, en privilégiant toujours le taux de réussite.
Au moins un coefficient doit être strictement positif. Avec les poids par défaut,
**Dijkstra obtient 60/100** sur des cartes accessibles (50 temps, 50 mémoire,
100 qualité). Le score 100 n’est pas un rang : il représente la borne supérieure
du compromis choisi.

Le classement **« Quels algorithmes sont les plus efficaces ? »** montre la
meilleure configuration entièrement évaluée de chaque algorithme, choisie selon
la réussite puis le score. Il inclut les mesures brutes et les sous-scores.
Il compare les configurations testées sur ces cartes, et non une supériorité
générale de l’algorithme sur tous les problèmes. Pendant l’expérience, le
classement est provisoire.

Après la fin ou l’annulation, **Recalculer les scores existants** applique les
nouvelles pondérations aux mesures sauvegardées sans lancer de nouveau benchmark.
Le classement, les courbes, les tableaux et les exports sont actualisés.

La synthèse d’une méthode donne les configurations entièrement évaluées,
le nombre réel d’évaluations (une configuration sur une carte) et le temps de
recherche cumulé (somme des moyennes lissées) et le temps total des benchmarks, qui inclut
l’échauffement, les répétitions et la mesure mémoire. Ces totaux par méthode
n’incluent pas la référence Dijkstra. La progression
globale et le temps écoulé incluent la référence et la préparation des cartes.
Le graphique affiche par défaut le **score global en fonction du poids d’heuristique w** :
abscisse = poids testé, ordonnée = score moyen sur les cartes, une couleur par
heuristique et des marqueurs distincts pour Grid Search et Random Search. Les
points sont reliés par poids croissant au sein de chaque heuristique et méthode ;
les segments servent de guide visuel, sans représenter de nouvelles évaluations.
La notation `f(w)` du graphique désigne la métrique mesurée pour le réglage w,
tandis que `g + w × h` est le score interne d’A*. Une ligne de référence affiche
la valeur de Dijkstra pour la métrique sélectionnée.
On peut choisir une autre métrique (coût, mémoire, temps, sous-scores, etc.), revenir au
**résultat de chaque essai** ou afficher le **meilleur jusque-là**
pour cette métrique, en privilégiant d’abord la réussite. Cette dernière vue
reste naturellement plate si le premier réglage atteint déjà la meilleure valeur.
L’échelle verticale est ajustée aux valeurs observées ; un message signale les
valeurs identiques. Les marqueurs distincts restent identifiables quand les deux
méthodes se superposent, et leur survol affiche les paramètres de la configuration.
Pour comparer les méthodes sur un
même espace discret, le budget Random Search peut être fixé au nombre de
combinaisons Grid Search ; un budget plus faible permet d’étudier le compromis
entre qualité et nombre d’essais.

Avec les déplacements diagonaux, L∞ et `w ≤ 1` garantissent une heuristique
admissible. Les autres réglages peuvent sacrifier le coût du chemin pour réduire
les expansions. Les temps très courts sont sensibles au bruit de mesure : la
graine reproduit les configurations et les cartes, pas les durées.

## Progression, annulation et exports

Une seule expérience s’exécute à la fois. **Annuler** termine l’évaluation de
carte en cours, puis arrête la suite. Les évaluations déjà calculées restent
exportables ; une configuration partiellement évaluée n’entre pas dans les
moyennes comparatives. L’actualisation du navigateur récupère l’expérience en
cours ou terminée.

L’expérience la plus récente est conservée **en mémoire uniquement**. Un nouvel
essai la remplace et un redémarrage du service Agent l’efface.

- **CSV** : une ligne par évaluation, avec méthode, paramètres, index de carte
  (à partir de zéro), succès, métriques brutes, sous-scores, score global,
  durée totale du benchmark et PID du worker.
- **JSON** : configuration, cartes, évaluations détaillées, moyennes,
  synthèses par méthode et courbes. Les lectures de progression excluent les
  cartes et les évaluations détaillées afin de limiter les transferts.

## API Agent

Préfixe dans le navigateur : `/api/agent` ; en local direct : `http://localhost:8001`.

| Méthode | Route | Fonction |
| --- | --- | --- |
| POST | `/experiments` | Valider et lancer une expérience |
| GET | `/experiments` | État courant, ou `null` avant la première expérience |
| POST | `/experiments/cancel` | Annuler et récupérer l’état |
| POST | `/experiments/scoring` | Recalculer les scores avec de nouvelles pondérations après la fin |
| GET | `/experiments/export?format=json` | Export complet |
| GET | `/experiments/export?format=csv` | Export des évaluations |

Exemple de lancement sans carte préparée :

```sh
curl -X POST http://localhost:8001/experiments \
  -H 'Content-Type: application/json' \
  -d '{"algorithms":["astar","dijkstra"],"methods":["grid","random"],"heuristics":["linf","l1"],"weight_space":"range","weight_start":1,"weight_end":50,"weight_step":1,"random_trials":20,"seed":42,"map_source":"random","map_count":10,"size":10,"obstacle_density":0.2,"cell_weight_min":1,"cell_weight_max":9,"objective":"score","score_weights":{"time":40,"memory":40,"quality":20,"expanded":0},"timing_repeats":3}'
```

Pour recalculer uniquement avec le temps comme critère :

```sh
curl -X POST http://localhost:8001/experiments/scoring \
  -H 'Content-Type: application/json' \
  -d '{"time":1,"memory":0,"quality":0,"expanded":0}'
```

Le modèle de requête complet est décrit dans le Swagger du service Agent
(`/docs`). Le moteur se trouve dans `agent/experiments.py` et réutilise
`agent/registry.py`, `RunGraph` et les implémentations d’algorithmes existantes.

## Vérification

Depuis la racine, avec les dépendances Python installées :

```sh
python -m unittest agent.test_experiments environment.test_grid environment.test_api environment.test_simulation -v
```

Depuis `control-panel/` : `npm run build`.
Après modification du contrat gRPC, reconstruire les services Environment et
Agent ensemble (`docker compose up -d --build`).
