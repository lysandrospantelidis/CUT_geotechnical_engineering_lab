# CUT_K_Coulomb_UI_TOPORIGIN_v3a.py
# -----------------------------------------------------------------------------
# PROGRAM_NAME = "CUT_K_Coulomb"
# VERSION      = "v1.0.0"
# AUTHOR       = "Dr Lysandros Pantelidis, Cyprus University of Technology"
#
# Smooth **vertical** (not battered) wall, δ = 0. Arbitrary piecewise-linear
# soil surface. Origin at top of wall (0,0); wall down to (0,-H). Failure plane
# leaves the base (0,-H) at angle θ from horizontal and intersects the surface.
#
# K(θ) = (2/H^2) * A(θ) * tan(θ ∓ φ)  | (−) active (maximize K), (+) passive (minimize K)
# -----------------------------------------------------------------------------

import math
from typing import List, Tuple, Optional

import tkinter as tk
from tkinter import ttk, messagebox

import numpy as np
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

PROGRAM_NAME = "CUT_K_Coulomb"
VERSION = "v1.0.0"
AUTHOR = "Dr Lysandros Pantelidis, Cyprus University of Technology"

Point = Tuple[float, float]


# ---------------- Geometry helpers (TOP origin) ----------------
class GeometryError(ValueError):
    pass


def _line_intersection_from_base(y0: float, m: float, p1: Point, p2: Point) -> Optional[Point]:
    (x1, y1), (x2, y2) = p1, p2
    dx, dy = x2 - x1, y2 - y1
    denom = dy - m * dx
    if abs(denom) < 1e-14:
        return None
    t = (m * x1 + y0 - y1) / denom
    if 0.0 <= t <= 1.0:
        xi, yi = x1 + t * dx, y1 + t * dy
        if xi > 1e-9:
            return (xi, yi)
    return None


def _polygon_area(points: List[Point]) -> float:
    a = 0.0
    n = len(points)
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        a += x1 * y2 - x2 * y1
    return abs(0.5 * a)


def _build_wedge(H: float, surface: List[Point], theta: float) -> Tuple[Optional[List[Point]], float]:
    m = math.tan(theta)
    poly = [(0.0, 0.0), (0.0, -H)]
    hit = None
    for i in range(len(surface) - 1):
        p1, p2 = surface[i], surface[i + 1]
        inter = _line_intersection_from_base(-H, m, p1, p2)
        if inter is not None:
            hit = inter
            poly.append(hit)
            poly.extend(reversed(surface[:i+1]))
            break
    if hit is None:
        return None, 0.0
    if poly[-1] != (0.0, 0.0):
        poly.append((0.0, 0.0))
    if _polygon_area(poly) <= 1e-12:
        return None, 0.0
    return poly, hit[0]


def _K_from_geom(H: float, area: float, angle_term: float) -> float:
    return (2.0 / (H * H)) * area * math.tan(angle_term)


def _sweep_theta(phi: float, H: float, surface: List[Point], mode: str, n_steps: int):
    eps = math.radians(0.1)
    if mode == "active":
        theta_min = max(eps, phi + eps)
        theta_max = math.radians(89.5)
        compare = lambda obj, best: (obj < best)  # minimize -K -> maximize K
        sign = -1
    else:
        theta_min = eps
        theta_max = max(theta_min + eps, math.radians(89.5) - phi)
        compare = lambda obj, best: (obj < best)  # minimize K
        sign = +1

    best_theta = None
    best_K = None
    best_obj = float("inf")
    for i in range(1, n_steps):
        theta = theta_min + (theta_max - theta_min) * i / n_steps
        poly, _ = _build_wedge(H, surface, theta)
        if poly is None:
            continue
        area = _polygon_area(poly)
        angle_term = (theta - phi) if mode == "active" else (theta + phi)
        if not (0.0 < angle_term < math.radians(89.0)):
            continue
        K = _K_from_geom(H, area, angle_term)
        obj = sign * K
        if compare(obj, best_obj):
            best_obj = obj
            best_theta = theta
            best_K = K
    if best_K is None:
        raise GeometryError("No feasible wedge found for these inputs.")
    return best_theta, best_K


def coulomb_top_origin(phi_deg: float, H: float, surface_pts: List[Point], n_steps: int, mode: str):
    if not (0.0 < phi_deg < 90.0):
        raise ValueError("φ must be between 0 and 90 degrees.")
    if H <= 0:
        raise ValueError("H must be positive.")
    if len(surface_pts) < 2:
        raise ValueError("Provide ≥2 surface points starting at (0, 0).")
    for (x1, _), (x2, _) in zip(surface_pts, surface_pts[1:]):
        if x2 < x1 - 1e-12:
            raise ValueError("x must be non-decreasing from Point 0 outward.")
    phi = math.radians(phi_deg)
    th, K = _sweep_theta(phi, H, surface_pts, mode, n_steps)
    return dict(theta_deg=math.degrees(th), K=K)


