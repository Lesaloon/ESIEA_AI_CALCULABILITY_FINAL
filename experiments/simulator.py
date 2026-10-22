"""Mini-environnement local : mêmes règles que environment/simulation.py."""

from dataclasses import dataclass
import random         

FOUR = ((1, 0), (-1, 0), (0, 1), (0, -1))
EIGHT = FOUR + ((1, 1), (1, -1), (-1, 1), (-1, -1))


@dataclass
class Scenario:
    name: str
    size: int
    start: tuple
    goal: tuple
    obstacles: frozenset
    weights: dict
    connectivity: int = 4

    def walkable(self, p):
        """Vrai si p est dans la grille ET n'est pas un obstacle."""
        x, y = p
        return 0 <= x < self.size and 0 <= y < self.size and p not in self.obstacles

    def neighbors(self, p):
        """Les voisins praticables de p, triés (pour que les résultats soient reproductibles)."""
        directions = FOUR if self.connectivity == 4 else EIGHT
        result = []
        for dx, dy in directions:
            q = (p[0] + dx, p[1] + dy)
            if self.walkable(q):
                result.append(q)
        return sorted(result)

    def render(self):
        """Grille en texte : S départ, G but, # obstacle, sinon le poids de la case."""
        rows = []
        for y in range(self.size):
            row = []
            for x in range(self.size):
                p = (x, y)
                if p == self.start:
                    row.append('S')
                elif p == self.goal:
                    row.append('G')
                elif p in self.obstacles:
                    row.append('#')
                else:
                    row.append(str(self.weights[p]))
            rows.append(' '.join(row))
        return '\n'.join(rows)


def make_scenario(kind, size=20, weights='random', seed=0, connectivity=4):
    """kind : 'open' (vide), 'u' (piège en U), 'wall' (ligne verticale avec un passage en bas)."""
    if size < 8:
        raise ValueError('size doit être >= 8 pour que le U et le mur tiennent dans la grille')
    m = size // 2
    start, goal = (1, m), (size - 2, m)
    obstacles = set()

    if kind == 'u':
        r = max(2, size // 5)
        bar = m + 1
        obstacles |= {(bar, y) for y in range(m - r, m + r + 1)}          # ← 1)
        for y in (m - r, m + r):
            obstacles |= {(x, y) for x in range(bar - r, bar + 1)}
    elif kind == 'wall':
        obstacles |= {(m, y) for y in range(size - 2)}                     # ← 2)
    elif kind != 'open':
        raise ValueError(f'scénario inconnu : {kind}')

    rng = random.Random(seed)
    cells = [(x, y) for x in range(size) for y in range(size) if (x, y) not in obstacles]
    if weights == 'random':
        w = {c: rng.randint(1, 9) for c in cells}                          # ← 3)
    else:
        w = {c: 1 for c in cells}
    return Scenario(kind, size, start, goal, frozenset(obstacles), w, connectivity)