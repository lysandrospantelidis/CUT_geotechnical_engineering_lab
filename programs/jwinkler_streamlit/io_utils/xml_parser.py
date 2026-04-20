from __future__ import annotations

import xml.etree.ElementTree as ET

from core.beam import Beam
from core.domain import Domain
from core.node import Node
from core.sections import SectionRectangle, SectionTrapezoidal, SectionUser


class XMLParser:
    @staticmethod
    def _txt(parent: ET.Element, name: str, default: str = "") -> str:
        child = parent.find(name)
        return child.text.strip() if child is not None and child.text else default

    @staticmethod
    def _flt(parent: ET.Element, name: str, default: float = 0.0) -> float:
        txt = XMLParser._txt(parent, name, "")
        return float(txt) if txt else default

    @staticmethod
    def _int(parent: ET.Element, name: str, default: int = 0) -> int:
        txt = XMLParser._txt(parent, name, "")
        return int(txt) if txt else default

    @staticmethod
    def _int_array(parent: ET.Element, name: str) -> list[int]:
        txt = XMLParser._txt(parent, name, "")
        return [int(v) for v in txt.split()] if txt else []

    @staticmethod
    def _float_array(parent: ET.Element, name: str) -> list[float]:
        txt = XMLParser._txt(parent, name, "")
        return [float(v) for v in txt.split()] if txt else []

    def parse(self, domain: Domain, file_path: str) -> None:
        tree = ET.parse(file_path)
        root = tree.getroot()
        domain.reset()

        settings = root.find("settings")
        if settings is not None:
            domain.project = self._txt(settings, "project")
            domain.user = self._txt(settings, "user")
            domain.comments = self._txt(settings, "comments")

        soil = root.find("soil")
        if soil is not None:
            domain.set_soil_mat(self._flt(soil, "gamma", 18.0), self._flt(soil, "Ks", 28000.0))

        concrete = root.find("concrete")
        if concrete is not None:
            domain.set_beam_mat(self._flt(concrete, "gamma", 20.0), self._flt(concrete, "E", 21_000_000.0), self._flt(concrete, "nu", 0.15))

        sec = root.find("section_trpz")
        if sec is not None:
            domain.set_beam_sec(SectionTrapezoidal(
                self._flt(sec, "b"), self._flt(sec, "h"), self._flt(sec, "b0"),
                self._flt(sec, "h0"), self._flt(sec, "h1"), self._flt(sec, "h2")
            ))
        sec = root.find("section_rect")
        if sec is not None:
            domain.set_beam_sec(SectionRectangle(
                self._flt(sec, "b"), self._flt(sec, "h"), self._flt(sec, "b0"),
                self._flt(sec, "h0"), self._flt(sec, "h1")
            ))
        sec = root.find("section_user")
        if sec is not None:
            domain.set_beam_sec(SectionUser(
                self._flt(sec, "b"), self._flt(sec, "h"), self._flt(sec, "A"), self._flt(sec, "I")
            ))

        for node_el in root.findall("node"):
            node = Node(
                id=self._int(node_el, "id"),
                x=self._flt(node_el, "x"),
                f_table=self._int_array(node_el, "fTable"),
                F=self._float_array(node_el, "F"),
                u=self._float_array(node_el, "u"),
            )
            domain.add_node(node)

        for beam_el in root.findall("beam"):
            n1 = domain.nodes[self._int(beam_el, "n1") - 1]
            n2 = domain.nodes[self._int(beam_el, "n2") - 1]
            beam = Beam(
                id=self._int(beam_el, "id"),
                n1=n1,
                n2=n2,
                beam_mat=domain.beam_mat,
                soil_mat=domain.soil_mat,
                sec=domain.beam_sec,
                f_table=self._int_array(beam_el, "fTable"),
                Fext=self._float_array(beam_el, "Fext"),
                Fint=self._float_array(beam_el, "Fint"),
            )
            domain.add_beam(beam)

    def save(self, domain: Domain, file_path: str) -> None:
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(domain.to_xml())
