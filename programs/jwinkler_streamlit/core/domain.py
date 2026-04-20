from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from .beam import Beam
from .materials import MaterialBeam, MaterialSoil
from .node import Node
from .sections import Section, SectionTrapezoidal
from .soe import Soe


class ResultsType(Enum):
    U = "U"
    V = "V"
    M = "M"
    P = "P"


@dataclass
class Domain:
    nodes: list[Node] = field(default_factory=list)
    beams: list[Beam] = field(default_factory=list)
    soil_mat: MaterialSoil = field(default_factory=lambda: MaterialSoil(18.0, 28_000.0))
    beam_mat: MaterialBeam = field(default_factory=lambda: MaterialBeam(20.0, 21_000_000.0, 0.15))
    beam_sec: Section = field(default_factory=lambda: SectionTrapezoidal(2.0, 2.0, 0.5, 0.5, 0.5, 0.5))
    soe: Soe = field(default_factory=Soe)
    project: str = ""
    user: str = ""
    comments: str = ""
    results_type: ResultsType = ResultsType.U

    def reset(self) -> None:
        self.nodes = []
        self.beams = []
        self.soil_mat = MaterialSoil(18.0, 28_000.0)
        self.beam_mat = MaterialBeam(20.0, 21_000_000.0, 0.15)
        self.beam_sec = SectionTrapezoidal(2.0, 2.0, 0.5, 0.5, 0.5, 0.5)
        self.project = ""
        self.user = ""
        self.comments = ""
        self.results_type = ResultsType.U

    @property
    def L(self) -> float:
        if len(self.nodes) < 2:
            return 0.0
        return self.nodes[-1].x - self.nodes[0].x

    def set_beam_mat(self, gamma: float, E: float, nu: float) -> None:
        self.beam_mat.gamma = gamma
        self.beam_mat.E = E
        self.beam_mat.nu = nu

    def set_soil_mat(self, gamma: float, Ks: float) -> None:
        self.soil_mat.gamma = gamma
        self.soil_mat.Ks = Ks

    def set_beam_sec(self, beam_sec: Section) -> None:
        self.beam_sec = beam_sec
        for beam in self.beams:
            beam.set_beam_sec(beam_sec)

    def set_nodes(self, nodes: list[Node]) -> None:
        self.nodes = nodes
        self.beams = []
        for i in range(len(nodes) - 1):
            self.beams.append(Beam(i + 1, nodes[i], nodes[i + 1], self.beam_mat, self.soil_mat, self.beam_sec))

    def add_node(self, node: Node) -> None:
        self.nodes.append(node)

    def add_beam(self, beam: Beam) -> None:
        self.beams.append(beam)

    def get_x(self, i: int | None = None):
        if i is None:
            return [node.x for node in self.nodes]
        return self.beams[i].get_x()

    def get_y(self, i: int):
        beam = self.beams[i]
        if self.results_type == ResultsType.U:
            return beam.get_u()
        if self.results_type == ResultsType.M:
            return beam.get_m()
        if self.results_type == ResultsType.V:
            return beam.get_v()
        return beam.get_p()

    def get_max_min(self) -> list[float]:
        if not self.beams:
            return [0.0, 0.0, 0.0, 0.0, 0.0]
        ymax = float("-inf")
        xmax = 0.0
        ymin = float("inf")
        xmin = 0.0
        for i in range(len(self.beams)):
            x = self.get_x(i)
            y = self.get_y(i)
            for xx, yy in zip(x, y):
                yy = float(yy)
                xx = float(xx)
                if yy > ymax:
                    ymax = yy
                    xmax = xx
                if yy < ymin:
                    ymin = yy
                    xmin = xx
        maxabs = max(abs(ymax), abs(ymin)) if ymax != float("-inf") and ymin != float("inf") else 0.0
        return [maxabs, ymax if ymax != float("-inf") else 0.0, xmax, ymin if ymin != float("inf") else 0.0, xmin]

    def get_table(self) -> list[list[str]]:
        rows: list[list[str]] = []
        for i, beam in enumerate(self.beams):
            uA = self.nodes[i].u
            uB = self.nodes[i + 1].u
            F = beam.Fint
            rows.append([
                str(i + 1),
                str(i + 1),
                f"{uA[0]:0.8f}",
                f"{uA[1]:0.8f}",
                f"{+F[1]:0.3f}",
                f"{-F[0]:0.3f}",
                f"{self.soil_mat.Ks * uA[0]:0.3f}",
            ])
            rows.append([
                "",
                str(i + 2),
                f"{uB[0]:0.8f}",
                f"{uB[1]:0.8f}",
                f"{-F[3]:0.3f}",
                f"{+F[2]:0.3f}",
                f"{self.soil_mat.Ks * uB[0]:0.3f}",
            ])
        return rows

    def clear(self) -> None:
        for node in self.nodes:
            node.clear()
        for beam in self.beams:
            beam.clear()

    def solve(self) -> None:
        self.soe.init(2 * len(self.nodes))
        for beam in self.beams:
            self.soe.add_matrix(beam.get_k(), beam.f_table)
        for beam in self.beams:
            self.soe.add_vector(beam.get_F(), beam.f_table)
        for node in self.nodes:
            self.soe.add_vector(node.F, node.f_table)
        self.soe.solve()
        X = self.soe.X
        for node in self.nodes:
            node.update(X)
        for beam in self.beams:
            beam.update()

    def to_xml(self) -> str:
        s = '<?xml version="1.0" encoding="UTF-8" ?>\n<jWinkler>\n'
        s += "\t<settings>\n"
        s += f"\t\t<project>{self.project} </project>\n"
        s += f"\t\t<user>{self.user} </user>\n"
        s += f"\t\t<comments>{self.comments} </comments>\n"
        s += "\t</settings>\n"
        s += self.soil_mat.to_xml()
        s += self.beam_mat.to_xml()
        s += self.beam_sec.to_xml()
        for node in self.nodes:
            s += node.to_xml()
        for beam in self.beams:
            s += beam.to_xml()
        s += "</jWinkler>\n"
        return s
