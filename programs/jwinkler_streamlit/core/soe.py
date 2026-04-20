from __future__ import annotations

import numpy as np


class Soe:
    def __init__(self) -> None:
        self.A = np.zeros((0, 0), dtype=float)
        self.B = np.zeros(0, dtype=float)
        self.X = np.zeros(0, dtype=float)

    def init(self, n: int) -> None:
        self.A = np.zeros((n, n), dtype=float)
        self.B = np.zeros(n, dtype=float)
        self.X = np.zeros(n, dtype=float)

    def add_matrix(self, m: np.ndarray, f_table: list[int]) -> None:
        for i in range(4):
            for j in range(4):
                self.A[f_table[i], f_table[j]] += m[i, j]

    def add_vector(self, v: np.ndarray | list[float], f_table: list[int]) -> None:
        for i, idx in enumerate(f_table):
            self.B[idx] += float(v[i])

    def solve(self) -> None:
        self.X = np.linalg.solve(self.A, self.B)
