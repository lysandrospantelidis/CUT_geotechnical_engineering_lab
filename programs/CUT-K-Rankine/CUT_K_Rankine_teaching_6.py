#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CUT_K_Rankine
v6
Dr Lysandros Pantelidis, Cyprus University of Technology

Direct application of the Rankine earth-pressure coefficient formulas
for Ka and Kp as functions of soil friction angle φ and backfill angle β.

This GUI preserves the layout spirit of the original CUT_K_Coulomb app,
while replacing the Coulomb-specific inputs with the directly applicable
Rankine variables only.
"""

import math
import os
import sys
import subprocess
import tempfile
import urllib.request
import webbrowser
from typing import Optional

import tkinter as tk
from tkinter import ttk, messagebox

from PIL import Image, ImageTk
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

PROGRAM_NAME = "CUT_K_Rankine"
VERSION = "v6"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"
CUT_LOGO_URL = "https://www.cut.ac.cy/digitalAssets/17/17780_100tepak-logo.png"
HOME_URL = "https://cut-apps.streamlit.app/"


TEACHING_IMAGES = [
    "59de0a21-411d-4634-8430-ae247d1c09ff.png",  # RL/Rankine figure
    "4a9c9a89-2087-4314-91b8-900584e99d64.png",  # text excerpt
]


class RankineError(ValueError):
    pass


def script_dir() -> str:
    return os.path.dirname(os.path.abspath(__file__))


def resource_path(name: str) -> str:
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = script_dir()
    return os.path.join(base_path, name)


def find_local_file(name: str) -> Optional[str]:
    candidates = [
        os.path.join(script_dir(), name),
        resource_path(name),
        os.path.join(os.path.abspath("."), name),
        os.path.join("/mnt/data", name),
    ]
    for p in candidates:
        if os.path.exists(p):
            return p
    return None


def load_button_image(path: str, target_w: int, target_h: int):
    img = Image.open(path).convert("RGBA")
    img.thumbnail((target_w, target_h), Image.LANCZOS)

    canvas = Image.new("RGBA", (target_w, target_h), (255, 255, 255, 0))
    x = (target_w - img.width) // 2
    y = (target_h - img.height) // 2
    canvas.paste(img, (x, y), img)
    return ImageTk.PhotoImage(canvas)


def load_home_button_image(path: str, target_size: int, crop_margin_ratio: float = 0.03):
    img = Image.open(path).convert("RGBA")
    w, h = img.size
    dx = int(w * crop_margin_ratio)
    dy = int(h * crop_margin_ratio)

    if w - 2 * dx > 10 and h - 2 * dy > 10:
        img = img.crop((dx, dy, w - dx, h - dy))

    img.thumbnail((target_size, target_size), Image.LANCZOS)

    canvas = Image.new("RGBA", (target_size, target_size), (255, 255, 255, 0))
    x = (target_size - img.width) // 2
    y = (target_size - img.height) // 2
    canvas.paste(img, (x, y), img)
    return ImageTk.PhotoImage(canvas)


def scale_image_for_panel(path: str, max_width: int) -> ImageTk.PhotoImage:
    img = Image.open(path).convert("RGBA")
    if img.width > max_width:
        ratio = max_width / float(img.width)
        new_size = (max_width, max(1, int(img.height * ratio)))
        img = img.resize(new_size, Image.LANCZOS)
    return ImageTk.PhotoImage(img)


def rankine_ka_kp(phi_deg: float, beta_deg: float):
    if not (0.0 < phi_deg < 90.0):
        raise RankineError("φ must be between 0 and 90 degrees.")

    phi = math.radians(phi_deg)
    beta = math.radians(beta_deg)

    cos_beta = math.cos(beta)
    radicand = cos_beta * cos_beta - math.cos(phi) * math.cos(phi)

    # Guard against tiny negative values caused by floating-point rounding.
    if radicand < -1e-12:
        raise RankineError(
            "The expression under the square root becomes negative. "
            "For these formulas, admissible inputs require cos²β ≥ cos²φ."
        )
    radicand = max(0.0, radicand)
    root = math.sqrt(radicand)

    den_ka = cos_beta + root
    den_kp = cos_beta - root
    if abs(den_ka) < 1e-14 or abs(den_kp) < 1e-14:
        raise RankineError("A denominator becomes zero for the selected inputs.")

    ka = cos_beta * (cos_beta - root) / den_ka
    kp = cos_beta * (cos_beta + root) / den_kp
    return ka, kp


class ScrollableFrame(ttk.Frame):
    def __init__(self, master, *args, **kwargs):
        super().__init__(master, *args, **kwargs)
        self.canvas = tk.Canvas(self, highlightthickness=0)
        self.vbar = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        self.inner = ttk.Frame(self.canvas)

        self.inner.bind(
            "<Configure>",
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all"))
        )

        self.window_id = self.canvas.create_window((0, 0), window=self.inner, anchor="nw")
        self.canvas.configure(yscrollcommand=self.vbar.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.vbar.grid(row=0, column=1, sticky="ns")
        self.rowconfigure(0, weight=1)
        self.columnconfigure(0, weight=1)

        self.canvas.bind("<Configure>", self._on_canvas_configure)
        self.canvas.bind_all("<MouseWheel>", self._on_mousewheel)

    def _on_canvas_configure(self, event):
        self.canvas.itemconfigure(self.window_id, width=event.width)

    def _on_mousewheel(self, event):
        if self.winfo_exists():
            self.canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")


class App:
    def __init__(self, root):
        self.root = root
        root.title(PROGRAM_NAME)

        try:
            self.root.state("zoomed")
        except Exception:
            self.root.attributes("-zoomed", True)

        self.root.minsize(1200, 800)

        try:
            ico = find_local_file("cut_logo.ico")
            if ico:
                root.iconbitmap(ico)
        except Exception:
            pass

        style = ttk.Style(root)
        try:
            if style.theme_use() == "classic":
                style.theme_use("default")
        except Exception:
            pass

        style.configure("Result.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Toolbar.TButton", font=("Segoe UI", 9))
        style.configure("TeachTitle.TLabel", font=("Segoe UI", 11, "bold"))
        style.configure("TeachBody.TLabel", font=("Segoe UI", 10), justify="left")

        self._compute_img = None
        self._home_img = None
        self._teaching_images = []

        main = ttk.Frame(root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        left_panel = ttk.Frame(main, width=380)
        left_panel.grid(row=0, column=0, sticky="nsnw", padx=(0, 10))
        left_panel.grid_propagate(False)

        right_panel = ttk.LabelFrame(main, text="Teaching Corner")
        right_panel.grid(row=0, column=1, sticky="nsew")

        main.columnconfigure(0, weight=0)
        main.columnconfigure(1, weight=1)
        main.rowconfigure(0, weight=1)

        left_panel.columnconfigure(0, weight=1)
        left_panel.rowconfigure(2, weight=1)

        toolbar = ttk.Frame(left_panel)
        toolbar.grid(row=0, column=0, sticky="w", pady=(0, 8))
        toolbar.columnconfigure(0, weight=0)
        toolbar.columnconfigure(1, weight=0)
        toolbar.columnconfigure(2, weight=0)
        toolbar.columnconfigure(3, weight=1)  # pushes "About" right

        self.button_img_w = 84
        self.button_img_h = 84
        self.button_size = 84

        compute_added = False
        for name in ["cut_tepak_logo.png", "100tepak-logo.png", "cut_logo.png"]:
            p = find_local_file(name)
            if p:
                try:
                    self._compute_img = load_button_image(p, self.button_img_w, self.button_img_h)
                    ttk.Button(toolbar, image=self._compute_img, command=self.compute).grid(row=0, column=0, padx=(0, 6))
                    compute_added = True
                    break
                except Exception:
                    pass

        if not compute_added:
            try:
                tmp = os.path.join(tempfile.gettempdir(), "cut_tepak_logo.png")
                if not os.path.exists(tmp):
                    urllib.request.urlretrieve(CUT_LOGO_URL, tmp)
                self._compute_img = load_button_image(tmp, self.button_img_w, self.button_img_h)
                ttk.Button(toolbar, image=self._compute_img, command=self.compute).grid(row=0, column=0, padx=(0, 6))
                compute_added = True
            except Exception:
                pass

        if not compute_added:
            ttk.Button(toolbar, text="Compute", command=self.compute).grid(row=0, column=0, padx=(0, 6))

        home_img_path = find_local_file("home.png")
        if home_img_path:
            try:
                self._home_img = load_home_button_image(home_img_path, self.button_size)
                ttk.Button(toolbar, image=self._home_img, command=self.open_home).grid(row=0, column=2, padx=6)
            except Exception:
                ttk.Button(toolbar, text="Home", command=self.open_home, style="Toolbar.TButton").grid(row=0, column=2, padx=6)
        else:
            ttk.Button(toolbar, text="Home", command=self.open_home, style="Toolbar.TButton").grid(row=0, column=2, padx=6)

        ttk.Button(toolbar, text="About", command=self.show_about, style="Toolbar.TButton").grid(row=0, column=3, padx=(6, 0))

        ctrl = ttk.LabelFrame(left_panel, text="Inputs")
        ctrl.grid(row=1, column=0, sticky="new")
        ctrl.columnconfigure(1, weight=1)

        r = 0
        self.phi = tk.DoubleVar(value=30.0)
        ttk.Label(ctrl, text="φ (deg)\nFriction angle of soil").grid(row=r, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.phi, width=12).grid(row=r, column=1, sticky="w", padx=6, pady=6)
        r += 1

        self.beta = tk.DoubleVar(value=0.0)
        ttk.Label(ctrl, text="β (deg)\nBackfill angle").grid(row=r, column=0, sticky="w", padx=6, pady=6)
        ttk.Entry(ctrl, textvariable=self.beta, width=12).grid(row=r, column=1, sticky="w", padx=6, pady=6)
        r += 1

        result_frame = ttk.LabelFrame(ctrl, text="Results")
        result_frame.grid(row=r, column=0, columnspan=2, sticky="we", padx=6, pady=(8, 10))
        result_frame.columnconfigure(0, weight=1)
        self.out = tk.StringVar(value="Kₐ = —    |    Kₚ = —")
        ttk.Label(result_frame, textvariable=self.out, style="Result.TLabel", justify="left").grid(
            row=0, column=0, sticky="w", padx=6, pady=(6, 3)
        )
        self.note = tk.StringVar(value="")
        ttk.Label(result_frame, textvariable=self.note, justify="left", wraplength=300).grid(
            row=1, column=0, sticky="w", padx=6, pady=(0, 6)
        )

        spacer = ttk.Frame(left_panel)
        spacer.grid(row=2, column=0, sticky="nsew", pady=(10, 0))

        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(0, weight=1)

        self.teach = ScrollableFrame(right_panel)
        self.teach.grid(row=0, column=0, sticky="nsew")
        self.build_teaching_corner()

        self.compute()

    def open_home(self):
        webbrowser.open(HOME_URL)

    def show_about(self):
        message = (
            f"{PROGRAM_NAME}\n{VERSION}\n{AUTHOR}\n\n"
            "Computes Kₐ and Kₚ by direct application of the Rankine formulas.\n"
            "Inputs: φ (soil friction angle) and β (backfill angle).\n\n"
            "Educational tool — no warranty. Use at your own risk. Free of charge."
        )
        messagebox.showinfo("About", message)

    def compute(self):
        try:
            phi = float(self.phi.get())
            beta = float(self.beta.get())
            ka, kp = rankine_ka_kp(phi, beta)
            self.out.set(f"Kₐ = {ka:.4f}    |    Kₚ = {kp:.4f}")
            if abs(beta) > 1e-12:
                self.note.set(
                    "For non-zero β, the program evaluates the published expressions directly; "
                    "see the teaching corner for their limitations."
                )
            else:
                self.note.set(
                    "β = 0° gives the horizontal-backfill case."
                )
        except Exception as e:
            self.out.set("Kₐ = —    |    Kₚ = —")
            self.note.set("")
            messagebox.showerror("Error", str(e))

    def add_teach_title(self, text: str):
        ttk.Label(self.teach.inner, text=text, style="TeachTitle.TLabel").pack(anchor="w", padx=10, pady=(10, 4))

    def add_teach_body(self, text: str, wrap: int = 760):
        ttk.Label(self.teach.inner, text=text, style="TeachBody.TLabel", wraplength=wrap).pack(anchor="w", fill="x", padx=10, pady=(0, 8))

    def add_equation(self, equation: str, number: int, fontsize: int = 7):
        frame = ttk.Frame(self.teach.inner)
        frame.pack(fill="x", padx=10, pady=(0, 2))

        frame.columnconfigure(0, weight=1)   # equation column stretches
        frame.columnconfigure(1, weight=0)   # number column stays tight

        fig = Figure(figsize=(4.6, 0.34), dpi=170)
        fig.patch.set_facecolor("white")

        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        ax.set_axis_off()
        ax.text(0.00, 0.50, f"${equation}$", ha="left", va="center", fontsize=fontsize)

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()

        eq_widget = canvas.get_tk_widget()
        eq_widget.grid(row=0, column=0, sticky="w")

        num_lbl = ttk.Label(frame, text=f"({number})", font=("Segoe UI", 10))
        num_lbl.grid(row=0, column=1, sticky="e", padx=(8, 6))

        self._teaching_images.append(canvas)

    def add_teaching_image(self, filename: str, max_width: int = 720, left_pad: int = 10, top_bottom_pad=(4, 10)):
        path = find_local_file(filename)
        if not path:
            print("Image not found:", filename)
            return

        try:
            img = Image.open(path).convert("RGBA")

            w, h = img.size
            if w > max_width:
                scale = max_width / float(w)
                new_w = int(w * scale)
                new_h = int(h * scale)
                img = img.resize((new_w, new_h), Image.LANCZOS)

            photo = ImageTk.PhotoImage(img)
            self._teaching_images.append(photo)

            frame = ttk.Frame(self.teach.inner)
            frame.pack(anchor="w", fill="x", padx=(left_pad, 10), pady=top_bottom_pad)

            lbl = ttk.Label(frame, image=photo)
            lbl.image = photo
            lbl.pack(anchor="w")

        except Exception as e:
            print("Failed to load image:", path, e)

    def build_teaching_corner(self):
        self.add_teach_title("Rankine formulas used by this program")

        self.add_equation(
            r"K_a = \frac{\cos\beta \left(\cos\beta - \sqrt{\cos^2\beta - \cos^2\phi}\right)}{\cos\beta + \sqrt{\cos^2\beta - \cos^2\phi}}", 1
        )

        self.add_equation(
            r"K_p = \frac{\cos\beta \left(\cos\beta + \sqrt{\cos^2\beta - \cos^2\phi}\right)}{\cos\beta - \sqrt{\cos^2\beta - \cos^2\phi}}", 2
        )

        # Rankine reference
        self.add_teach_body(
            "Rankine, W. J. M. (1857). On the stability of loose earth. "
            "Philosophical Transactions of the Royal Society of London, 147, 9–27."
        )

        self.add_teach_title("Assumptions behind Rankine theory")
        self.add_teach_body(
            "Rankine’s original theory is derived for a cohesionless granular mass whose stability arises from internal friction alone. "
            "The wall is smooth, so wall friction is zero, and the stress state is governed by limiting frictional equilibrium. "
            "In the original 1857 paper, Rankine treated the case of a horizontal or uniformly sloping backfill."
        )

        self.add_teach_title("Why Rankine theory is not valid for non-zero backfill angle")

        self.add_teach_body(
            "Perhaps few have noticed that a positive (and therefore, favourable) angle β results in an unfavourable Kₚ coefficient (and vice versa). "
            "This is obviously not acceptable."
        )

        self.add_teach_body(
            "Schematically, for sloping ground inclined at an angle of β to the horizontal, the active Rankine’s earth pressure is defined by point B in Figure 1 (σA′). "
            "The fact that σA′ > σA, as explained below, does not mean that σA′ is the correct answer to Rankine’s problem. "
            "In this context, point E provides the answer. Point E defines the corresponding passive Rankine’s earth pressure (σP′′), which is smaller than σP; "
            "the latter obviously should not be the case. This discrepancy is a strong indication that the line OE in Figure 1 does not represent the ground inclination."
        )

        self.add_teach_body(
            "Another indication is that the vertical stress of the sloping ground in the active state is less than that of the horizontal ground (σν < σv), which is also incorrect."
        )

        self.add_teach_body(
            "A third indication is that the same point in the ground has different vertical stress depending on whether the problem is examined from the “active” or “passive” perspective "
            "(i.e., σv′ ≠ σv″; point C ≠ point D). This is also not acceptable since the vertical stress in the ground should be independent of the state of the soil."
        )

        # ✅ FIGURE 2 (σωστό σημείο και σωστή χρήση)
        self.add_teaching_image("fig2.png", max_width=400)

        self.add_teach_body(
            "Figure 1. Rankine’s theory for sloping ground for the active and passive state"
        )

        self.add_teach_title("The paradox")

        self.add_teach_body(
            "For φ = 30° and β = 0°, Kₐ = 0.3333 and Kₚ = 3.0000. "
            "For β either +10 or -10°, Kₐ = 0.3495 and Kₚ = 2.7748."
        )

        self.add_teach_body(
            "Thus, not only +10° and −10° give identical results, but also, the passive coefficient becomes smaller than the horizontal case, which is incorrect."
        )

        self.add_teach_title("Further reading")

        ref_frame = ttk.Frame(self.teach.inner)
        ref_frame.pack(anchor="w", fill="x", padx=10, pady=(0, 10))

        ref_text = (
            "Pantelidis, L. (2024). From EN 1998-5: 2004 to prEN 1998-5: 2023: "
            "Has the calculation of earth pressures improved or deteriorated? "
            "In Proceedings of the XVIII European Conference on Soil Mechanics "
            "and Geotechnical Engineering (ECSMGE 2024), Lisbon, Portugal, "
            "26–30 August 2024 (pp. 733–738). CRC Press. "
        )

        ttk.Label(ref_frame, text=ref_text, wraplength=760, justify="left").pack(anchor="w")

        doi_label = tk.Label(
            ref_frame,
            text="https://doi.org/10.1201/9781003431749-121",
            fg="blue",
            cursor="hand2",
            wraplength=760,
            justify="left"
        )
        doi_label.pack(anchor="w")
        doi_label.bind("<Button-1>", lambda e: webbrowser.open("https://doi.org/10.1201/9781003431749-121"))

        ttk.Label(ref_frame, text="").pack()

        ttk.Label(ref_frame, text="Direct download:", font=("Segoe UI", 10, "bold")).pack(anchor="w")

        dl_label = tk.Label(
            ref_frame,
            text="https://www.issmge.org/uploads/publications/51/126/367_A_from_en_199852004_to_pren_199852023_has_the_calcul.pdf",
            fg="blue",
            cursor="hand2",
            wraplength=760,
            justify="left"
        )
        dl_label.pack(anchor="w")

        dl_label.bind(
            "<Button-1>",
            lambda e: webbrowser.open(
                "https://www.issmge.org/uploads/publications/51/126/367_A_from_en_199852004_to_pren_199852023_has_the_calcul.pdf"
            )
        )

if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
