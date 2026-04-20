from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class Section:
    b: float
    h: float
    A: float = field(init=False)
    Au: float = field(init=False)
    I: float = field(init=False)
    tag: str = field(init=False, default="")

    def to_xml(self) -> str:
        raise NotImplementedError


@dataclass
class SectionRectangle(Section):
    b0: float
    h0: float
    h1: float

    def __post_init__(self) -> None:
        self.tag = "RECT"
        A1 = self.b * self.h0
        ys1 = 0.5 * self.h0
        I1 = self.b * self.h0**3 / 12.0

        A2 = self.b0 * self.h1
        ys2 = self.h0 + 0.5 * self.h1
        I2 = self.b0 * self.h1**3 / 12.0

        self.A = A1 + A2
        ys = (ys1 * A1 + ys2 * A2) / self.A
        self.I = I1 + (ys - ys1) ** 2 * A1 + I2 + (ys - ys2) ** 2 * A2
        self.Au = self.b * self.h - self.A

    def to_xml(self) -> str:
        return (
            "\t<section_rect>\n"
            f"\t\t<b>{self.b}</b>\n"
            f"\t\t<h>{self.h}</h>\n"
            f"\t\t<b0>{self.b0}</b0>\n"
            f"\t\t<h0>{self.h0}</h0>\n"
            f"\t\t<h1>{self.h1}</h1>\n"
            f"\t\t<A>{self.A}</A>\n"
            f"\t\t<I>{self.I}</I>\n"
            "\t</section_rect>\n"
        )


@dataclass
class SectionTrapezoidal(Section):
    b0: float
    h0: float
    h1: float
    h2: float

    def __post_init__(self) -> None:
        self.tag = "TRPZ"
        # lower rectangle
        A1 = self.b * self.h0
        ys1 = 0.5 * self.h0
        I1 = self.b * self.h0**3 / 12.0
        # middle trapezoid = rectangle + two triangles
        bw = self.b - 2.0 * self.h1 * (self.b - self.b0) / (2.0 * self.h1 + self.h2) if (2.0 * self.h1 + self.h2) != 0 else self.b0
        # exact split matching geometry intent of original section
        # use polygon formula instead for robustness
        pts = [
            (-self.b / 2.0, 0.0),
            (self.b / 2.0, 0.0),
            (self.b / 2.0, self.h0),
            (self.b0 / 2.0, self.h0 + self.h1),
            (self.b0 / 2.0, self.h0 + self.h1 + self.h2),
            (-self.b0 / 2.0, self.h0 + self.h1 + self.h2),
            (-self.b0 / 2.0, self.h0 + self.h1),
            (-self.b / 2.0, self.h0),
        ]
        area2 = 0.0
        cx_num = 0.0
        cy_num = 0.0
        Ixx_num = 0.0
        for i in range(len(pts)):
            x1, y1 = pts[i]
            x2, y2 = pts[(i + 1) % len(pts)]
            cross = x1 * y2 - x2 * y1
            area2 += cross
            cx_num += (x1 + x2) * cross
            cy_num += (y1 + y2) * cross
            Ixx_num += (y1 * y1 + y1 * y2 + y2 * y2) * cross
        A = abs(area2) / 2.0
        cy = abs(cy_num) / (3.0 * abs(area2)) if area2 != 0 else 0.0
        Ixx_origin = abs(Ixx_num) / 12.0
        self.A = A
        self.I = Ixx_origin - A * cy**2
        self.Au = self.b * self.h - self.A

    def to_xml(self) -> str:
        return (
            "\t<section_trpz>\n"
            f"\t\t<b>{self.b}</b>\n"
            f"\t\t<h>{self.h}</h>\n"
            f"\t\t<b0>{self.b0}</b0>\n"
            f"\t\t<h0>{self.h0}</h0>\n"
            f"\t\t<h1>{self.h1}</h1>\n"
            f"\t\t<h2>{self.h2}</h2>\n"
            f"\t\t<A>{self.A}</A>\n"
            f"\t\t<I>{self.I}</I>\n"
            "\t</section_trpz>\n"
        )


@dataclass
class SectionUser(Section):
    user_A: float
    user_I: float

    def __post_init__(self) -> None:
        self.tag = "USER"
        self.A = self.user_A
        self.I = self.user_I
        self.Au = self.b * self.h - self.A

    def to_xml(self) -> str:
        return (
            "\t<section_user>\n"
            f"\t\t<b>{self.b}</b>\n"
            f"\t\t<h>{self.h}</h>\n"
            f"\t\t<A>{self.A}</A>\n"
            f"\t\t<I>{self.I}</I>\n"
            "\t</section_user>\n"
        )
