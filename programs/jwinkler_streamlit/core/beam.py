from __future__ import annotations

from dataclasses import dataclass, field
import math
import numpy as np

from .materials import MaterialBeam, MaterialSoil
from .node import Node
from .sections import Section


@dataclass
class Beam:
    id: int
    n1: Node
    n2: Node
    beam_mat: MaterialBeam
    soil_mat: MaterialSoil
    sec: Section
    f_table: list[int] = field(default_factory=list)
    Fext: list[float] = field(default_factory=list)
    Fint: list[float] = field(default_factory=list)
    NUM_OF_SEGS: int = 30

    def __post_init__(self) -> None:
        self.f_table = self.f_table or [self.n1.f_table[0], self.n1.f_table[1], self.n2.f_table[0], self.n2.f_table[1]]
        self.Fext = self.Fext or [0.0, 0.0]
        self.Fint = self.Fint or [0.0, 0.0, 0.0, 0.0]
        self.L = self.n2.x - self.n1.x

    def set_beam_sec(self, sec: Section) -> None:
        self.sec = sec

    def set_load(self, pA: float, pB: float) -> None:
        self.Fext = [pA, pB]

    def get_F(self) -> np.ndarray:
        A = self.sec.A
        Au = self.sec.Au
        gamma_soil = self.soil_mat.gamma
        gamma_conc = self.beam_mat.gamma
        p = self.L * (A * gamma_conc + Au * gamma_soil)
        pA = self.Fext[0] + p
        pB = self.Fext[1] + p
        return np.array([
            +self.L / 60.0 * (21.0 * pA + 9.0 * pB),
            +self.L / 60.0 * (3.0 * pA + 2.0 * pB) * self.L,
            +self.L / 60.0 * (9.0 * pA + 21.0 * pB),
            -self.L / 60.0 * (2.0 * pA + 3.0 * pB) * self.L,
        ], dtype=float)

    def get_x(self) -> np.ndarray:
        return np.linspace(self.n1.x, self.n2.x, self.NUM_OF_SEGS + 1)

    def get_u(self) -> np.ndarray:
        X = self.get_x()
        u1, u2 = self.n1.u
        u3, u4 = self.n2.u
        Y = np.zeros_like(X)
        for i, xg in enumerate(X):
            x = xg - X[0]
            N1 = 1 - 3 * x * x / (self.L * self.L) + 2 * (x**3) / (self.L**3)
            N2 = x - 2 * x * x / self.L + (x**3) / (self.L * self.L)
            N3 = 3 * x * x / (self.L * self.L) - 2.0 * (x**3) / (self.L**3)
            N4 = -x * x / self.L + (x**3) / (self.L * self.L)
            Y[i] = N1 * u1 + N2 * u2 + N3 * u3 + N4 * u4
        return Y

    def get_m(self) -> np.ndarray:
        MA = +self.Fint[1]
        MB = -self.Fint[3]
        return np.linspace(MA, MB, self.NUM_OF_SEGS + 1)

    def get_v(self) -> np.ndarray:
        VA = -self.Fint[0]
        VB = +self.Fint[2]
        return np.linspace(VA, VB, self.NUM_OF_SEGS + 1)

    def get_p(self) -> np.ndarray:
        Y = self.get_u().copy()
        Ks = self.soil_mat.Ks * self.sec.b
        return Y * Ks

    def get_k(self) -> np.ndarray:
        E = self.beam_mat.E
        I = self.sec.I
        Ks = self.soil_mat.Ks * self.sec.b
        lam = self.L * (Ks / (4.0 * E * I)) ** 0.25
        sn = math.sin(lam)
        cs = math.cos(lam)
        sh = math.sinh(lam)
        ch = math.cosh(lam)
        dl = lam / self.L
        a1 = sn * cs - sh * ch
        a2 = -2 * dl * dl * (sn * cs + sh * ch)
        a3 = sh * cs - ch * sn
        a4 = dl * (sn * sn + sh * sh)
        a5 = 2 * dl * (sn * sh)
        a6 = 2 * dl * dl * (sh * cs + ch * sn)
        K0 = 2 * E * I * lam / (self.L * (sn * sn - sh * sh))
        K = np.zeros((4, 4), dtype=float)
        K[0, 0] = +K0 * a2
        K[0, 1] = -K0 * a4
        K[0, 2] = +K0 * a6
        K[0, 3] = -K0 * a5
        K[1, 0] = -K0 * a4
        K[1, 1] = +K0 * a1
        K[1, 2] = +K0 * a5
        K[1, 3] = +K0 * a3
        K[2, 0] = +K0 * a6
        K[2, 1] = +K0 * a5
        K[2, 2] = +K0 * a2
        K[2, 3] = +K0 * a4
        K[3, 0] = -K0 * a5
        K[3, 1] = +K0 * a3
        K[3, 2] = +K0 * a4
        K[3, 3] = +K0 * a1
        return K

    def update(self) -> None:
        KL = self.get_k()
        F = self.get_F()
        u1, u2 = self.n1.u
        u3, u4 = self.n2.u
        self.Fint = [
            float(KL[0, 0] * u1 + KL[0, 1] * u2 + KL[0, 2] * u3 + KL[0, 3] * u4 - F[0]),
            float(KL[1, 0] * u1 + KL[1, 1] * u2 + KL[1, 2] * u3 + KL[1, 3] * u4 - F[1]),
            float(KL[2, 0] * u1 + KL[2, 1] * u2 + KL[2, 2] * u3 + KL[2, 3] * u4 - F[2]),
            float(KL[3, 0] * u1 + KL[3, 1] * u2 + KL[3, 2] * u3 + KL[3, 3] * u4 - F[3]),
        ]

    def clear(self) -> None:
        self.Fint = [0.0, 0.0, 0.0, 0.0]

    def to_xml(self) -> str:
        return (
            "\t<beam>\n"
            f"\t\t<id>{self.id}</id>\n"
            f"\t\t<n1>{self.n1.id}</n1>\n"
            f"\t\t<n2>{self.n2.id}</n2>\n"
            f"\t\t<L>{self.L}</L>\n"
            f"\t\t<fTable>{' '.join(map(str, self.f_table))} </fTable>\n"
            f"\t\t<Fext>{self.Fext[0]} {self.Fext[1]}</Fext>\n"
            f"\t\t<Fint>{self.Fint[0]} {self.Fint[1]} {self.Fint[2]} {self.Fint[3]}</Fint>\n"
            "\t</beam>\n"
        )
