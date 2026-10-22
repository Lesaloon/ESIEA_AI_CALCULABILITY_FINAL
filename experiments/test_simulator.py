import unittest

from experiments.simulator import Scenario


def empty_grid(size, connectivity, obstacles=()):
    cells = [(x, y) for x in range(size) for y in range(size)]
    return Scenario('test', size, (0, 0), (size - 1, size - 1),
                    frozenset(obstacles), {c: 1 for c in cells}, connectivity)


class SimulatorTests(unittest.TestCase):
    def test_number_of_neighbors(self):
        four, eight = empty_grid(5, 4), empty_grid(5, 8)
        self.assertEqual(len(four.neighbors((0, 0))), 2)    # coin, 4-connexité
        self.assertEqual(len(eight.neighbors((0, 0))), 3)   # coin, 8-connexité
        self.assertEqual(len(four.neighbors((2, 2))), 4)    # milieu, 4-connexité
        self.assertEqual(len(eight.neighbors((2, 2))), 8)   # milieu, 8-connexité

    def test_obstacles_and_borders_are_excluded(self):
        sc = empty_grid(5, 4, obstacles={(1, 0)})
        self.assertEqual(sc.neighbors((0, 0)), [(0, 1)])    # (1,0) bloqué, (-1,0) et (0,-1) hors grille
        self.assertFalse(sc.walkable((-1, 0)))
        self.assertFalse(sc.walkable((5, 0)))               # size=5 → x va de 0 à 4
        self.assertFalse(sc.walkable((1, 0)))


if __name__ == '__main__':
    unittest.main()