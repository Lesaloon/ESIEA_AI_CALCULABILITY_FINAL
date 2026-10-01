"""HTTP contracts for weight editing and reset behavior."""

import unittest

from fastapi.testclient import TestClient

from environment.api import app


class WeightApiTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def test_single_bulk_and_reset_weights(self):
        response = self.client.post('/grid/weights/1/2', json={'weight': 7})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['weights'][2][1], 7)
        self.client.post('/grid/obstacles/1/2')
        response = self.client.post('/grid/weights', json={'weight': 4})
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.json()['weights'][2][1])
        self.assertEqual(response.json()['weights'][0][0], 4)
        self.client.delete('/grid/obstacles/1/2')
        self.assertEqual(self.client.get('/grid/render').json()['weights'][2][1], 7)
        self.client.post('/grid/obstacles/1/2')
        response = self.client.post('/grid/weights/reset')
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['cells'][2][1], 'obstacle')
        self.assertEqual(response.json()['weights'][0][0], 1)
        self.client.delete('/grid/obstacles/1/2')
        self.assertEqual(self.client.get('/grid/render').json()['weights'][2][1], 1)

    def test_invalid_weights_and_cells_do_not_mutate_grid(self):
        self.client.post('/grid/obstacles/1/2')
        before = self.client.get('/grid/render').json()
        for route in ('/grid/weights', '/grid/weights/0/0'):
            for weight in (0, 10, 2.5, 3.0, True, '3', None):
                with self.subTest(route=route, weight=weight):
                    self.assertEqual(self.client.post(route, json={'weight': weight}).status_code, 422)
            self.assertEqual(self.client.post(route, json={}).status_code, 422)
        for coordinates, status in (('1/2', 409), ('-1/0', 404), ('10/0', 404), ('0/10', 404)):
            with self.subTest(coordinates=coordinates):
                response = self.client.post(f'/grid/weights/{coordinates}', json={'weight': 5})
                self.assertEqual(response.status_code, status)
        self.assertEqual(self.client.get('/grid/render').json(), before)

    def test_grid_reset_and_resize_clear_weights(self):
        for route, body, size in (('/grid/reset', {}, 10), ('/grid/resize', {'size': 3}, 3)):
            with self.subTest(route=route):
                self.client.post('/grid/weights', json={'weight': 9})
                self.client.post('/grid/obstacles/0/0')
                response = self.client.post(route, json=body)
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.json()['weights'], [[1] * size for _ in range(size)])
                self.assertEqual(response.json()['cells'], [['empty'] * size for _ in range(size)])

    def test_stroke_updates_multiple_cells_atomically(self):
        cells = [{'x': x, 'y': 2} for x in range(4)]
        response = self.client.post('/grid/weights/stroke', json={'cells': cells, 'weight': 6})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['weights'][2][:5], [6, 6, 6, 6, 1])
        self.client.post('/grid/obstacles/3/2')
        before = self.client.get('/grid/render').json()
        for invalid, status in (({'x': 3, 'y': 2}, 409), ({'x': 10, 'y': 0}, 404)):
            response = self.client.post('/grid/weights/stroke', json={
                'cells': [{'x': 0, 'y': 0}, invalid], 'weight': 9,
            })
            self.assertEqual(response.status_code, status)
            self.assertEqual(self.client.get('/grid/render').json(), before)

    def test_stroke_payload_validation(self):
        for cells, weight in (([], 3), ([{'x': 0, 'y': 0}] * 401, 3),
                              ([{'x': 0.5, 'y': 0}], 3), ([{'x': 0, 'y': 0}], 10)):
            with self.subTest(cells=len(cells), weight=weight):
                response = self.client.post('/grid/weights/stroke', json={'cells': cells, 'weight': weight})
                self.assertEqual(response.status_code, 422)


class ObstacleStrokeApiTests(unittest.TestCase):
    def setUp(self):
        self.client = self.enterContext(TestClient(app))

    def test_paint_erase_and_repeated_cells_preserve_weights_and_topology(self):
        self.client.post('/grid/weights/1/0', json={'weight': 7})
        original = self.client.get('/grid/render').json()
        original_edges = {frozenset(edge) for edge in app.state.grid.graph.edges}
        self.client.post('/grid/obstacles/2/0')
        cells = [{'x': x, 'y': 0} for x in (0, 1, 2, 1, 0)]
        for _ in range(2):
            response = self.client.post('/grid/obstacles/stroke', json={'cells': cells, 'obstacle': True})
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json()['cells'][0][:4], ['obstacle'] * 3 + ['empty'])
            self.assertEqual(response.json()['weights'][0][:3], [None] * 3)
        for _ in range(2):
            response = self.client.post('/grid/obstacles/stroke', json={
                'cells': cells + [{'x': 3, 'y': 0}], 'obstacle': False,
            })
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.json(), original)
            self.assertEqual({frozenset(edge) for edge in app.state.grid.graph.edges}, original_edges)

    def test_invalid_strokes_do_not_partially_change_grid(self):
        self.client.post('/grid/obstacles/0/0')
        before = self.client.get('/grid/render').json()
        for obstacle in (True, False):
            for invalid in ({'x': -1, 'y': 0}, {'x': 10, 'y': 0}, {'x': 0, 'y': 10}):
                response = self.client.post('/grid/obstacles/stroke', json={
                    'obstacle': obstacle, 'cells': [{'x': 0, 'y': 0}, {'x': 1, 'y': 0}, invalid],
                })
                self.assertEqual(response.status_code, 404)
                self.assertEqual(self.client.get('/grid/render').json(), before)
        for body in (
            {'cells': [], 'obstacle': True},
            {'cells': [{'x': 0, 'y': 0}] * 401, 'obstacle': True},
            {'cells': [{'x': 0.5, 'y': 0}], 'obstacle': True},
            {'cells': [{'x': 0, 'y': 0}], 'obstacle': 'true'},
            {'cells': [{'x': 0, 'y': 0}]},
        ):
            self.assertEqual(self.client.post('/grid/obstacles/stroke', json=body).status_code, 422)
            self.assertEqual(self.client.get('/grid/render').json(), before)


if __name__ == '__main__':
    unittest.main()
