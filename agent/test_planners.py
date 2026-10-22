import random
import unittest

from agent.models import DiscoveredGraphView
from agent.planners.template import AStarPlanner, DijkstraPlanner


def path_cost(graph, path):
    return sum(graph.edges[a][b] for a, b in zip(path, path[1:]))


def make_graph(edges):
    nodes = set(edges) | {d for out in edges.values() for d in out}
    return DiscoveredGraphView(edges={n: dict(edges.get(n, {})) for n in nodes},
                               weights={n: 1 for n in nodes}, visited=frozenset())


def planners():
    return [DijkstraPlanner(), AStarPlanner('zero'), AStarPlanner('l1'),
            AStarPlanner('l2'), AStarPlanner('linf')]


class PlannerTests(unittest.TestCase):
    def test_detour_cheaper_than_direct(self):
        g = make_graph({(0, 0): {(1, 0): 10, (0, 1): 1},
                        (0, 1): {(1, 1): 1}, (1, 1): {(1, 0): 1}})
        for p in planners():
            path = p.plan(g, (0, 0), (1, 0)).path
            self.assertEqual(path, [(0, 0), (0, 1), (1, 1), (1, 0)])
            self.assertEqual(path_cost(g, path), 3)

    def test_directional_costs(self):
        g = make_graph({(0, 0): {(1, 0): 1, (0, 1): 5}, (1, 0): {(0, 0): 9, (1, 1): 1},
                        (0, 1): {(0, 0): 1, (1, 1): 1}, (1, 1): {(1, 0): 1, (0, 1): 1}})
        for p in planners():
            self.assertEqual(path_cost(g, p.plan(g, (0, 0), (0, 1)).path), 3)
            self.assertEqual(path_cost(g, p.plan(g, (0, 1), (1, 0)).path), 2)

    def test_start_equals_target_and_unreachable(self):
        g = make_graph({(0, 0): {(1, 0): 1}, (5, 5): {}})
        for p in planners():
            self.assertEqual(p.plan(g, (0, 0), (0, 0)).path, [(0, 0)])
            self.assertEqual(p.plan(g, (0, 0), (5, 5)).path, [])
            self.assertEqual(p.plan(g, (0, 0), (9, 9)).path, [])

    def test_improved_cost_of_discovered_node(self):
        # B is first seen at cost 10, then improved to 3 through C and D.
        a, b, c, d = (0, 0), (9, 9), (0, 1), (0, 2)
        g = make_graph({a: {b: 10, c: 1}, c: {d: 1}, d: {b: 1}})
        for p in (DijkstraPlanner(), AStarPlanner('zero')):
            self.assertEqual(p.plan(g, a, b).path, [a, c, d, b])

    def test_deterministic(self):
        g = make_graph({(0, 0): {(1, 0): 1, (0, 1): 1}, (1, 0): {(1, 1): 1}, (0, 1): {(1, 1): 1}})
        first = DijkstraPlanner().plan(g, (0, 0), (1, 1)).path
        for _ in range(20):
            self.assertEqual(DijkstraPlanner().plan(g, (0, 0), (1, 1)).path, first)

    def test_graph_not_mutated(self):
        g = make_graph({(0, 0): {(1, 0): 2}, (1, 0): {(0, 0): 3}})
        before = {k: dict(v) for k, v in g.edges.items()}
        DijkstraPlanner().plan(g, (0, 0), (1, 0))
        self.assertEqual(g.edges, before)

    def test_against_networkx_oracle(self):
        import networkx as nx
        rng = random.Random(7)
        for _ in range(60):
            size = 6
            edges = {}
            for x in range(size):
                for y in range(size):
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        n = (x + dx, y + dy)
                        if 0 <= n[0] < size and 0 <= n[1] < size and rng.random() < 0.8:
                            edges.setdefault((x, y), {})[n] = rng.randint(1, 9)
            g = make_graph(edges)
            start = (rng.randrange(size), rng.randrange(size))
            target = (rng.randrange(size), rng.randrange(size))
            digraph = nx.DiGraph()
            digraph.add_nodes_from(g.edges)
            for s, out in g.edges.items():
                for d, w in out.items():
                    digraph.add_edge(s, d, weight=w)
            try:
                expected = nx.shortest_path_length(digraph, start, target, weight='weight')
            except nx.NetworkXNoPath:
                expected = None
            for p in planners():  # all admissible with min cost 1
                path = p.plan(g, start, target).path
                if expected is None:
                    self.assertEqual(path, [])
                else:
                    self.assertEqual(path[0], start)
                    self.assertEqual(path[-1], target)
                    self.assertEqual(path_cost(g, path), expected)


if __name__ == '__main__':
    unittest.main()
