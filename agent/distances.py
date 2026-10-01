"""Geometric helpers for planners; these do not query the environment."""

from math import sqrt


def distance(a, b, metric='l1'):
    dx, dy = abs(a[0] - b[0]), abs(a[1] - b[1])
    squared = dx * dx + dy * dy
    return {'zero': 0, 'l1': dx + dy, 'l2': sqrt(squared),
            'squared_l2': squared, 'mse': squared / 2, 'linf': max(dx, dy)}[metric]
