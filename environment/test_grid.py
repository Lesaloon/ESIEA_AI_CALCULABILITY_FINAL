"""Graph invariants when manually blocking and restoring cells."""

import unittest

from environment.grid import Grid


class GridRestorationTests(unittest.TestCase):
    def test_restores_original_topology_and_weight(self):
        grid = Grid(3, 3)
        original_edges = {frozenset(edge) for edge in grid.graph.edges}
        grid.graph.nodes[1, 1]["weight"] = 3.5
        grid.remove_node((1, 1))
        grid.add_node((1, 1))
        self.assertEqual(grid.graph.nodes[1, 1]["weight"], 3.5)
        self.assertEqual({frozenset(edge) for edge in grid.graph.edges}, original_edges)

    def test_does_not_restore_adjacent_obstacles(self):
        grid = Grid(3, 3)
        grid.remove_node((1, 1))
        grid.remove_node((1, 0))
        grid.add_node((1, 1))
        self.assertFalse(grid.is_walkable((1, 0)))
        self.assertEqual(set(grid.neighbors((1, 1))), {(0, 1), (2, 1), (1, 2)})
        grid.add_node((1, 0))
        self.assertTrue(grid.graph.has_edge((1, 0), (1, 1)))
        self.assertEqual(grid.graph.number_of_edges(), 12)

    def test_corners_and_invalid_restorations(self):
        grid = Grid(3, 3)
        grid.remove_node((0, 0))
        grid.add_node((0, 0))
        self.assertEqual(set(grid.neighbors((0, 0))), {(1, 0), (0, 1)})
        for node in ((0, 0), (-1, 0), (3, 0), (0, 3)):
            with self.subTest(node=node), self.assertRaises(ValueError):
                grid.add_node(node)
        self.assertEqual(grid.graph.number_of_nodes(), 9)

    def test_default_weight_survives_repeated_toggles(self):
        grid = Grid(1, 1)
        for _ in range(3):
            self.assertEqual(grid.graph.nodes[0, 0]["weight"], 1)
            grid.remove_node((0, 0))
            grid.add_node((0, 0))
        self.assertEqual(grid.graph.number_of_edges(), 0)


class GridWeightTests(unittest.TestCase):
    def test_weight_updates_preserve_topology_and_saved_weights(self):
        grid = Grid(3, 3)
        grid.set_weight((1, 1), 7)
        grid.remove_node((1, 1))
        edges = set(grid.graph.edges)
        grid.set_all_weights(4)
        self.assertEqual(set(grid.graph.edges), edges)
        self.assertTrue(all(data['weight'] == 4 for _, data in grid.graph.nodes(data=True)))
        grid.add_node((1, 1))
        self.assertEqual(grid.graph.nodes[1, 1]['weight'], 7)

    def test_reset_includes_obstacles_without_unblocking_them(self):
        grid = Grid(3, 3)
        grid.set_all_weights(9)
        grid.remove_node((1, 1))
        edges = set(grid.graph.edges)
        grid.reset_weights()
        self.assertFalse(grid.is_walkable((1, 1)))
        self.assertEqual(set(grid.graph.edges), edges)
        grid.add_node((1, 1))
        self.assertTrue(all(data['weight'] == 1 for _, data in grid.graph.nodes(data=True)))

    def test_invalid_edits_leave_grid_unchanged(self):
        grid = Grid(3, 3)
        for weight in (0, 10, 1.5, 3.0, True, '3', None):
            for operation in (lambda value: grid.set_weight((0, 0), value), grid.set_all_weights):
                with self.subTest(weight=weight), self.assertRaises(ValueError):
                    operation(weight)
        grid.remove_node((1, 1))
        for node in ((1, 1), (-1, 0), (3, 0), (0, 3)):
            with self.subTest(node=node), self.assertRaises(ValueError):
                grid.set_weight(node, 3)
        self.assertEqual(grid.graph.number_of_nodes(), 8)
        self.assertTrue(all(data['weight'] == 1 for _, data in grid.graph.nodes(data=True)))


if __name__ == "__main__":
    unittest.main()