# ---------------- Tkinter GUI ----------------
class App:
    def __init__(self, root):
        self.root = root
        root.title(f"{PROGRAM_NAME} — TOP Origin")

        # Styles
        style = ttk.Style(root)
        try:
            if style.theme_use() == "classic":
                style.theme_use("default")
        except Exception:
            pass
        style.configure("Result.TLabel", font=("Segoe UI", 12, "bold"))
        style.configure("Header.TLabel", font=("Segoe UI", 10, "bold"))
        style.configure("Compute.TButton", font=("Segoe UI", 10, "bold"))
        style.configure("About.TButton", font=("Segoe UI", 9))

        main = ttk.Frame(root, padding=8); main.grid(row=0, column=0, sticky="nsew")
        root.columnconfigure(0, weight=1); root.rowconfigure(0, weight=1)

        # Left controls
        ctrl = ttk.Frame(main); ctrl.grid(row=0, column=0, sticky="nsw", padx=(0,10))
        r = 0

        # Toolbar with side-by-side buttons
        toolbar = ttk.Frame(ctrl)
        toolbar.grid(row=r, column=0, columnspan=2, sticky="we", pady=(0,6))
        toolbar.columnconfigure(0, weight=1); toolbar.columnconfigure(1, weight=0)

        self._compute_img = None
        try:
            self._compute_img = tk.PhotoImage(file="compute.png")
            compute_btn = ttk.Button(toolbar, image=self._compute_img, command=self.compute, style="Compute.TButton")
        except Exception:
            compute_btn = ttk.Button(toolbar, text="Compute", command=self.compute, style="Compute.TButton")
        compute_btn.grid(row=0, column=0, sticky="w")

        about_btn = ttk.Button(toolbar, text="About", command=self.show_about, style="About.TButton")
        about_btn.grid(row=0, column=1, sticky="e")
        r += 1

        # Mode, phi, H, steps
        self.mode = tk.StringVar(value="active")
        ttk.Label(ctrl, text="Mode").grid(row=r, column=0, sticky="w")
        ttk.Combobox(ctrl, textvariable=self.mode, values=["active", "passive"], state="readonly", width=12)\
            .grid(row=r, column=1, sticky="w"); r+=1

        self.phi = tk.DoubleVar(value=30.0)
        ttk.Label(ctrl, text="φ (deg)").grid(row=r, column=0, sticky="w")
        ttk.Entry(ctrl, textvariable=self.phi, width=10).grid(row=r, column=1, sticky="w"); r+=1

        self.H = tk.DoubleVar(value=6.0)
        ttk.Label(ctrl, text="H (m)\n(wall height, downward)").grid(row=r, column=0, sticky="w")
        ttk.Entry(ctrl, textvariable=self.H, width=10).grid(row=r, column=1, sticky="w"); r+=1

        self.n_steps = tk.IntVar(value=10000)
        ttk.Label(ctrl, text="Angle sweep steps").grid(row=r, column=0, sticky="w")
        ttk.Entry(ctrl, textvariable=self.n_steps, width=10).grid(row=r, column=1, sticky="w"); r+=1

        # Result panel
        result_frame = ttk.LabelFrame(ctrl, text="Results")
        result_frame.grid(row=r, column=0, columnspan=2, sticky="we", pady=(0,8))
        self.out = tk.StringVar()
        ttk.Label(result_frame, textvariable=self.out, style="Result.TLabel", justify="left")\
            .grid(row=0, column=0, sticky="w", padx=6, pady=6)
        r += 1

        # Points table (auto names)
        points_box = ttk.LabelFrame(main, text="Points (TOP origin: Point 0 is fixed at (0, 0))")
        points_box.grid(row=0, column=1, sticky="nsew"); main.columnconfigure(1, weight=1)
        ph = ttk.Frame(points_box); ph.grid(row=0, column=0, sticky="ew")
        for c, t in enumerate(["", "Point", "x", "y"]):
            ttk.Label(ph, text=t, style="Header.TLabel").grid(row=0, column=c, padx=4, pady=2, sticky="w")
        self.points_rows = ttk.Frame(points_box); self.points_rows.grid(row=1, column=0, sticky="nsew")
        points_box.columnconfigure(0, weight=1)
        btns = ttk.Frame(points_box); btns.grid(row=2, column=0, sticky="ew", pady=(6,0))
        ttk.Button(btns, text="Add Point", command=self.add_point_row).pack(side="left")
        ttk.Button(btns, text="Remove Selected", command=self.remove_selected_points).pack(side="left", padx=6)

        # Plot / Sketch area (ADDED BACK)
        plot_box = ttk.LabelFrame(main, text="Geometry & Wedge")
        plot_box.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(10,0))
        main.rowconfigure(1, weight=1)
        fig = Figure(figsize=(7.2, 4.2), dpi=100)
        self.ax = fig.add_subplot(111)                # <<--- ensures self.ax exists
        self.canvas = FigureCanvasTkAgg(fig, master=plot_box)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        plot_box.columnconfigure(0, weight=1); plot_box.rowconfigure(0, weight=1)

        # Defaults
        self.point_rows = []
        self.add_point_row(prefill=(0.0, 0.0), locked=True)  # Point 0
        self.add_point_row(prefill=(5.0, 0.5))
        self.add_point_row(prefill=(10.0, 0.8))

    # ---- UI helpers ----
    def _renumber_point_labels(self):
        for idx, row in enumerate(self.point_rows):
            row["lbl"].configure(text=f"Point {idx}")

    def add_point_row(self, prefill=None, locked=False):
        row = ttk.Frame(self.points_rows); row.pack(fill="x", pady=1)
        sel = tk.BooleanVar(value=False)
        ttk.Checkbutton(row, variable=sel).grid(row=0, column=0, padx=(2,4))
        lbl = ttk.Label(row, text="")
        lbl.grid(row=0, column=1, padx=2)
        x_var = tk.DoubleVar(value=prefill[0] if prefill else 0.0)
        y_var = tk.DoubleVar(value=prefill[1] if prefill else 0.0)
        ttk.Entry(row, textvariable=x_var, width=8, state="disabled" if locked else "normal").grid(row=0, column=2, padx=2)
        ttk.Entry(row, textvariable=y_var, width=8, state="disabled" if locked else "normal").grid(row=0, column=3, padx=2)
        self.point_rows.append(dict(frame=row, lbl=lbl, x=x_var, y=y_var, sel=sel, locked=locked))
        self._renumber_point_labels()

    def remove_selected_points(self):
        to_keep = []
        for idx, row in enumerate(self.point_rows):
            if idx == 0:
                to_keep.append(row)
                continue
            if row["sel"].get():
                row["frame"].destroy()
            else:
                to_keep.append(row)
        self.point_rows = to_keep
        self._renumber_point_labels()

    # ---- About ----
    def show_about(self):
        message = (
            f"{PROGRAM_NAME}\n"
            f"{VERSION}\n"
            f"{AUTHOR}\n\n"
            "Smooth VERTICAL wall (δ = 0). The wall top is the origin (0,0); "
            "the failure plane leaves the base (0,-H) and intersects the user-defined broken surface. "
            "Ka/Kp are computed by sweeping θ and optimizing the classic Coulomb objective. "
            "Any soil surface geometry can be modeled via points. "
			"Educational tool — no warranty. Use at your own risk. Free of charge."
        )
        messagebox.showinfo("About", message)

    # ---- Parsing ----
    def _collect_points(self) -> List[Point]:
        pts = []
        for idx, row in enumerate(self.point_rows):
            x = float(row["x"].get()); y = float(row["y"].get())
            pts.append((x, y))
        if len(pts) == 0 or abs(pts[0][0]) > 1e-12 or abs(pts[0][1]) > 1e-12:
            raise ValueError("Point 0 must be exactly at (0, 0).")
        for (x1, _), (x2, _) in zip(pts, pts[1:]):
            if x2 < x1 - 1e-12:
                raise ValueError("x must be non-decreasing from Point 0 outward.")
        if len(pts) < 2:
            raise ValueError("Provide at least two points (Point 0 and one more).")
        return pts

    # ---- Compute & plot ----
    def compute(self):
        try:
            mode = self.mode.get()
            phi = float(self.phi.get()); H = float(self.H.get()); steps = int(self.n_steps.get())
            surface = self._collect_points()
            res = coulomb_top_origin(phi, H, surface, steps, mode)
            K, th = res["K"], res["theta_deg"]

            if mode == "active":
                self.out.set(f"K\u2090 = {K:.4f}    |    \u03B8 = {th:.2f}\N{DEGREE SIGN}")
            else:
                self.out.set(f"K\u209A = {K:.4f}    |    \u03B8 = {th:.2f}\N{DEGREE SIGN}")

            # Plot
            self.ax.clear()
            xs_plot = [p[0] for p in surface]; ys_plot = [p[1] for p in surface]
            self.ax.plot([0, 0], [0, -H], lw=2, color="k")
            self.ax.plot(xs_plot, ys_plot, marker="o")
            th_rad = math.radians(th)
            xa = np.linspace(0, max(xs_plot) if xs_plot else 1.0, 200)
            ya = -H + np.tan(th_rad) * xa
            self.ax.plot(xa, ya, ls="--")
            poly, _ = _build_wedge(H, surface, th_rad)
            if poly:
                self.ax.fill([p[0] for p in poly], [p[1] for p in poly], alpha=0.18)
            xmax = max(1.0, max(xs_plot) * 1.2 if xs_plot else 1.0)
            ymax = max(1.0, max([0.0] + ys_plot) * 1.4 if ys_plot else 1.0)
            self.ax.set_aspect("equal", adjustable="box")
            self.ax.set_xlim(-0.5, xmax); self.ax.set_ylim(-H * 1.15, ymax)
            self.ax.set_xlabel("x (m)  \u2192"); self.ax.set_ylabel("y (m)  \u2191   (top at 0)")
            self.ax.grid(True, alpha=0.3); self.canvas.draw()
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
