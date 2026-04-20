from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Material:
    gamma: float = 0.0


@dataclass
class MaterialBeam(Material):
    E: float = 21_000_000.0
    nu: float = 0.15

    def to_xml(self) -> str:
        return (
            "\t<concrete>\n"
            f"\t\t<E>{self.E}</E>\n"
            f"\t\t<nu>{self.nu}</nu>\n"
            f"\t\t<gamma>{self.gamma}</gamma>\n"
            "\t</concrete>\n"
        )


@dataclass
class MaterialSoil(Material):
    Ks: float = 28_000.0

    def to_xml(self) -> str:
        return (
            "\t<soil>\n"
            f"\t\t<Ks>{self.Ks}</Ks>\n"
            f"\t\t<gamma>{self.gamma}</gamma>\n"
            "\t</soil>\n"
        )
