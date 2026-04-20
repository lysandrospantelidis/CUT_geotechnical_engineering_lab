from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Node:
    id: int
    x: float
    f_table: list[int] = field(default_factory=list)
    F: list[float] = field(default_factory=list)
    u: list[float] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.f_table:
            self.f_table = [2 * (self.id - 1), 2 * (self.id - 1) + 1]
        if not self.F:
            self.F = [0.0, 0.0]
        if not self.u:
            self.u = [0.0, 0.0]

    def set_load(self, V: float, M: float) -> None:
        self.F = [V, M]

    def update(self, X: list[float]) -> None:
        self.u[0] = float(X[self.f_table[0]])
        self.u[1] = float(X[self.f_table[1]])

    def clear(self) -> None:
        self.u = [0.0, 0.0]

    def to_xml(self) -> str:
        return (
            "\t<node>\n"
            f"\t\t<id>{self.id}</id>\n"
            f"\t\t<x>{self.x}</x>\n"
            f"\t\t<u>{self.u[0]} {self.u[1]}</u>\n"
            f"\t\t<fTable>{self.f_table[0]} {self.f_table[1]}</fTable>\n"
            f"\t\t<F>{self.F[0]} {self.F[1]}</F>\n"
            "\t</node>\n"
        )
