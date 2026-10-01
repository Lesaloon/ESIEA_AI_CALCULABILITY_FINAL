import random
import math
import networkx as nx

class GestionnairePoids:
    
    def __init__(self, poids_min: int = 1, poids_max: int = 5):
        self.poids_min = poids_min
        self.poids_max = poids_max

    def appliquer_poids_aleatoires(self, graphe: nx.Graph) -> None:
        for (noeud1, noeud2) in graphe.edges():
            difficulte = random.randint(self.poids_min, self.poids_max)
            
            distance= math.dist(noeud1, noeud2)
            poids_final = difficulte * distance
            graphe.edges[noeud1, noeud2]['weight'] = poids_final
    