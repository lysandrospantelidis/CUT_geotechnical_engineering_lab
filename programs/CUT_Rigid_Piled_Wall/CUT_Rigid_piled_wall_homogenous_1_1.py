# CUT_Rigid_piled_wall_homogenous.py

from __future__ import annotations

import sys
import os
import webbrowser
from PIL import Image, ImageTk

from dataclasses import dataclass
from typing import Literal, Optional, TypedDict, Any
import math
import tkinter as tk
from tkinter import ttk, messagebox

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # PyInstaller temp folder
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)
    
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg


Quadrant = Literal["RA", "RP", "LP", "LA", "void"]
QuadrantType = Literal["active", "passive"]
SideName = Literal["left", "right"]

# ============================================================
# Data containers
# ============================================================

@dataclass
class Geometry:
    H_R: float
    H_L: float
    z_p: float


@dataclass
class SideData:
    beta_deg: float
    q_real: float
    z_w: float
    gamma: float
    gamma_sat: float
    c_prime: float
    phi_prime_deg: float
    E_s: float
    nu: float


@dataclass
class SeismicData:
    a_v: float
    k_v: float
    theta_eq_deg: float


@dataclass
class MovementData:
    dx_trans: float
    theta_rot_deg: float


class VerticalStressResult(TypedDict):
    z_local: float
    z_w_local: float
    sigma_v_geo: float
    q_upper: float
    sigma_v_total: float


class PhiMResult(TypedDict):
    phi_m_deg: float
    e1: float
    e2: float
    a0: float
    b0: float
    c0: float
    d0: float
    D0: float
    D1: float
    C0: complex


class StateSolveResult(TypedDict):
    lambda_value: int
    A0: float
    B1: float
    C1: float
    phi_m: PhiMResult
    c_m: float
    K_XE: float


class PointSolveResult(TypedDict):
    z: float
    side: SideName
    quadrant: Quadrant
    quadrant_type: Optional[QuadrantType]
    z_local: Optional[float]
    H_quad: Optional[float]
    beta_deg: Optional[float]
    q_real: Optional[float]
    q_upper: Optional[float]
    sigma_v_geo: Optional[float]
    sigma_v_total: Optional[float]
    u: Optional[float]
    dx_rot: Optional[float]
    dx_tot_signed: Optional[float]
    dx_tot_abs: Optional[float]
    K_OE: Optional[float]
    K_AE: Optional[float]
    K_PE: Optional[float]
    K_limit: Optional[float]
    DeltaK: Optional[float]
    dx_max: Optional[float]
    dx_M: Optional[float]
    m: Optional[float]
    xi: Optional[float]
    xi1: Optional[float]
    xi2: Optional[float]
    lambda_value: Optional[int]
    A0: Optional[float]
    B1: Optional[float]
    C1: Optional[float]
    phi_m_deg: Optional[float]
    c_m: Optional[float]
    K_XE: Optional[float]
    slope_factor: Optional[float]
    sigma_h_OE: Optional[float]
    sigma_h_AE: Optional[float]
    sigma_h_PE: Optional[float]
    sigma_h_limit: Optional[float]
    sigma_h_corrected: Optional[float]
    p_h_final: Optional[float]
    notes: list[str]


# ============================================================
# Small helpers
# ============================================================

M_FULL = 1_000_000_000.0
C_PRIME_MIN = 1e-5
PHI_PRIME_MIN_DEG = 1e-6



# ============================================================
# Small helpers
# ============================================================

def _deg_tan(angle_deg: float) -> float:
    return math.tan(math.radians(angle_deg))


def get_state_label(dx_signed: float, dx_max: float, qtype: Optional[QuadrantType] = None) -> str:
    """Compact mobilization-state label for profile tables.

    O  = at rest, dx_tot ~= 0
    IA = intermediate active, before the active limit
    IP = intermediate passive, before the passive limit
    A  = active limit reached
    P  = passive limit reached
    """
    if dx_signed is None:
        return "—"
    if abs(dx_signed) < 1e-12:
        return "O"

    direction = qtype
    if direction not in ("active", "passive"):
        direction = "active" if dx_signed < 0.0 else "passive"

    if dx_max is not None and dx_max > 0.0 and abs(dx_signed) >= dx_max:
        return "A" if direction == "active" else "P"

    return "IA" if direction == "active" else "IP"

def _safe_positive(name: str, value: float) -> None:
    if value <= 0.0:
        raise ValueError(f"{name} must be positive, got {value}.")


def _clip_unit(x: float) -> float:
    return max(-1.0, min(1.0, x))


def _profile_epsilon(H: float) -> float:
    """Small positive depth used to avoid singular evaluation exactly at z=0."""
    return 1e-6 * max(1.0, H)


def _regularize_c_prime(c_prime: float) -> float:
    return max(float(c_prime), C_PRIME_MIN)


def _regularize_phi_prime_deg(phi_prime_deg: float) -> float:
    return max(float(phi_prime_deg), PHI_PRIME_MIN_DEG)


def _regularize_side_data(side_data: SideData) -> SideData:
    return SideData(
        beta_deg=side_data.beta_deg,
        q_real=side_data.q_real,
        z_w=side_data.z_w,
        gamma=side_data.gamma,
        gamma_sat=side_data.gamma_sat,
        c_prime=_regularize_c_prime(side_data.c_prime),
        phi_prime_deg=_regularize_phi_prime_deg(side_data.phi_prime_deg),
        E_s=side_data.E_s,
        nu=side_data.nu,
    )


# ============================================================
# Task 2 — Geometry / quadrant functions
# ============================================================


def classify_quadrant(z: float, side: SideName, H_R: float, H_L: float, z_p: float) -> Quadrant:
    """
    Return the quadrant for a given global depth z and side.

    right:
        0 <= z <= z_p   -> RA
        z_p <= z <= H_R -> RP

    left:
        soil exists only for H_R - H_L <= z <= H_R
        if z_p > H_R - H_L:
            H_R-H_L <= z <= z_p -> LP
            z_p <= z <= H_R     -> LA
        if z_p < H_R - H_L:
            H_R-H_L <= z <= H_R -> LA
    """
    if z < 0.0 or z > H_R:
        return "void"

    if side == "right":
        if z <= z_p:
            return "RA"
        return "RP"

    z_left_surface = H_R - H_L
    if z < z_left_surface or z > H_R:
        return "void"

    if z_p > z_left_surface:
        if z <= z_p:
            return "LP"
        return "LA"

    if z_p < z_left_surface:
        return "LA"

    # Boundary case: z_p == z_left_surface
    if z == z_p:
        return "LP"
    return "LA"



def quadrant_type(quadrant: Quadrant) -> Optional[QuadrantType]:
    """
    Geometric default only. Do not use this function for mobilized active/passive
    state after wall movement.
    """
    if quadrant in ("RA", "LA"):
        return "active"
    if quadrant in ("LP", "RP"):
        return "passive"
    return None



def mobilized_quadrant_type(quadrant: Quadrant, dx_tot_signed: float) -> Optional[QuadrantType]:
    """
    Return the active/passive state using the agreed movement convention.

    Positive displacement is to the left.
    Translational dx is always positive.
    Rotational dx is positive above z_p and negative below z_p.

        LP: always passive, if it exists
        RA: always active
        LA: passive if dx_tot >= 0, active if dx_tot < 0
        RP: active if dx_tot >= 0, passive if dx_tot < 0
    """
    if quadrant == "LP":
        return "passive"
    if quadrant == "RA":
        return "active"
    if quadrant == "LA":
        return "passive" if dx_tot_signed >= 0.0 else "active"
    if quadrant == "RP":
        return "active" if dx_tot_signed >= 0.0 else "passive"
    return None



def quadrant_side(quadrant: Quadrant) -> Optional[SideName]:
    """RA, RP -> right; LP, LA -> left; void -> None."""
    if quadrant in ("RA", "RP"):
        return "right"
    if quadrant in ("LP", "LA"):
        return "left"
    return None



def local_depth(z: float, quadrant: Quadrant, H_R: float, H_L: float, z_p: float) -> float:
    """
    Local depth by agreed convention:
        RA: z_local = z
        RP: z_local = z - z_p
        LP: z_local = z - (H_R - H_L)
        LA: z_local = z - z_p
    """
    if quadrant == "RA":
        return z
    if quadrant == "RP":
        return z - z_p
    if quadrant == "LP":
        return z - (H_R - H_L)
    if quadrant == "LA":
        return z - z_p
    raise ValueError("local_depth is undefined for 'void'.")



def quadrant_height(quadrant: Quadrant, H_R: float, H_L: float, z_p: float) -> float:
    """
    Characteristic height H of each quadrant:
        RA: H_RA = z_p
        RP: H_RP = H_R - z_p
        LP: H_LP = z_p - (H_R - H_L)
        LA: H_LA = H_R - z_p
    """
    if quadrant == "RA":
        return z_p
    if quadrant == "RP":
        return H_R - z_p
    if quadrant == "LP":
        return z_p - (H_R - H_L)
    if quadrant == "LA":
        return H_R - z_p
    raise ValueError("quadrant_height is undefined for 'void'.")


# ============================================================

def side_mobilization_depth(z: float, side: SideName, H_R: float, H_L: float) -> float:
    """
    Continuous mobilization depth measured from the actual ground surface
    of each side, not from the internal pivot/quadrant boundary.

    This prevents an artificial reset of z_local to zero at z_p, which would
    create spurious spikes at the pivot point under pure translation.
    """
    if side == "right":
        return z
    if side == "left":
        return z - (H_R - H_L)
    raise ValueError("side_mobilization_depth requires side='left' or side='right'.")


def side_mobilization_height(side: SideName, H_R: float, H_L: float) -> float:
    """Return the full soil height of the selected side for mobilization."""
    if side == "right":
        return H_R
    if side == "left":
        return H_L
    raise ValueError("side_mobilization_height requires side='left' or side='right'.")

# Task 3 — Side-property lookup
# ============================================================


def get_side_data(quadrant: Quadrant, left_data: SideData, right_data: SideData) -> SideData:
    """Return the corresponding side data for the quadrant."""
    side = quadrant_side(quadrant)
    if side == "left":
        return left_data
    if side == "right":
        return right_data
    raise ValueError("get_side_data is undefined for 'void'.")



def get_beta_for_quadrant(quadrant: Quadrant, left_data: SideData, right_data: SideData) -> float:
    """Return beta_R for RA/RP and beta_L for LP/LA."""
    return get_side_data(quadrant, left_data, right_data).beta_deg


# ============================================================
# Task 4 — Water and geostatic stress functions
# ============================================================


def local_water_depth(z_w_global: float, quadrant: Quadrant, H_R: float, H_L: float, z_p: float) -> float:
    """
    Convert global water table depth to local depth coordinate for the quadrant.
    By convention:
        RA: z_w_local = z_w_R
        RP: z_w_local = z_w_R - z_p
        LP: z_w_local = z_w_L - (H_R - H_L)
        LA: z_w_local = z_w_L - z_p
    """
    if quadrant == "RA":
        return z_w_global
    if quadrant == "RP":
        return z_w_global - z_p
    if quadrant == "LP":
        return z_w_global - (H_R - H_L)
    if quadrant == "LA":
        return z_w_global - z_p
    raise ValueError("local_water_depth is undefined for 'void'.")



def vertical_geostatic_stress(
    z_local: float,
    gamma: float,
    gamma_sat: float,
    z_w_local: float,
    gamma_w: float = 0.0,
    include_water_overburden: bool = False,
) -> float:
    """
    Total geostatic vertical stress using gamma above water table and gamma_sat below.

    If z_w_local < 0, the water table is above the local origin. For local
    origins that are actual ground surfaces (RA and LP), include the water
    column above the soil surface as a total vertical overburden. For local
    origins that are internal quadrant boundaries (RP and LA), do not add
    this water head again because the overlying total surcharge has already
    been transferred through q_upper.
    """
    if z_local <= 0.0:
        if include_water_overburden and z_w_local < 0.0:
            return gamma_w * (-z_w_local)
        return 0.0
    if z_w_local <= 0.0:
        water_overburden = gamma_w * (-z_w_local) if include_water_overburden else 0.0
        return water_overburden + gamma_sat * z_local
    if z_local <= z_w_local:
        return gamma * z_local
    return gamma * z_w_local + gamma_sat * (z_local - z_w_local)



def pore_pressure(z_local: float, z_w_local: float, gamma_w: float) -> float:
    """
    u = 0 for z_local <= z_w_local
    u = gamma_w * (z_local - z_w_local) otherwise
    """
    if z_local <= z_w_local:
        return 0.0
    return gamma_w * (z_local - z_w_local)


# ============================================================
# Task 5 — Upper-quadrant surcharge functions
# ============================================================


def compute_q_RA_total(geometry: Geometry, right_data: SideData, gamma_w: float) -> float:
    """
    Total surcharge transferred from RA to RP:
        q_RA_total = q_R + sigma_v_geo at base of RA
    """
    z_local_base = geometry.z_p
    z_w_local = right_data.z_w
    sigma_v_geo_base = vertical_geostatic_stress(
        z_local=z_local_base,
        gamma=right_data.gamma,
        gamma_sat=right_data.gamma_sat,
        z_w_local=z_w_local,
        gamma_w=gamma_w,
        include_water_overburden=True,
    )
    return right_data.q_real + sigma_v_geo_base



def compute_q_LP_total(geometry: Geometry, left_data: SideData, gamma_w: float) -> float:
    """
    Total surcharge transferred from LP to LA:
        q_LP_total = q_L + sigma_v_geo at base of LP
    Only meaningful if LP exists.
    """
    H_LP = geometry.z_p - (geometry.H_R - geometry.H_L)
    if H_LP <= 0.0:
        return 0.0
    z_local_base = H_LP
    z_w_local = local_water_depth(left_data.z_w, "LP", geometry.H_R, geometry.H_L, geometry.z_p)
    sigma_v_geo_base = vertical_geostatic_stress(
        z_local=z_local_base,
        gamma=left_data.gamma,
        gamma_sat=left_data.gamma_sat,
        z_w_local=z_w_local,
        gamma_w=gamma_w,
        include_water_overburden=True,
    )
    return left_data.q_real + sigma_v_geo_base



def upper_quadrant_surcharge(
    quadrant: Quadrant,
    geometry: Geometry,
    left_data: SideData,
    right_data: SideData,
    gamma_w: float,
) -> float:
    """
    Return upper-quadrant surcharge by agreed convention:
        RA -> 0
        RP -> q_RA_total
        LP -> 0
        LA -> q_LP_total if LP exists else 0
    """
    if quadrant == "RA":
        return 0.0
    if quadrant == "RP":
        return compute_q_RA_total(geometry, right_data, gamma_w)
    if quadrant == "LP":
        return 0.0
    if quadrant == "LA":
        H_LP = geometry.z_p - (geometry.H_R - geometry.H_L)
        if H_LP > 0.0:
            return compute_q_LP_total(geometry, left_data, gamma_w)
        return 0.0
    raise ValueError("upper_quadrant_surcharge is undefined for 'void'.")


# ============================================================
# Task 6 — Total vertical stress
# ============================================================


def total_vertical_stress(
    z: float,
    quadrant: Quadrant,
    geometry: Geometry,
    left_data: SideData,
    right_data: SideData,
    gamma_w: float,
) -> VerticalStressResult:
    """
    By the locked convention:
        Upper quadrants: sigma_v = q_real + sigma_v_geo
        Lower quadrants: sigma_v = q_upper_total + sigma_v_geo(lower)
    Returns local depth, local water depth, geostatic component, upper surcharge,
    and total vertical stress.
    """
    if quadrant == "void":
        raise ValueError("total_vertical_stress is undefined for 'void'.")

    side_data = get_side_data(quadrant, left_data, right_data)
    z_local = local_depth(z, quadrant, geometry.H_R, geometry.H_L, geometry.z_p)
    z_w_local = local_water_depth(side_data.z_w, quadrant, geometry.H_R, geometry.H_L, geometry.z_p)
    sigma_v_geo = vertical_geostatic_stress(
        z_local=z_local,
        gamma=side_data.gamma,
        gamma_sat=side_data.gamma_sat,
        z_w_local=z_w_local,
        gamma_w=gamma_w,
        include_water_overburden=quadrant in ("RA", "LP"),
    )
    q_upper = upper_quadrant_surcharge(quadrant, geometry, left_data, right_data, gamma_w)

    if quadrant in ("RA", "LP"):
        sigma_v_total = side_data.q_real + sigma_v_geo
    else:
        sigma_v_total = q_upper + sigma_v_geo

    return {
        "z_local": z_local,
        "z_w_local": z_w_local,
        "sigma_v_geo": sigma_v_geo,
        "q_upper": q_upper,
        "sigma_v_total": sigma_v_total,
    }


# ============================================================
# Task 7 — Movement functions
# ============================================================


def rotation_displacement(z: float, z_p: float, theta_rot_deg: float) -> float:
    """
    Signed rotational displacement under the agreed convention:
        positive to the left above z_p
        negative to the right below z_p
    """
    dx_rot_abs = abs(z - z_p) * _deg_tan(theta_rot_deg)
    if z <= z_p:
        return dx_rot_abs
    return -dx_rot_abs



def signed_total_displacement(dx_trans: float, dx_rot_signed: float) -> float:
    """
    Total signed displacement under the agreed convention:
        dx_trans is always positive to the left
        dx_rot_signed carries its own sign
    """
    return dx_trans + dx_rot_signed



def absolute_total_displacement(dx_tot_signed: float) -> float:
    """Return the magnitude of the total displacement used for mobilization."""
    return abs(dx_tot_signed)


# ============================================================
# Task 8 — Mobilization parameter functions
# ============================================================


def xi_parameters(m: float) -> tuple[float, float, float]:
    """
    xi  = (m - 1)/(m + 1) - 1
    xi1 = 1 + xi
    xi2 = 2/m - 1
    """
    if m <= 0:
        raise ValueError("m must be positive.")
    xi = (m - 1.0) / (m + 1.0) - 1.0
    xi1 = 1.0 + xi
    xi2 = 2.0 / m - 1.0
    return xi, xi1, xi2



def delta_x_max(
    z_local: float,
    H_quad: float,
    E_s: float,
    nu: float,
    DeltaK: float,
    a_v: float,
    sigma_v: float,
    u: float,
) -> float:
    """
    Implement the agreed formula with plateau for z/H > 0.5.
    """
    if z_local <= 0.0:
        return 0.0
    _safe_positive("H_quad", H_quad)
    _safe_positive("E_s", E_s)

    z_over_H = z_local / H_quad
    z_over_H_eff = min(z_over_H, 0.5)  # plateau beyond 0.5

    # shape factor
    num = (1.0 + z_over_H_eff) ** 3 * (1.0 - z_over_H_eff)
    den = z_over_H_eff if z_over_H_eff > 1e-12 else 1e-12

    shape = num / den

    return (
        (math.pi / 4.0)
        * (1.0 - nu**2)
        / E_s
        * shape
        * H_quad
        * DeltaK
        * (1.0 - a_v)
        * (sigma_v - u)
    )



def delta_x_M(
    H_quad: float,
    E_s: float,
    nu: float,
    DeltaK: float,
    a_v: float,
    sigma_v_mid: float,
    u_mid: float,
) -> float:
    """Return dx_M = dx_max at z/H = 0.5 for the quadrant."""
    z_local_mid = 0.5 * H_quad
    return delta_x_max(
        z_local=z_local_mid,
        H_quad=H_quad,
        E_s=E_s,
        nu=nu,
        DeltaK=DeltaK,
        a_v=a_v,
        sigma_v=sigma_v_mid,
        u=u_mid,
    )



def mobilization_m(dx_abs: float, dx_M: float, z_local: float, H_quad: float) -> float:
    """
    Use the agreed m formula with protections:
        dx_abs == 0   -> m = 1
        dx_abs >= dx_M -> m = M_FULL
    """
    if dx_abs <= 0.0:
        return 1.0
    if dx_M <= 0.0:
        return M_FULL
    if dx_abs >= dx_M:
        return M_FULL
    if z_local <= 0.0:
        return 1.0

    ratio = dx_abs / dx_M
    exponent = 1.0 + ratio
    base = (H_quad / z_local) if z_local > 1e-12 else 1e12

    m = (1.0 + ratio * (base ** exponent)) / (1.0 - ratio)
    return m


# ============================================================
# Task 9 — Reference-state functions
# ============================================================


def reference_K_OE(
    quadrant_type_str: QuadrantType,
    sigma_v: float,
    u: float,
    side_data: SideData,
    seismic_data: SeismicData,
) -> float:
    """
    Compute K_OE by solving constitutive problem with m = 1.
    """
    side_data = _regularize_side_data(side_data)
    xi, xi1, xi2 = xi_parameters(1.0)
    if quadrant_type_str == "active":
        result = solve_active_state(
            sigma_v=sigma_v,
            u=u,
            side_data=side_data,
            seismic_data=seismic_data,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
        )
    else:
        result = solve_passive_state(
            sigma_v=sigma_v,
            u=u,
            side_data=side_data,
            seismic_data=seismic_data,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
        )
    return result["K_XE"]



def reference_K_limit(
    quadrant_type_str: QuadrantType,
    sigma_v: float,
    u: float,
    side_data: SideData,
    seismic_data: SeismicData,
) -> float:
    """
    Compute K_AE (active) or K_PE (passive) with m = M_FULL.
    """
    side_data = _regularize_side_data(side_data)
    xi, xi1, xi2 = xi_parameters(M_FULL)
    if quadrant_type_str == "active":
        result = solve_active_state(
            sigma_v=sigma_v,
            u=u,
            side_data=side_data,
            seismic_data=seismic_data,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
        )
    else:
        result = solve_passive_state(
            sigma_v=sigma_v,
            u=u,
            side_data=side_data,
            seismic_data=seismic_data,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
        )
    return result["K_XE"]



def delta_K(quadrant_type_str: QuadrantType, K_OE: float, K_limit: float) -> float:
    """
    active : DeltaK = K_OE - K_AE
    passive: DeltaK = K_PE - K_OE
    """
    if quadrant_type_str == "active":
        return K_OE - K_limit
    if quadrant_type_str == "passive":
        return K_limit - K_OE
    raise ValueError("delta_K requires a valid quadrant_type.")


# ============================================================
# Task 10 — CUT constitutive functions
# ============================================================


def compute_A0_B1_active(
    phi_prime_deg: float,
    c_prime: float,
    xi: float,
    theta_eq_deg: float,
    a_v: float,
    sigma_v: float,
    u: float,
) -> tuple[float, float]:
    """Return A0, B1 for active region."""
    phi = math.radians(phi_prime_deg)
    sin_phi = math.sin(phi)
    tan_phi = math.tan(phi)
    theta_eq = math.radians(theta_eq_deg)
    denom = (1.0 - a_v) * (sigma_v - u)
    _safe_positive("(1-a_v)(sigma_v-u)", denom)

    A0 = ((1.0 - sin_phi) / (1.0 + sin_phi)) * (
        1.0 - xi * sin_phi + math.tan(theta_eq) * tan_phi * (2.0 + xi * (1.0 - sin_phi))
    )
    B1 = (2.0 * c_prime / denom) * math.tan(math.pi / 4.0 - phi / 2.0)
    return A0, B1



def compute_A0_B1_passive(
    phi_prime_deg: float,
    c_prime: float,
    xi: float,
    xi1: float,
    xi2: float,
    theta_eq_deg: float,
    a_v: float,
    sigma_v: float,
    u: float,
) -> tuple[float, float]:
    """Return A0, B1 for passive region."""
    phi = math.radians(phi_prime_deg)
    sin_phi = math.sin(phi)
    tan_phi = math.tan(phi)
    theta_eq = math.radians(theta_eq_deg)
    denom = (1.0 - a_v) * (sigma_v - u)
    _safe_positive("(1-a_v)(sigma_v-u)", denom)

    A0 = (((1.0 + sin_phi) / (1.0 - sin_phi)) ** xi1) * (
        1.0 + xi * sin_phi + xi2 * math.tan(theta_eq) * tan_phi * (2.0 + xi * (1.0 + sin_phi))
    )
    B1 = (2.0 * c_prime / denom) * math.tan(math.pi / 4.0 - phi / 2.0) * (
        math.tan(math.pi / 4.0 + phi / 2.0) / math.tan(math.pi / 4.0 - phi / 2.0)
    ) ** xi1
    return A0, B1



def compute_C1(A0: float, c_prime: float, phi_prime_deg: float, a_v: float, sigma_v: float, u: float) -> float:
    """Return C1 from the agreed equation."""
    phi = math.radians(phi_prime_deg)
    tan_phi = math.tan(phi)
    _safe_positive("tan(phi')", abs(tan_phi))
    denom = (1.0 - a_v) * (sigma_v - u) * tan_phi
    _safe_positive("(1-a_v)(sigma_v-u)tan(phi')", abs(denom))
    return (2.0 * c_prime / denom) + 1.0 + A0



def compute_phi_m(A0: float, B1: float, C1: float, phi_prime_deg: float, lambda_value: int) -> PhiMResult:
    """
    Solve the cubic and return phi_m and intermediates.
    This is the mathematically delicate function and should be tested in isolation.
    """
    phi = math.radians(phi_prime_deg)
    tan_phi = math.tan(phi)
    s = 2.0 * lambda_value - 1.0

    if abs(B1) <= 1e-20 or not math.isfinite(B1):
        raise ValueError(f"Invalid B1 for cubic solution: {B1}")

    e1 = (1.0 - A0) / B1
    e2 = C1 / B1
    tan2 = tan_phi ** 2

    a0 = s * (1.0 + e2 ** 2 * tan2)
    b0 = 1.0 - (2.0 * e1 * e2 + e2 ** 2) * tan2
    c0 = s * (e1 ** 2 + 2.0 * e1 * e2) * tan2
    d0 = -(e1 ** 2) * tan2

    if abs(a0) <= 1e-20:
        raise ValueError("Degenerate cubic: a0 is zero.")

    D0 = b0 ** 2 - 3.0 * a0 * c0
    D1 = 2.0 * b0 ** 3 - 9.0 * a0 * b0 * c0 + 27.0 * (a0 ** 2) * d0

    radicand = complex(D1 ** 2 - 4.0 * (D0 ** 3), 0.0)
    sqrt_term = radicand ** 0.5
    C0_complex = (0.5 * (complex(D1, 0.0) - sqrt_term)) ** (1.0 / 3.0)

    if abs(C0_complex) <= 1e-30:
        alt = (0.5 * (complex(D1, 0.0) + sqrt_term)) ** (1.0 / 3.0)
        C0_complex = alt
        if abs(C0_complex) <= 1e-30:
            raise ValueError("Invalid cubic solution: C0 is zero on both branches.")

    zeta = complex(-0.5, math.sqrt(3.0) / 2.0)
    zlam = zeta ** lambda_value
    x_complex = -(b0 + D0 / (C0_complex * zlam) + C0_complex * zlam) / (3.0 * a0)
    x_real = max(-1.0, min(1.0, x_complex.real))
    phi_m_deg = math.degrees(math.asin(x_real))

    # Numerical guard for the same cubic solution: with very small c', Cardano's
    # principal complex branch can occasionally return the extraneous root close
    # to |sin(phi_m)| = 1, producing an isolated pressure spike. If that happens,
    # solve the same cubic in depressed-cubic form and select the bounded real root
    # with the smallest |phi_m|. This does not introduce a new constitutive case;
    # it only stabilizes the root selection of the existing equation.
    if abs(phi_m_deg) > 0.95 * 90.0:
        def _real_cuberoot(value: float) -> float:
            if value >= 0.0:
                return value ** (1.0 / 3.0)
            return -((-value) ** (1.0 / 3.0))

        A = b0 / a0
        B = c0 / a0
        C = d0 / a0
        p_dep = B - A * A / 3.0
        q_dep = 2.0 * A**3 / 27.0 - A * B / 3.0 + C
        disc = (q_dep / 2.0) ** 2 + (p_dep / 3.0) ** 3
        candidates: list[float] = []

        if disc >= -1e-18:
            disc_eff = max(0.0, disc)
            y = _real_cuberoot(-q_dep / 2.0 + math.sqrt(disc_eff)) + _real_cuberoot(-q_dep / 2.0 - math.sqrt(disc_eff))
            candidates.append(y - A / 3.0)
        else:
            radius = 2.0 * math.sqrt(max(0.0, -p_dep / 3.0))
            arg_den = 2.0 * math.sqrt(max(1e-300, (-p_dep / 3.0) ** 3))
            arg = max(-1.0, min(1.0, (3.0 * q_dep / (2.0 * p_dep)) * math.sqrt(-3.0 / p_dep) if abs(p_dep) > 1e-300 else -q_dep / arg_den))
            angle = math.acos(arg)
            for k_root in range(3):
                y = radius * math.cos((angle - 2.0 * math.pi * k_root) / 3.0)
                candidates.append(y - A / 3.0)

        bounded = [max(-1.0, min(1.0, x)) for x in candidates if math.isfinite(x) and -1.0 - 1e-8 <= x <= 1.0 + 1e-8]
        if bounded:
            x_real = min(bounded, key=lambda x: abs(math.degrees(math.asin(max(-1.0, min(1.0, x))))))
            phi_m_deg = math.degrees(math.asin(x_real))

        # Last-resort numerical stabilization of the same polynomial. Matplotlib
        # already depends on NumPy, so this does not add a practical GUI dependency.
        # It is used only if the closed-form branch above still lands on the
        # extraneous |sin(phi_m)| ~= 1 root.
        if abs(phi_m_deg) > 0.95 * 90.0:
            try:
                import numpy as _np
                roots = _np.roots([a0, b0, c0, d0])
                real_roots = [float(root.real) for root in roots if abs(float(root.imag)) < 1e-7]
                bounded_np = [max(-1.0, min(1.0, x)) for x in real_roots if -1.0 - 1e-8 <= x <= 1.0 + 1e-8]
                if bounded_np:
                    x_real = min(bounded_np, key=lambda x: abs(math.degrees(math.asin(max(-1.0, min(1.0, x))))))
                    phi_m_deg = math.degrees(math.asin(x_real))
            except Exception:
                pass

    return {
        "phi_m_deg": phi_m_deg,
        "e1": e1,
        "e2": e2,
        "a0": a0,
        "b0": b0,
        "c0": c0,
        "d0": d0,
        "D0": D0,
        "D1": D1,
        "C0": C0_complex,
    }



def compute_c_m(c_prime: float, phi_m_deg: float, phi_prime_deg: float) -> float:
    """c_m = c' * tan(phi_m) / tan(phi')."""
    tan_phi_m = math.tan(math.radians(phi_m_deg))
    tan_phi_p = math.tan(math.radians(phi_prime_deg))
    if abs(tan_phi_p) <= 1e-20:
        return c_prime
    return c_prime * tan_phi_m / tan_phi_p



def compute_K_XE(
    phi_m_deg: float,
    c_m: float,
    sigma_v: float,
    u: float,
    k_v: float,
    lambda_value: int,
) -> float:
    """Return K_XE from the agreed general equation."""
    phi_m = math.radians(phi_m_deg)
    s = 2.0 * lambda_value - 1.0
    denom = (1.0 - k_v) * sigma_v - u
    _safe_positive("(1-k_v)sigma_v-u", denom)
    return (
        (1.0 - s * math.sin(phi_m)) / (1.0 + s * math.sin(phi_m))
        - s * (2.0 * c_m / denom) * math.tan(math.pi / 4.0 - s * phi_m / 2.0)
    )


# ============================================================
# Task 11 — Active/passive state solvers
# ============================================================


def solve_active_state(
    sigma_v: float,
    u: float,
    side_data: SideData,
    seismic_data: SeismicData,
    xi: float,
    xi1: float,
    xi2: float,
) -> StateSolveResult:
    """
    Active rule:
        lambda = 1 always
    Compute A0, B1, C1, phi_m, c_m, K_XE.
    """
    side_data = _regularize_side_data(side_data)
    lambda_value = 1
    A0, B1 = compute_A0_B1_active(
        phi_prime_deg=side_data.phi_prime_deg,
        c_prime=side_data.c_prime,
        xi=xi,
        theta_eq_deg=seismic_data.theta_eq_deg,
        a_v=seismic_data.a_v,
        sigma_v=sigma_v,
        u=u,
    )
    C1 = compute_C1(
        A0=A0,
        c_prime=side_data.c_prime,
        phi_prime_deg=side_data.phi_prime_deg,
        a_v=seismic_data.a_v,
        sigma_v=sigma_v,
        u=u,
    )
    phi_m = compute_phi_m(
        A0=A0,
        B1=B1,
        C1=C1,
        phi_prime_deg=side_data.phi_prime_deg,
        lambda_value=lambda_value,
    )
    c_m = compute_c_m(
        c_prime=side_data.c_prime,
        phi_m_deg=phi_m["phi_m_deg"],
        phi_prime_deg=side_data.phi_prime_deg,
    )
    K_XE = compute_K_XE(
        phi_m_deg=phi_m["phi_m_deg"],
        c_m=c_m,
        sigma_v=sigma_v,
        u=u,
        k_v=seismic_data.k_v,
        lambda_value=lambda_value,
    )
    return {
        "lambda_value": lambda_value,
        "A0": A0,
        "B1": B1,
        "C1": C1,
        "phi_m": phi_m,
        "c_m": c_m,
        "K_XE": K_XE,
    }



def solve_passive_state(
    sigma_v: float,
    u: float,
    side_data: SideData,
    seismic_data: SeismicData,
    xi: float,
    xi1: float,
    xi2: float,
) -> StateSolveResult:
    """
    Passive rule:
        try lambda = 0 first
        if K_XE >= 1 keep it
        else recompute with lambda = 1
    """
    side_data = _regularize_side_data(side_data)

    def _solve_with_lambda(lambda_value: int) -> StateSolveResult:
        A0, B1 = compute_A0_B1_passive(
            phi_prime_deg=side_data.phi_prime_deg,
            c_prime=side_data.c_prime,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
            theta_eq_deg=seismic_data.theta_eq_deg,
            a_v=seismic_data.a_v,
            sigma_v=sigma_v,
            u=u,
        )
        C1 = compute_C1(
            A0=A0,
            c_prime=side_data.c_prime,
            phi_prime_deg=side_data.phi_prime_deg,
            a_v=seismic_data.a_v,
            sigma_v=sigma_v,
            u=u,
        )
        phi_m = compute_phi_m(
            A0=A0,
            B1=B1,
            C1=C1,
            phi_prime_deg=side_data.phi_prime_deg,
            lambda_value=lambda_value,
        )
        c_m = compute_c_m(
            c_prime=side_data.c_prime,
            phi_m_deg=phi_m["phi_m_deg"],
            phi_prime_deg=side_data.phi_prime_deg,
        )
        K_XE = compute_K_XE(
            phi_m_deg=phi_m["phi_m_deg"],
            c_m=c_m,
            sigma_v=sigma_v,
            u=u,
            k_v=seismic_data.k_v,
            lambda_value=lambda_value,
        )
        return {
            "lambda_value": lambda_value,
            "A0": A0,
            "B1": B1,
            "C1": C1,
            "phi_m": phi_m,
            "c_m": c_m,
            "K_XE": K_XE,
        }

    trial0 = _solve_with_lambda(0)
    if trial0["K_XE"] >= 1.0:
        return trial0
    return _solve_with_lambda(1)


# ============================================================
# Task 12 — Slope-correction functions
# ============================================================


def slope_correction_factor(K_XE: float, K_AE: float, K_PE: float) -> float:
    """
    Return the locked slope-correction factor:

        f(K) = 1 + 1.5 * [ 3 r^2 - 2 r^3 ]

    where

        r = (K_XE - K_AE) / (K_PE - K_AE)

    The ratio is clipped to [0, 1] for numerical robustness.
    """
    denom = K_PE - K_AE
    if abs(denom) <= 1e-20:
        return 1.0
    r = (K_XE - K_AE) / denom
    r = max(0.0, min(1.0, r))
    return 1.0 + 1.5 * (3.0 * r**2 - 2.0 * r**3)



def apply_slope_correction(
    quadrant: Quadrant,
    K_XE: float,
    K_AE: float,
    K_PE: float,
    beta_deg: float,
    sigma_v: float,
    u: float,
) -> dict[str, Any]:
    """
    Effective-stress slope correction:

        sigma'_h = sigma'_v * [ K_XE + f(K) * tan(beta) ]
        sigma_h  = sigma'_h + u

    where:
        sigma'_v = sigma_v - u
    """
    sigma_v_eff = sigma_v - u
    _safe_positive("sigma'_v", sigma_v_eff)

    fK = slope_correction_factor(K_XE, K_AE, K_PE)
    sigma_h_eff_corrected = sigma_v_eff * (K_XE + fK * math.tan(math.radians(beta_deg)))
    sigma_h_corrected = sigma_h_eff_corrected + u
    return {
        "fK": fK,
        "sigma_v_eff": sigma_v_eff,
        "sigma_h_eff_corrected": sigma_h_eff_corrected,
        "sigma_h_corrected": sigma_h_corrected,
    }


# ============================================================
# Task 13 — Final pressure function
# ============================================================


def final_horizontal_pressure(quadrant_type_str: QuadrantType, sigma_h_value: float) -> float:
    """
    Active: clip negative values to zero.
    Passive: keep as-is.
    """
    if quadrant_type_str == "active":
        return max(0.0, sigma_h_value)
    return sigma_h_value


# ============================================================
# Task 14 — Main point solver
# ============================================================


def solve_point(
    z: float,
    side: SideName,
    geometry: Geometry,
    left_data: SideData,
    right_data: SideData,
    seismic_data: SeismicData,
    movement_data: MovementData,
    gamma_w: float,
) -> PointSolveResult:
    """
    Main point solver.

    Flow:
        1. classify quadrant
        2. if void -> return empty/zero result
        3. get quadrant side and type
        4. fetch side data
        5. compute local depth and quadrant height
        6. compute total vertical stress
        7. compute pore pressure
        8. compute displacements
        9. compute reference states K_OE, K_AE, K_PE
        10. compute DeltaK
        11. compute dx_max and dx_M
        12. compute m and xi parameters
        13. solve active or passive constitutive state
        14. apply slope correction
        15. apply final active clipping if needed
    """
    notes: list[str] = []
    quadrant = classify_quadrant(z, side, geometry.H_R, geometry.H_L, geometry.z_p)

    if quadrant == "void":
        return {
            "z": z,
            "side": side,
            "quadrant": quadrant,
            "quadrant_type": None,
            "z_local": None,
            "H_quad": None,
            "beta_deg": None,
            "q_real": None,
            "q_upper": None,
            "sigma_v_geo": None,
            "sigma_v_total": None,
            "u": None,
            "dx_rot": None,
            "dx_tot_signed": None,
            "dx_tot_abs": None,
            "K_OE": None,
            "K_limit": None,
            "K_AE": None,
            "K_PE": None,
            "DeltaK": None,
            "dx_max": None,
            "dx_M": None,
            "m": None,
            "xi": None,
            "xi1": None,
            "xi2": None,
            "lambda_value": None,
            "A0": None,
            "B1": None,
            "C1": None,
            "phi_m_deg": None,
            "c_m": None,
            "K_XE": None,
            "slope_factor": None,
            "sigma_h_OE": None,
            "sigma_h_AE": None,
            "sigma_h_PE": None,
            "sigma_h_limit": None,
            "sigma_h_corrected": 0.0,
            "p_h_final": 0.0,
            "notes": ["No soil exists at this point for the selected side."],
        }

    side_data = get_side_data(quadrant, left_data, right_data)
    z_local = local_depth(z, quadrant, geometry.H_R, geometry.H_L, geometry.z_p)
    H_quad = quadrant_height(quadrant, geometry.H_R, geometry.H_L, geometry.z_p)
    beta_deg = get_beta_for_quadrant(quadrant, left_data, right_data)

    vs = total_vertical_stress(
        z=z,
        quadrant=quadrant,
        geometry=geometry,
        left_data=left_data,
        right_data=right_data,
        gamma_w=gamma_w,
    )
    sigma_v_total = vs["sigma_v_total"]
    sigma_v_geo = vs["sigma_v_geo"]
    q_upper = vs["q_upper"]
    z_w_local = vs["z_w_local"]
    u = pore_pressure(z_local, z_w_local, gamma_w)

    dx_rot = rotation_displacement(z, geometry.z_p, movement_data.theta_rot_deg)
    dx_tot_signed = signed_total_displacement(movement_data.dx_trans, dx_rot)
    dx_tot_abs = absolute_total_displacement(dx_tot_signed)

    qtype = mobilized_quadrant_type(quadrant, dx_tot_signed)
    if qtype is None:
        raise ValueError("Quadrant type could not be determined.")

    sigma_v_eff = sigma_v_total - u

    # CUT equations are singular at exactly zero effective vertical stress.
    # Return a benign zero-pressure state instead of forcing a tiny artificial surcharge.
    if sigma_v_eff <= 1e-12:
        notes.append("Point skipped because effective vertical stress is zero or negative.")
        return {
            "z": z,
            "side": side,
            "quadrant": quadrant,
            "quadrant_type": qtype,
            "z_local": z_local,
            "H_quad": H_quad,
            "beta_deg": beta_deg,
            "q_real": side_data.q_real,
            "q_upper": q_upper,
            "sigma_v_geo": sigma_v_geo,
            "sigma_v_total": sigma_v_total,
            "u": u,
            "dx_rot": dx_rot,
            "dx_tot_signed": dx_tot_signed,
            "dx_tot_abs": dx_tot_abs,
            "K_OE": 0.0,
            "K_AE": 0.0,
            "K_PE": 0.0,
            "K_limit": 0.0,
            "DeltaK": 0.0,
            "dx_max": 0.0,
            "dx_M": 0.0,
            "m": 1.0,
            "xi": None,
            "xi1": None,
            "xi2": None,
            "lambda_value": None,
            "A0": None,
            "B1": None,
            "C1": None,
            "phi_m_deg": None,
            "c_m": None,
            "K_XE": 0.0,
            "slope_factor": 1.0,
            "sigma_h_OE": 0.0,
            "sigma_h_AE": 0.0,
            "sigma_h_PE": 0.0,
            "sigma_h_limit": 0.0,
            "sigma_h_corrected": 0.0,
            "p_h_final": 0.0,
            "notes": notes,
        }

    # Reference states needed both for mobilization and slope correction
    K_OE_active = reference_K_OE(
        quadrant_type_str="active",
        sigma_v=sigma_v_total,
        u=u,
        side_data=side_data,
        seismic_data=seismic_data,
    )
    K_OE_passive = reference_K_OE(
        quadrant_type_str="passive",
        sigma_v=sigma_v_total,
        u=u,
        side_data=side_data,
        seismic_data=seismic_data,
    )
    K_AE = reference_K_limit(
        quadrant_type_str="active",
        sigma_v=sigma_v_total,
        u=u,
        side_data=side_data,
        seismic_data=seismic_data,
    )
    K_PE = reference_K_limit(
        quadrant_type_str="passive",
        sigma_v=sigma_v_total,
        u=u,
        side_data=side_data,
        seismic_data=seismic_data,
    )

    # By convention use K_OE from the same quadrant type for DeltaK and reporting
    K_OE = K_OE_active if qtype == "active" else K_OE_passive
    K_limit = K_AE if qtype == "active" else K_PE
    DeltaK = delta_K(qtype, K_OE, K_limit)

    # Mobilization must be continuous along each side of the wall.
    # Therefore the displacement-mobilization depth is measured from the
    # actual ground surface of the selected side, not from the internal
    # pivot/quadrant boundary z_p. Otherwise z_local resets to zero at
    # z_p for RP/LA and creates artificial spikes at the pivot under
    # pure translation.
    side_for_mob = quadrant_side(quadrant)
    if side_for_mob is None:
        raise ValueError("Side could not be determined for mobilization.")
    z_mob = side_mobilization_depth(z, side_for_mob, geometry.H_R, geometry.H_L)
    H_mob = side_mobilization_height(side_for_mob, geometry.H_R, geometry.H_L)

    # Mid-height stress estimate for dx_M: evaluated at the mid-depth of the
    # full soil height of the selected side, using the existing vertical-stress
    # convention for whichever quadrant contains that mid-depth.
    if side_for_mob == "right":
        z_mid_global = 0.5 * geometry.H_R
    else:
        z_mid_global = (geometry.H_R - geometry.H_L) + 0.5 * geometry.H_L

    q_mid = classify_quadrant(z_mid_global, side_for_mob, geometry.H_R, geometry.H_L, geometry.z_p)
    if q_mid == "void":
        sigma_v_mid = sigma_v_total
        u_mid = u
    else:
        vs_mid = total_vertical_stress(
            z=z_mid_global,
            quadrant=q_mid,
            geometry=geometry,
            left_data=left_data,
            right_data=right_data,
            gamma_w=gamma_w,
        )
        sigma_v_mid = vs_mid["sigma_v_total"]
        u_mid = pore_pressure(vs_mid["z_local"], vs_mid["z_w_local"], gamma_w)

    dx_max = delta_x_max(
        z_local=z_mob,
        H_quad=H_mob,
        E_s=side_data.E_s,
        nu=side_data.nu,
        DeltaK=DeltaK,
        a_v=seismic_data.a_v,
        sigma_v=sigma_v_total,
        u=u,
    )
    dx_M = delta_x_M(
        H_quad=H_mob,
        E_s=side_data.E_s,
        nu=side_data.nu,
        DeltaK=DeltaK,
        a_v=seismic_data.a_v,
        sigma_v_mid=sigma_v_mid,
        u_mid=u_mid,
    )
    m = mobilization_m(dx_tot_abs, dx_M, z_mob if z_mob > 0 else 1e-9, H_mob)
    xi, xi1, xi2 = xi_parameters(m)

    if qtype == "active":
        state = solve_active_state(
            sigma_v=sigma_v_total,
            u=u,
            side_data=side_data,
            seismic_data=seismic_data,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
        )
    else:
        state = solve_passive_state(
            sigma_v=sigma_v_total,
            u=u,
            side_data=side_data,
            seismic_data=seismic_data,
            xi=xi,
            xi1=xi1,
            xi2=xi2,
        )

    sigma_curve_OE = apply_slope_correction(
        quadrant=quadrant,
        K_XE=K_OE,
        K_AE=K_AE,
        K_PE=K_PE,
        beta_deg=beta_deg,
        sigma_v=sigma_v_total,
        u=u,
    )["sigma_h_corrected"]
    sigma_curve_AE = apply_slope_correction(
        quadrant=quadrant,
        K_XE=K_AE,
        K_AE=K_AE,
        K_PE=K_PE,
        beta_deg=beta_deg,
        sigma_v=sigma_v_total,
        u=u,
    )["sigma_h_corrected"]
    sigma_curve_PE = apply_slope_correction(
        quadrant=quadrant,
        K_XE=K_PE,
        K_AE=K_AE,
        K_PE=K_PE,
        beta_deg=beta_deg,
        sigma_v=sigma_v_total,
        u=u,
    )["sigma_h_corrected"]

    slope = apply_slope_correction(
        quadrant=quadrant,
        K_XE=state["K_XE"],
        K_AE=K_AE,
        K_PE=K_PE,
        beta_deg=beta_deg,
        sigma_v=sigma_v_total,
        u=u,
    )
    sigma_h_corrected = slope["sigma_h_corrected"]
    p_h_final = final_horizontal_pressure(qtype, sigma_h_corrected)
    sigma_h_limit = sigma_curve_AE if qtype == "active" else sigma_curve_PE

    notes.append("Slope correction applied in effective stresses: sigma'_h = sigma'_v [K_XE + f(K) tan(beta)], then total sigma_h = sigma'_h + u.")

    return {
        "z": z,
        "side": side,
        "quadrant": quadrant,
        "quadrant_type": qtype,
        "z_local": z_local,
        "H_quad": H_quad,
        "beta_deg": beta_deg,
        "q_real": side_data.q_real,
        "q_upper": q_upper,
        "sigma_v_geo": sigma_v_geo,
        "sigma_v_total": sigma_v_total,
        "u": u,
        "dx_rot": dx_rot,
        "dx_tot_signed": dx_tot_signed,
        "dx_tot_abs": dx_tot_abs,
        "K_OE": K_OE,
        "K_AE": K_AE,
        "K_PE": K_PE,
        "K_limit": K_limit,
        "DeltaK": DeltaK,
        "dx_max": dx_max,
        "dx_M": dx_M,
        "m": m,
        "xi": xi,
        "xi1": xi1,
        "xi2": xi2,
        "lambda_value": state["lambda_value"],
        "A0": state["A0"],
        "B1": state["B1"],
        "C1": state["C1"],
        "phi_m_deg": state["phi_m"]["phi_m_deg"],
        "c_m": state["c_m"],
        "K_XE": state["K_XE"],
        "slope_factor": slope["fK"],
        "sigma_h_OE": sigma_curve_OE,
        "sigma_h_AE": sigma_curve_AE,
        "sigma_h_PE": sigma_curve_PE,
        "sigma_h_limit": sigma_h_limit,
        "sigma_h_corrected": sigma_h_corrected,
        "p_h_final": p_h_final,
        "notes": notes,
    }


def solve_profile(
    side: SideName,
    z_values: list[float],
    geometry: Geometry,
    left_data: SideData,
    right_data: SideData,
    seismic_data: SeismicData,
    movement_data: MovementData,
    gamma_w: float,
) -> dict[str, list[Any]]:
    """
    Run solve_point over a depth profile.
    Returns arrays/lists of outputs for plotting and post-processing.
    """
    z_values_safe = [max(float(z), _profile_epsilon(geometry.H_R)) for z in z_values]
    results = [
        solve_point(
            z=z,
            side=side,
            geometry=geometry,
            left_data=left_data,
            right_data=right_data,
            seismic_data=seismic_data,
            movement_data=movement_data,
            gamma_w=gamma_w,
        )
        for z in z_values_safe
    ]
    return {
        "z": [r["z"] for r in results],
        "quadrant": [r["quadrant"] for r in results],
        "quadrant_type": [r["quadrant_type"] for r in results],
        "sigma_v": [r["sigma_v_total"] for r in results],
        "u": [r["u"] for r in results],
        "dx_tot": [r["dx_tot_signed"] for r in results],
        "m": [r["m"] for r in results],
        "K_XE": [r["K_XE"] for r in results],
        "K_OE": [r["K_OE"] for r in results],
        "K_AE": [r["K_AE"] for r in results],
        "K_PE": [r["K_PE"] for r in results],
        "K_limit": [r["K_limit"] for r in results],
        "sigma_h_OE": [r["sigma_h_OE"] for r in results],
        "sigma_h_AE": [r["sigma_h_AE"] for r in results],
        "sigma_h_PE": [r["sigma_h_PE"] for r in results],
        "sigma_h_limit": [r["sigma_h_limit"] for r in results],
        "p_h": [r["p_h_final"] for r in results],
        "raw_results": results,
    }


# ============================================================
# Task 16 — Resultant functions
# ============================================================


def resultant_force(z_values: list[float], p_values: list[float]) -> float:
    """Numerically integrate p(z) over z."""
    if len(z_values) != len(p_values):
        raise ValueError("z_values and p_values must have the same length.")
    if len(z_values) < 2:
        return 0.0
    total = 0.0
    for i in range(len(z_values) - 1):
        dz = z_values[i + 1] - z_values[i]
        p0 = 0.0 if p_values[i] is None else p_values[i]
        p1 = 0.0 if p_values[i + 1] is None else p_values[i + 1]
        total += 0.5 * (p0 + p1) * dz
    return total



def resultant_location(z_values: list[float], p_values: list[float]) -> float:
    """Return centroid/depth of resultant line of action."""
    if len(z_values) != len(p_values):
        raise ValueError("z_values and p_values must have the same length.")
    if len(z_values) < 2:
        return 0.0
    P = resultant_force(z_values, p_values)
    if abs(P) <= 1e-20:
        return 0.0
    M = 0.0
    for i in range(len(z_values) - 1):
        dz = z_values[i + 1] - z_values[i]
        z0, z1 = z_values[i], z_values[i + 1]
        p0 = 0.0 if p_values[i] is None else p_values[i]
        p1 = 0.0 if p_values[i + 1] is None else p_values[i + 1]
        M += 0.5 * (z0 * p0 + z1 * p1) * dz
    return M / P


# ============================================================
# Minimal GUI shell
# ============================================================


class CutSolverApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("CUT_Rigid_piled_wall_homogenous")
        self.geometry("1500x900")

        self.img_run = ImageTk.PhotoImage(
            Image.open(resource_path("cut.png")).resize((40, 40))
        )

        self.img_home = ImageTk.PhotoImage(
            Image.open(resource_path("home.png")).resize((40, 40))
        )

        self.stop_requested = False

        try:
            self.state("zoomed")
        except Exception:
            self.attributes("-zoomed", True)

        self.geometry_data, self.left_default, self.right_default, self.seismic_default, self.movement_default, self.gamma_w_default = _example_setup()

        self._build_variables()
        self._build_layout()
        self._load_defaults()
        self.run_solver()
    def integrate_quadrant(self, profile, quadrant_name, force_sign, z_p):
        """Integrate signed total-pressure resultants for one quadrant.

        The pressure profile p_h is already TOTAL horizontal pressure, i.e. it
        already includes pore pressure. Therefore water is NOT added again in
        the resultants table.

        Sign convention used consistently with compute_global_resultants:
            + force = leftward force
            - force = rightward force

        Important:
            The force direction is geometric, not displacement-based.
            dx_tot affects mobilization and work only; it must not decide the
            sign of the external pressure force.

        Moment is evaluated about the pivot depth z_p:
            M = integral F_signed(z) * (z - z_p) dz

        Work is reported as magnitude in the table:
            W = integral |F_signed(z) * dx_tot(z)| dz
        """
        z = profile["z"]
        quads = profile["quadrant"]
        p = profile["p_h"]
        dx = profile["dx_tot"]

        F = 0.0
        M = 0.0
        W = 0.0
        z_used: list[float] = []

        for i in range(len(z) - 1):
            if quads[i] != quadrant_name or quads[i + 1] != quadrant_name:
                continue
            if any(v is None for v in (p[i], p[i + 1], dx[i], dx[i + 1])):
                continue

            z0 = float(z[i])
            z1 = float(z[i + 1])
            dz = z1 - z0
            if dz <= 0.0:
                continue

            p0 = float(p[i])
            p1 = float(p[i + 1])
            dx0 = float(dx[i])
            dx1 = float(dx[i + 1])

            f0 = force_sign * p0
            f1 = force_sign * p1

            F += 0.5 * (f0 + f1) * dz
            M += 0.5 * (f0 * (z0 - z_p) + f1 * (z1 - z_p)) * dz
            W += 0.5 * (abs(f0 * dx0) + abs(f1 * dx1)) * dz
            z_used.extend([z0, z1])

        z_action = z_p + M / F if abs(F) > 1e-12 else float("nan")
        z_upper = min(z_used) if z_used else float("nan")
        z_lower = max(z_used) if z_used else float("nan")

        return {
            "F": F,
            "M": M,
            "z_action": z_action,
            "z_upper": z_upper,
            "z_lower": z_lower,
            "W": W,
        }
    def integrate_left_water_above_surface(self, geometry, left_data, movement, gamma_w, n_segments: int = 200):
        """Integrate water pressure acting on the left side above the left soil surface.

        This is needed when z_w_L is above z_top_L. That water is outside the
        left soil profile (quadrant = void), so it is not included in p_h from
        solve_profile. It must be added separately to the total wall pressure
        diagram and to the resultants table.
        """
        z_top_L = geometry.H_R - geometry.H_L
        z_w = left_data.z_w
        if not (0.0 <= z_w < z_top_L):
            return None

        n = max(3, int(n_segments))
        z_vals = [z_w + (z_top_L - z_w) * i / (n - 1) for i in range(n)]
        u_vals = [gamma_w * (zz - z_w) for zz in z_vals]

        F = 0.0
        M = 0.0
        W = 0.0
        for i in range(n - 1):
            z0 = z_vals[i]
            z1 = z_vals[i + 1]
            dz = z1 - z0
            if dz <= 0.0:
                continue

            # Left-side water pushes the wall to the right under the adopted
            # table sign convention (+ leftward, - rightward).
            f0 = -u_vals[i]
            f1 = -u_vals[i + 1]

            dx0 = signed_total_displacement(
                movement.dx_trans,
                rotation_displacement(z0, geometry.z_p, movement.theta_rot_deg),
            )
            dx1 = signed_total_displacement(
                movement.dx_trans,
                rotation_displacement(z1, geometry.z_p, movement.theta_rot_deg),
            )

            F += 0.5 * (f0 + f1) * dz
            M += 0.5 * (f0 * (z0 - geometry.z_p) + f1 * (z1 - geometry.z_p)) * dz
            W += 0.5 * (abs(f0 * dx0) + abs(f1 * dx1)) * dz

        z_action = geometry.z_p + M / F if abs(F) > 1e-12 else float("nan")
        return {
            "F": F,
            "M": M,
            "z_action": z_action,
            "z_upper": z_w,
            "z_lower": z_top_L,
            "W": W,
            "z_values": z_vals,
            "p_values": [-u for u in u_vals],
        }

    # ----------------------------
    # variables
    # ----------------------------
    def _build_variables(self) -> None:
        # geometry
        self.var_H_R = tk.DoubleVar()
        self.var_H_L = tk.DoubleVar()
        self.var_z_p = tk.DoubleVar()

        # right side
        self.var_beta_R = tk.DoubleVar()
        self.var_q_R = tk.DoubleVar()
        self.var_z_w_R = tk.DoubleVar()
        self.var_gamma_R = tk.DoubleVar()
        self.var_gamma_sat_R = tk.DoubleVar()
        self.var_c_R = tk.DoubleVar()
        self.var_phi_R = tk.DoubleVar()
        self.var_E_R = tk.DoubleVar()
        self.var_nu_R = tk.DoubleVar()

        # left side
        self.var_beta_L = tk.DoubleVar()
        self.var_q_L = tk.DoubleVar()
        self.var_z_w_L = tk.DoubleVar()
        self.var_gamma_L = tk.DoubleVar()
        self.var_gamma_sat_L = tk.DoubleVar()
        self.var_c_L = tk.DoubleVar()
        self.var_phi_L = tk.DoubleVar()
        self.var_E_L = tk.DoubleVar()
        self.var_nu_L = tk.DoubleVar()

        # seismic
        self.var_a_v = tk.DoubleVar()
        self.var_k_v = tk.DoubleVar()

        # movement
        self.var_dx_trans = tk.DoubleVar()
        self.var_theta_rot = tk.DoubleVar()
        self.var_auto = tk.BooleanVar(value=False)
        self.var_auto_tol_F = tk.DoubleVar(value=10.0)
        self.var_auto_tol_M = tk.DoubleVar(value=50.0)
        self.stop_requested = False

        # global
        self.var_gamma_w = tk.DoubleVar()
        self.var_z_query = tk.DoubleVar(value=2.0)
        self.var_n_points = tk.IntVar(value=1000)

    def _load_defaults(self) -> None:
        g = self.geometry_data
        l = self.left_default
        r = self.right_default
        s = self.seismic_default
        m = self.movement_default

        self.var_H_R.set(g.H_R)
        self.var_H_L.set(g.H_L)
        self.var_z_p.set(g.z_p)

        self.var_beta_R.set(r.beta_deg)
        self.var_q_R.set(r.q_real)
        self.var_z_w_R.set(r.z_w)
        self.var_gamma_R.set(r.gamma)
        self.var_gamma_sat_R.set(r.gamma_sat)
        self.var_c_R.set(r.c_prime)
        self.var_phi_R.set(r.phi_prime_deg)
        self.var_E_R.set(r.E_s)
        self.var_nu_R.set(r.nu)

        self.var_beta_L.set(l.beta_deg)
        self.var_q_L.set(l.q_real)
        self.var_z_w_L.set(l.z_w)
        self.var_gamma_L.set(l.gamma)
        self.var_gamma_sat_L.set(l.gamma_sat)
        self.var_c_L.set(l.c_prime)
        self.var_phi_L.set(l.phi_prime_deg)
        self.var_E_L.set(l.E_s)
        self.var_nu_L.set(l.nu)

        self.var_a_v.set(s.a_v)
        self.var_k_v.set(s.k_v)

        self.var_dx_trans.set(m.dx_trans)
        self.var_theta_rot.set(m.theta_rot_deg)

        self.var_gamma_w.set(self.gamma_w_default)
        self.var_z_query.set(2.0)

    # ----------------------------
    # layout
    # ----------------------------
    def _build_layout(self) -> None:
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        left_outer = ttk.Frame(self, padding=8)
        left_outer.grid(row=0, column=0, sticky="nsw")
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        self.left_canvas = tk.Canvas(left_outer, width=265, highlightthickness=0)
        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        left_scroll = ttk.Scrollbar(left_outer, orient="vertical", command=self.left_canvas.yview)
        left_scroll.grid(row=0, column=1, sticky="ns")
        self.left_canvas.configure(yscrollcommand=left_scroll.set)

        self.left_inner = ttk.Frame(self.left_canvas)
        self.left_window = self.left_canvas.create_window((0, 0), window=self.left_inner, anchor="nw")
        self.left_inner.bind("<Configure>", lambda e: self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all")))
        self.left_canvas.bind("<Configure>", lambda e: self.left_canvas.itemconfigure(self.left_window, width=e.width))
        self.left_canvas.bind_all("<MouseWheel>", self._on_mousewheel)

        right_panel = ttk.Frame(self, padding=8)
        right_panel.grid(row=0, column=1, sticky="nsew")
        right_panel.columnconfigure(0, weight=1)
        right_panel.rowconfigure(1, weight=1)

        self._build_input_panel(self.left_inner)
        self._build_output_panel(right_panel)

    def _add_entry(self, parent: ttk.LabelFrame, row: int, label: str, variable: tk.Variable) -> None:
        existing_cols = parent.grid_size()[0]
        if existing_cols >= 2 and row == 0 and any(w.grid_info().get("row") == 0 for w in parent.winfo_children()):
            pass
        # Find next free 2-column slot on the requested row
        used_cols = {int(w.grid_info()["column"]) for w in parent.winfo_children() if int(w.grid_info().get("row", -1)) == row}
        base_col = 0
        while base_col in used_cols or (base_col + 1) in used_cols:
            base_col += 2
        ttk.Label(parent, text=label).grid(row=row, column=base_col, sticky="w", padx=4, pady=2)
        ttk.Entry(parent, textvariable=variable, width=8).grid(row=row, column=base_col + 1, sticky="ew", padx=4, pady=2)

    def _build_input_panel(self, parent: ttk.Frame) -> None:

        input_box = ttk.LabelFrame(parent, text="Input data")
        input_box.grid(row=0, column=0, columnspan=2, sticky="ew", pady=4)
        input_box.columnconfigure(0, weight=0)
        input_box.columnconfigure(1, weight=0)
        input_box.columnconfigure(2, weight=0)

        ttk.Label(input_box, text="Magnitude").grid(row=0, column=0, sticky="w", padx=4, pady=2)
        ttk.Label(input_box, text="Left side").grid(row=0, column=1, sticky="w", padx=4, pady=2)
        ttk.Label(input_box, text="Right side").grid(row=0, column=2, sticky="w", padx=4, pady=2)

        def _add_lr_entry(row: int, label: str, var_left: tk.Variable, var_right: tk.Variable) -> None:
            ttk.Label(input_box, text=label).grid(row=row, column=0, sticky="w", padx=4, pady=2)
            ttk.Entry(input_box, textvariable=var_left, width=8).grid(row=row, column=1, sticky="w", padx=4, pady=2)
            ttk.Entry(input_box, textvariable=var_right, width=8).grid(row=row, column=2, sticky="w", padx=4, pady=2)

        _add_lr_entry(1, "H (m)", self.var_H_L, self.var_H_R)
        _add_lr_entry(2, "β (deg)", self.var_beta_L, self.var_beta_R)
        _add_lr_entry(3, "q (kPa)", self.var_q_L, self.var_q_R)
        _add_lr_entry(4, "z_w (m)", self.var_z_w_L, self.var_z_w_R)
        _add_lr_entry(5, "γ (kN/m³)", self.var_gamma_L, self.var_gamma_R)
        _add_lr_entry(6, "γ_sat (kN/m³)", self.var_gamma_sat_L, self.var_gamma_sat_R)
        _add_lr_entry(7, "c' (kPa)", self.var_c_L, self.var_c_R)
        _add_lr_entry(8, "φ' (deg)", self.var_phi_L, self.var_phi_R)
        _add_lr_entry(9, "E_s (kPa)", self.var_E_L, self.var_E_R)
        _add_lr_entry(10, "ν (-)", self.var_nu_L, self.var_nu_R)

        seis = ttk.LabelFrame(parent, text="Seismic")
        seis.grid(row=1, column=0, columnspan=2, sticky="ew", pady=4)
        self._add_entry(seis, 0, "k_v = a_v (-)", self.var_a_v)
        self._add_entry(seis, 1, "k_h = a_h (-)", self.var_k_v)

        move = ttk.LabelFrame(parent, text="Movement")
        move.grid(row=2, column=0, columnspan=2, sticky="ew", pady=4)
        self._add_entry(move, 0, "z_p (m, pivot point)", self.var_z_p)
        self._add_entry(move, 1, "dx_trans (m)", self.var_dx_trans)
        self._add_entry(move, 2, "θ_rot (deg)", self.var_theta_rot)

        ttk.Checkbutton(
            move,
            text="Auto equilibrium search",
            variable=self.var_auto
        ).grid(row=3, column=0, columnspan=4, sticky="w", padx=4, pady=2)

        self._add_entry(move, 4, "tol |ΣF| (kN/m)", self.var_auto_tol_F)
        self._add_entry(move, 5, "tol |ΣM| (kNm/m)", self.var_auto_tol_M)

        misc = ttk.LabelFrame(parent, text="Run controls")
        misc.grid(row=3, column=0, columnspan=2, sticky="ew", pady=4)
        self._add_entry(misc, 0, "γ_w (kN/m³)", self.var_gamma_w)
        self._add_entry(misc, 1, "query z (m, red dot)", self.var_z_query)
        self._add_entry(misc, 2, "n profile points (-)", self.var_n_points)
        btns = ttk.Frame(parent)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)

        btns = ttk.Frame(parent)
        btns.grid(row=4, column=0, columnspan=2, sticky="ew", pady=8)

        # RUN
        tk.Button(
            btns,
            image=self.img_run,
            command=self.run_solver,
            borderwidth=0,
            bg="white",
            activebackground="white"
        ).grid(row=0, column=0, padx=6)

        # STOP
        ttk.Button(
            btns,
            text="Stop",
            command=self.request_stop
        ).grid(row=0, column=1, padx=6)

        # HOME
        tk.Button(
            btns,
            image=self.img_home,
            command=lambda: webbrowser.open("https://cut-apps.streamlit.app/"),
            borderwidth=0,
            bg="white",
            activebackground="white"
        ).grid(row=0, column=2, padx=6)

        # ABOUT (text button όπως στο v8.5)
        ttk.Button(
            btns,
            text="About",
            command=self.show_about
        ).grid(row=0, column=3, padx=6)

    def show_about(self):
        messagebox.showinfo(
            "About",
            "CUT_Rigid_piled_wall_homogenous\n"
            "Version: v1.1 (Program)\n"
            "Author: Dr Lysandros Pantelidis, Cyprus University of Technology\n\n"
            "Educational tool — no warranty. Use at your own risk. Free of charge."
        )
    
    def _build_output_panel(self, parent: ttk.Frame) -> None:
        top_bar = ttk.Frame(parent)
        top_bar.grid(row=0, column=0, sticky="ew")
        self.status_var = tk.StringVar(value="Ready")
        ttk.Label(top_bar, textvariable=self.status_var).grid(row=0, column=0, sticky="w")

        notebook = ttk.Notebook(parent)
        notebook.grid(row=1, column=0, sticky="nsew")

        tab_geom = ttk.Frame(notebook)
        tab_plots = ttk.Frame(notebook)
        tab_table = ttk.Frame(notebook)
        notebook.add(tab_geom, text="Geometry")
        notebook.add(tab_plots, text="Plots")
        tab_pressure = ttk.Frame(notebook)
        notebook.add(tab_pressure, text="Pressure diagrams")
        notebook.add(tab_table, text="Query z table")
        tab_profile = ttk.Frame(notebook)
        notebook.add(tab_profile, text="Profile table")
        tab_auto = ttk.Frame(notebook)
        notebook.add(tab_auto, text="Auto solutions")

        tab_geom.columnconfigure(0, weight=1)
        tab_geom.rowconfigure(0, weight=1)
        self.fig_geom = Figure(figsize=(8, 6), dpi=100)
        self.ax_geom = self.fig_geom.add_subplot(111)
        self.canvas_geom = FigureCanvasTkAgg(self.fig_geom, master=tab_geom)
        self.canvas_geom.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        tab_plots.columnconfigure(0, weight=1)
        tab_plots.rowconfigure(0, weight=1)

        # The plots tab is both vertically and horizontally scrollable.
        # The figure keeps a fixed large canvas size instead of being squeezed
        # to the visible tab width, so both plot columns remain readable.
        self.plots_scroll_canvas = tk.Canvas(tab_plots, highlightthickness=0)
        self.plots_scroll_canvas.grid(row=0, column=0, sticky="nsew")

        self.plots_v_scrollbar = ttk.Scrollbar(tab_plots, orient="vertical", command=self.plots_scroll_canvas.yview)
        self.plots_v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.plots_h_scrollbar = ttk.Scrollbar(tab_plots, orient="horizontal", command=self.plots_scroll_canvas.xview)
        self.plots_h_scrollbar.grid(row=1, column=0, sticky="ew")
        self.plots_scroll_canvas.configure(
            yscrollcommand=self.plots_v_scrollbar.set,
            xscrollcommand=self.plots_h_scrollbar.set,
        )

        self.plots_inner = ttk.Frame(self.plots_scroll_canvas)
        self.plots_window = self.plots_scroll_canvas.create_window((0, 0), window=self.plots_inner, anchor="nw")
        self.plots_inner.bind(
            "<Configure>",
            lambda e: self.plots_scroll_canvas.configure(scrollregion=self.plots_scroll_canvas.bbox("all")),
        )
        self.plots_scroll_canvas.bind("<Enter>", lambda e: self._bind_plots_mousewheel())
        self.plots_scroll_canvas.bind("<Leave>", lambda e: self._unbind_plots_mousewheel())

        self.fig = Figure(figsize=(18, 20), dpi=100)
        self.plot_axes = {
            "left_stress": self.fig.add_subplot(5, 2, 1),
            "right_stress": self.fig.add_subplot(5, 2, 2),
            "left_disp": self.fig.add_subplot(5, 2, 3),
            "right_disp": self.fig.add_subplot(5, 2, 4),
            "left_m": self.fig.add_subplot(5, 2, 5),
            "right_m": self.fig.add_subplot(5, 2, 6),
            "left_k": self.fig.add_subplot(5, 2, 7),
            "right_k": self.fig.add_subplot(5, 2, 8),
            "left_p": self.fig.add_subplot(5, 2, 9),
            "right_p": self.fig.add_subplot(5, 2, 10),
        }
        self.canvas = FigureCanvasTkAgg(self.fig, master=self.plots_inner)
        self.canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")

        tab_pressure.columnconfigure(0, weight=1)
        tab_pressure.rowconfigure(0, weight=1)

        # Pressure tab: vertically scrollable content. It contains the total
        # pressure diagram, the axis controls, and the resultants/work table.
        self.pressure_scroll_canvas = tk.Canvas(tab_pressure, highlightthickness=0)
        self.pressure_scroll_canvas.grid(row=0, column=0, sticky="nsew")
        self.pressure_v_scrollbar = ttk.Scrollbar(tab_pressure, orient="vertical", command=self.pressure_scroll_canvas.yview)
        self.pressure_v_scrollbar.grid(row=0, column=1, sticky="ns")
        self.pressure_scroll_canvas.configure(yscrollcommand=self.pressure_v_scrollbar.set)

        self.pressure_inner = ttk.Frame(self.pressure_scroll_canvas)
        self.pressure_window = self.pressure_scroll_canvas.create_window((0, 0), window=self.pressure_inner, anchor="nw")
        self.pressure_inner.bind(
            "<Configure>",
            lambda e: self.pressure_scroll_canvas.configure(scrollregion=self.pressure_scroll_canvas.bbox("all")),
        )
        self.pressure_scroll_canvas.bind("<Configure>", lambda e: self.pressure_scroll_canvas.itemconfigure(self.pressure_window, width=e.width))
        self.pressure_scroll_canvas.bind("<Enter>", lambda e: self.pressure_scroll_canvas.bind_all("<MouseWheel>", self._on_pressure_mousewheel))
        self.pressure_scroll_canvas.bind("<Leave>", lambda e: self.pressure_scroll_canvas.unbind_all("<MouseWheel>"))

        self.pressure_inner.columnconfigure(0, weight=1)
        self.fig_p = Figure(figsize=(10, 8), dpi=100)
        self.ax_p = self.fig_p.add_subplot(111)
        self.canvas_p = FigureCanvasTkAgg(self.fig_p, master=self.pressure_inner)
        self.canvas_p.get_tk_widget().grid(row=1, column=0, sticky="nsew")
        ctrl_frame = ttk.Frame(self.pressure_inner)
        ctrl_frame.grid(row=2, column=0, sticky="ew", pady=4)

        self.var_xmin = tk.DoubleVar()
        self.var_xmax = tk.DoubleVar()

        ttk.Label(ctrl_frame, text="min x-axis value").grid(row=0, column=0, padx=5)
        entry_xmin = ttk.Entry(ctrl_frame, textvariable=self.var_xmin, width=12)
        entry_xmin.grid(row=0, column=1, padx=5)

        ttk.Label(ctrl_frame, text="max x-axis value").grid(row=0, column=2, padx=5)
        entry_xmax = ttk.Entry(ctrl_frame, textvariable=self.var_xmax, width=12)
        entry_xmax.grid(row=0, column=3, padx=5)

        entry_xmin.bind("<Return>", lambda e: self.update_pressure_xlim())
        entry_xmax.bind("<Return>", lambda e: self.update_pressure_xlim())
        entry_xmin.bind("<FocusOut>", lambda e: self.update_pressure_xlim())
        entry_xmax.bind("<FocusOut>", lambda e: self.update_pressure_xlim())

        result_frame = ttk.Frame(self.pressure_inner)
        result_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 8))
        result_frame.columnconfigure(0, weight=1)
        ttk.Label(
            result_frame,
            text="Resultant forces, moments, points of action, and work by quadrant",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=4, pady=(0, 4))

        self.tree_res = ttk.Treeview(
            result_frame,
            columns=("side", "quad", "z_upper", "z_lower", "dir", "F", "M", "mdir", "z", "W"),
            show="headings",
            height=6,
        )

        headers = [
            ("side", "Side"),
            ("quad", "Quadrant"),
            ("z_upper", "z upper (m)"),
            ("z_lower", "z lower (m)"),
            ("dir", "Force dir."),
            ("F", "ΣF total (kN/m)"),
            ("M", "ΣM about z_p (kNm/m)"),
            ("mdir", "Moment dir."),
            ("z", "z action (m)"),
            ("W", "Work (kN·m/m)"),
        ]

        # Columns setup
        widths = {
            "side": 75, "quad": 105, "z_upper": 80, "z_lower": 80,
            "dir": 75, "F": 105, "M": 120, "mdir": 90, "z": 90, "W": 110
        }

        for col, txt in headers:
            self.tree_res.heading(col, text=txt)
            self.tree_res.column(col, width=widths[col], anchor="center", stretch=False)

        # Styling
        self.tree_res.tag_configure(
            "sum",
            background="#d9e8ff",
            font=("TkDefaultFont", 9, "bold")
        )

        # Grid
        self.tree_res.grid(row=1, column=0, sticky="nsew")

        # Vertical scrollbar
        res_scroll_y = ttk.Scrollbar(
            result_frame,
            orient="vertical",
            command=self.tree_res.yview
        )
        res_scroll_y.grid(row=1, column=1, sticky="ns")

        # Horizontal scrollbar (λείπει από πριν)
        res_scroll_x = ttk.Scrollbar(
            result_frame,
            orient="horizontal",
            command=self.tree_res.xview
        )
        res_scroll_x.grid(row=2, column=0, sticky="ew")

        # Bind scrollbars
        self.tree_res.configure(
            yscrollcommand=res_scroll_y.set,
            xscrollcommand=res_scroll_x.set
        )

        # Query z table: one compact table with left and right values side by side.
        # This replaces the old Details tab; notes are shown inside this table.
        tab_table.columnconfigure(0, weight=1)
        tab_table.rowconfigure(0, weight=1)

        query_table_frame = ttk.Frame(tab_table, padding=8)
        query_table_frame.grid(row=0, column=0, sticky="nsew")
        query_table_frame.columnconfigure(0, weight=1)
        query_table_frame.rowconfigure(1, weight=1)

        ttk.Label(
            query_table_frame,
            text="Query z results: left side and right side",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", pady=(0, 6))

        self.query_tree = ttk.Treeview(
            query_table_frame,
            columns=("quantity", "left", "right"),
            show="headings",
            height=28,
        )
        self.query_tree.heading("quantity", text="Quantity")
        self.query_tree.heading("left", text="Left")
        self.query_tree.heading("right", text="Right")
        self.query_tree.column("quantity", width=260, anchor="w", stretch=True)
        self.query_tree.column("left", width=220, anchor="center", stretch=True)
        self.query_tree.column("right", width=220, anchor="center", stretch=True)
        self.query_tree.tag_configure("section", background="#d9e8ff", font=("TkDefaultFont", 9, "bold"))
        self.query_tree.tag_configure("odd", background="#f7f7f7")
        self.query_tree.tag_configure("even", background="#ffffff")
        self.query_tree.grid(row=1, column=0, sticky="nsew")

        query_scroll_y = ttk.Scrollbar(query_table_frame, orient="vertical", command=self.query_tree.yview)
        query_scroll_y.grid(row=1, column=1, sticky="ns")
        self.query_tree.configure(yscrollcommand=query_scroll_y.set)

        # Backward-compatible alias for any old code that might still reference self.tree.
        self.tree = self.query_tree

        tab_profile.columnconfigure(0, weight=1)
        tab_profile.rowconfigure(1, weight=1)

        ttk.Label(
            tab_profile,
            text="Profile table: Left side and Right side",
            font=("TkDefaultFont", 10, "bold"),
        ).grid(row=0, column=0, sticky="w", padx=6, pady=(4, 2))

        profile_cols = (
            "z",
            "q_L", "st_L", "sv_L", "u_L", "dx_L", "m_L", "K_L", "p_L",
            "q_R", "st_R", "sv_R", "u_R", "dx_R", "m_R", "K_R", "p_R",
        )
        self.profile_tree = ttk.Treeview(tab_profile, columns=profile_cols, show="headings")

        headings = {
            "z": "z (m)",
            "q_L": "quad", "st_L": "state", "sv_L": "σv (kPa)", "u_L": "u (kPa)", "dx_L": "dx (m)", "m_L": "m (-)", "K_L": "KXE (-)", "p_L": "p (kPa)",
            "q_R": "quad", "st_R": "state", "sv_R": "σv (kPa)", "u_R": "u (kPa)", "dx_R": "dx (m)", "m_R": "m (-)", "K_R": "KXE (-)", "p_R": "p (kPa)",
        }
        widths = {
            "z": 58,
            "q_L": 52, "st_L": 48, "sv_L": 64, "u_L": 58, "dx_L": 58, "m_L": 58, "K_L": 58, "p_L": 64,
            "q_R": 52, "st_R": 48, "sv_R": 64, "u_R": 58, "dx_R": 58, "m_R": 58, "K_R": 58, "p_R": 64,
        }
        for col in profile_cols:
            self.profile_tree.heading(col, text=headings[col])
            self.profile_tree.column(col, width=widths[col], minwidth=widths[col], anchor="center", stretch=False)

        self.profile_tree.tag_configure("odd", background="#f7f7f7")
        self.profile_tree.tag_configure("even", background="#ffffff")
        self.profile_tree.grid(row=1, column=0, sticky="nsew")

        profile_scroll_y = ttk.Scrollbar(tab_profile, orient="vertical", command=self.profile_tree.yview)
        profile_scroll_y.grid(row=1, column=1, sticky="ns")
        profile_scroll_x = ttk.Scrollbar(tab_profile, orient="horizontal", command=self.profile_tree.xview)
        profile_scroll_x.grid(row=2, column=0, sticky="ew")
        self.profile_tree.configure(yscrollcommand=profile_scroll_y.set, xscrollcommand=profile_scroll_x.set)

        # Auto-solutions tables: populated only when Auto equilibrium search runs.
        tab_auto.columnconfigure(0, weight=1)
        tab_auto.rowconfigure(5, weight=1)
        self.auto_info_var = tk.StringVar(value="Run Auto equilibrium search to populate these tables.")
        ttk.Label(tab_auto, textvariable=self.auto_info_var, font=("TkDefaultFont", 10, "bold")).grid(row=0, column=0, sticky="w", padx=6, pady=(4, 2))

        ttk.Label(
            tab_auto,
            text="Best candidates summary",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=1, column=0, sticky="w", padx=6, pady=(4, 2))

        summary_cols = ("criterion", "range", "dx", "theta", "zp", "score", "W", "SF", "SM")
        self.auto_summary_tree = ttk.Treeview(tab_auto, columns=summary_cols, show="headings", height=4)
        summary_headings = {
            "criterion": "Criterion",
            "range": "Criterion range",
            "dx": "|dx| (m)",
            "theta": "θ_rot (deg)",
            "zp": "z_p (m)",
            "score": "score (-)",
            "W": "Work (kN·m/m)",
            "SF": "ΣF (kN/m)",
            "SM": "ΣM (kNm/m)",
        }
        summary_widths = {"criterion": 105, "range": 170, "dx": 95, "theta": 105, "zp": 95, "score": 95, "W": 125, "SF": 115, "SM": 125}
        for col in summary_cols:
            self.auto_summary_tree.heading(col, text=summary_headings[col])
            self.auto_summary_tree.column(col, width=summary_widths[col], anchor="center", stretch=False)
        self.auto_summary_tree.tag_configure("summary", background="#eef6ff", font=("TkDefaultFont", 9, "bold"))
        self.auto_summary_tree.grid(row=2, column=0, sticky="ew", padx=6, pady=(0, 0))

        summary_scroll_x = ttk.Scrollbar(tab_auto, orient="horizontal", command=self.auto_summary_tree.xview)
        summary_scroll_x.grid(row=3, column=0, sticky="ew", padx=6, pady=(0, 6))
        self.auto_summary_tree.configure(xscrollcommand=summary_scroll_x.set)

        ttk.Label(
            tab_auto,
            text="Accepted candidates table — click a column heading to sort",
            font=("TkDefaultFont", 9, "bold"),
        ).grid(row=4, column=0, sticky="w", padx=6, pady=(4, 2))

        auto_cols = ("rank", "dx", "theta", "zp", "W", "SF", "SM", "score")
        self.auto_tree = ttk.Treeview(tab_auto, columns=auto_cols, show="headings", height=22)
        auto_headings = {
            "rank": "#",
            "dx": "|dx| (m)",
            "theta": "θ_rot (deg)",
            "zp": "z_p (m)",
            "W": "Work (kN·m/m)",
            "SF": "ΣF (kN/m)",
            "SM": "ΣM (kNm/m)",
            "score": "score (-)",
        }
        auto_widths = {"rank": 55, "dx": 115, "theta": 120, "zp": 115, "W": 135, "SF": 120, "SM": 130, "score": 110}
        for col in auto_cols:
            self.auto_tree.heading(col, text=auto_headings[col], command=lambda c=col: self._sort_auto_tree(c))
            self.auto_tree.column(col, width=auto_widths[col], anchor="center", stretch=False)
        self.auto_tree.tag_configure("selected", background="#d9e8ff", font=("TkDefaultFont", 9, "bold"))
        self.auto_tree.tag_configure("odd", background="#f7f7f7")
        self.auto_tree.tag_configure("even", background="#ffffff")
        self.auto_tree.grid(row=5, column=0, sticky="nsew", padx=6, pady=4)
        auto_scroll_y = ttk.Scrollbar(tab_auto, orient="vertical", command=self.auto_tree.yview)
        auto_scroll_y.grid(row=5, column=1, sticky="ns")
        auto_scroll_x = ttk.Scrollbar(tab_auto, orient="horizontal", command=self.auto_tree.xview)
        auto_scroll_x.grid(row=6, column=0, sticky="ew", padx=6)
        self.auto_tree.configure(yscrollcommand=auto_scroll_y.set, xscrollcommand=auto_scroll_x.set)
        self._auto_tree_sort_reverse = {}



    # ----------------------------
    # data collection
    # ----------------------------
    def collect_inputs(self) -> tuple[Geometry, SideData, SideData, SeismicData, MovementData, float, float, int, float]:
        geometry = Geometry(
            H_R=self.var_H_R.get(),
            H_L=self.var_H_L.get(),
            z_p=self.var_z_p.get(),
        )
        if geometry.H_R <= geometry.H_L:
            raise ValueError("Geometry restriction violated: H_R must be greater than H_L.")
        if geometry.H_R <= 0.0 or geometry.H_L <= 0.0:
            raise ValueError("Geometry restriction violated: H_R and H_L must be positive.")
        if not (0.0 <= geometry.z_p <= geometry.H_R):
            raise ValueError("Geometry restriction violated: z_p must lie between 0 and H_R.")

        z_top_L = geometry.H_R - geometry.H_L
        z_w_R_input = self.var_z_w_R.get()
        z_w_L_input = self.var_z_w_L.get()

        # Water table depths are measured positive downward from the right-side
        # top reference z=0. Do not allow water above the corresponding ground
        # surface, because that creates a separate external water load outside
        # the soil profile and strongly distorts the equilibrium search.
        if z_w_R_input < 0.0:
            raise ValueError("Water level restriction violated: z_w_R cannot be above the right ground surface (z_w_R >= 0).")
        if z_w_L_input < z_top_L:
            raise ValueError(
                f"Water level restriction violated: z_w_L cannot be above the left ground surface "
                f"(z_w_L >= H_R - H_L = {z_top_L:.3f})."
            )

        right_data = SideData(
            beta_deg=self.var_beta_R.get(),
            q_real=self.var_q_R.get(),
            z_w=z_w_R_input,
            gamma=self.var_gamma_R.get(),
            gamma_sat=self.var_gamma_sat_R.get(),
            c_prime=_regularize_c_prime(self.var_c_R.get()),
            phi_prime_deg=self.var_phi_R.get(),
            E_s=self.var_E_R.get(),
            nu=self.var_nu_R.get(),
        )
        left_data = SideData(
            beta_deg=self.var_beta_L.get(),
            q_real=self.var_q_L.get(),
            z_w=z_w_L_input,
            gamma=self.var_gamma_L.get(),
            gamma_sat=self.var_gamma_sat_L.get(),
            c_prime=_regularize_c_prime(self.var_c_L.get()),
            phi_prime_deg=self.var_phi_L.get(),
            E_s=self.var_E_L.get(),
            nu=self.var_nu_L.get(),
        )
        k_v = self.var_a_v.get()
        k_h = self.var_k_v.get()
        theta_eq_deg = math.degrees(math.atan2(k_h, 1.0 - k_v))
        seismic = SeismicData(
            a_v=k_v,
            k_v=k_v,
            theta_eq_deg=theta_eq_deg,
        )
        movement = MovementData(
            dx_trans=self.var_dx_trans.get(),
            theta_rot_deg=self.var_theta_rot.get(),
        )
        gamma_w = self.var_gamma_w.get()
        z_query = self.var_z_query.get()
        n_points = max(11, int(self.var_n_points.get()))
        return geometry, left_data, right_data, seismic, movement, gamma_w, z_query, n_points, 0.0

    def _load_defaults_and_run(self) -> None:
        self._load_defaults()
        self.run_solver()

    def _on_mousewheel(self, event: tk.Event) -> None:
        try:
            self.left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _bind_plots_mousewheel(self) -> None:
        self.plots_scroll_canvas.bind_all("<MouseWheel>", self._on_plots_mousewheel)
        self.plots_scroll_canvas.bind_all("<Shift-MouseWheel>", self._on_plots_shift_mousewheel)

    def _unbind_plots_mousewheel(self) -> None:
        self.plots_scroll_canvas.unbind_all("<MouseWheel>")
        self.plots_scroll_canvas.unbind_all("<Shift-MouseWheel>")

    def _on_plots_mousewheel(self, event: tk.Event) -> None:
        try:
            self.plots_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_plots_shift_mousewheel(self, event: tk.Event) -> None:
        try:
            self.plots_scroll_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    def _on_pressure_mousewheel(self, event: tk.Event) -> None:
        try:
            self.pressure_scroll_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        except Exception:
            pass

    # ----------------------------
    # stop / interrupt control
    # ----------------------------
    def request_stop(self) -> None:
        """Request interruption of a long Auto equilibrium search."""
        self.stop_requested = True
        try:
            self.status_var.set("Stop requested — finishing current calculation step...")
            self.update_idletasks()
        except Exception:
            pass

    def _check_stop(self) -> None:
        """Process GUI events and stop the auto-search if the Stop button was pressed."""
        try:
            self.update()
        except tk.TclError:
            raise
        if self.stop_requested:
            raise KeyboardInterrupt("Auto equilibrium search stopped by user.")

    # ----------------------------
    # run/update
    # ----------------------------
    def run_solver(self) -> None:

        if not self.var_auto.get():
            self.stop_requested = False

        if self.var_auto.get():
            try:
                self.run_auto_solver()
            except KeyboardInterrupt as exc:
                self.var_auto.set(False)
                self.status_var.set(str(exc))
            finally:
                self.stop_requested = False
            return

        try:
            geometry, left_data, right_data, seismic, movement, gamma_w, z_query, n_points, k_xlim = self.collect_inputs()
            z_eps = _profile_epsilon(geometry.H_R)
            z_values = [z_eps + (geometry.H_R - z_eps) * i / (n_points - 1) for i in range(n_points)]

            profile_left = solve_profile(
                side="left",
                z_values=z_values,
                geometry=geometry,
                left_data=left_data,
                right_data=right_data,
                seismic_data=seismic,
                movement_data=movement,
                gamma_w=gamma_w,
            )
            profile_right = solve_profile(
                side="right",
                z_values=z_values,
                geometry=geometry,
                left_data=left_data,
                right_data=right_data,
                seismic_data=seismic,
                movement_data=movement,
                gamma_w=gamma_w,
            )
            point_left = solve_point(
                z=z_query,
                side="left",
                geometry=geometry,
                left_data=left_data,
                right_data=right_data,
                seismic_data=seismic,
                movement_data=movement,
                gamma_w=gamma_w,
            )
            point_right = solve_point(
                z=z_query,
                side="right",
                geometry=geometry,
                left_data=left_data,
                right_data=right_data,
                seismic_data=seismic,
                movement_data=movement,
                gamma_w=gamma_w,
            )
            self.update_tables(point_left, point_right)
            self.update_profile_table(profile_left, profile_right)
            self.update_plots(profile_left, profile_right, geometry, left_data, right_data, gamma_w)
            self.update_geometry_plot(geometry, left_data, right_data, "both", z_query, point_right)
            self.update_pressure_diagram(geometry, left_data, right_data, seismic, movement, gamma_w, n_points)
            self.status_var.set(f"Solved query z={z_query:.3f}")
        except Exception as exc:
            messagebox.showerror("Solver error", str(exc))
            self.status_var.set(f"Error: {exc}")

    def run_auto_solver(self) -> None:
        self.stop_requested = False
        """Multi-level auto search for dx_trans, theta_rot and z_p.

        Level 1: broad coarse scan over the full admissible domain to identify
                 several promising regions instead of trusting a single initial
                 guess.
        Level 2: directional/recentered adaptive moving grids around the best
                 Level-1 candidates.
        Level 3: local pattern refinement around the best result.

        Candidate selection keeps the original hierarchy:
            first practical equilibrium (small |ΣF| and |ΣM|),
            then minimum work among those candidates.
        If no practical equilibrium is found, the best approximate residual is
        shown explicitly as a non-equilibrium approximation.
        """
        try:
            geometry0, left_data, right_data, seismic, movement0, gamma_w, z_query, n_points, _ = self.collect_inputs()
        except Exception as exc:
            messagebox.showerror("Auto solver error", str(exc))
            self.status_var.set(f"Auto error: {exc}")
            return

        H = geometry0.H_R
        z_top_L = geometry0.H_R - geometry0.H_L

        # Moderate profile resolution for search speed. The final displayed
        # solution is recomputed by run_solver() with the user's n_points.
        n_search = max(81, min(181, int(n_points)))
        z_eps = _profile_epsilon(H)
        z_values = [z_eps + (H - z_eps) * i / (n_search - 1) for i in range(n_search)]

        # Absolute safety limits. These are intentionally wider than the first
        # active search box, because the Level-1 scan decides where to move.
        dx_abs_min, dx_abs_max = 0.0, max(0.50, 0.50 * H)
        th_abs_min, th_abs_max = 0.0, 12.0
        zp_abs_min, zp_abs_max = max(0.0, min(H, z_top_L)), H

        # Level-1 starts with a broad but not extreme domain. If the solution
        # tries to sit on a boundary, Level-2 may expand up to the safety limits.
        dx0_min, dx0_max = dx_abs_min, min(dx_abs_max, max(0.30 * H, 0.50))
        th0_min, th0_max = th_abs_min, min(th_abs_max, 6.0)
        zp0_min, zp0_max = zp_abs_min, zp_abs_max

        F_ref = max(1.0, right_data.gamma * H * H)
        M_ref = max(1.0, F_ref * H)
        # User-controlled absolute tolerances for accepting equilibrium candidates.
        # A candidate is accepted only if both |ΣF| and |ΣM| are within these values.
        tol_F_practical = abs(float(self.var_auto_tol_F.get()))
        tol_M_practical = abs(float(self.var_auto_tol_M.get()))
        if tol_F_practical <= 0.0:
            tol_F_practical = max(0.5, 1e-3 * F_ref)
        if tol_M_practical <= 0.0:
            tol_M_practical = max(1.0, 1e-3 * M_ref)

        all_candidates = []
        best_record = None
        best_score = float("inf")
        cache = {}
        warnings = []

        def linspace(a, b, n):
            if n <= 1 or abs(b - a) < 1e-15:
                return [0.5 * (a + b)]
            return [a + (b - a) * i / (n - 1) for i in range(n)]

        def clamp(v, lo, hi):
            return min(hi, max(lo, float(v)))

        def near(value, bound, span):
            return abs(value - bound) <= max(1e-10, 0.015 * max(abs(span), 1e-12))

        def evaluate(dx, theta_deg, zp):
            dx = clamp(dx, dx_abs_min, dx_abs_max)
            theta_deg = clamp(theta_deg, th_abs_min, th_abs_max)
            zp = clamp(zp, zp_abs_min, zp_abs_max)
            key = (round(dx, 12), round(theta_deg, 12), round(zp, 12))
            if key in cache:
                return cache[key]
            geometry = Geometry(H_R=geometry0.H_R, H_L=geometry0.H_L, z_p=zp)
            movement = MovementData(dx_trans=dx, theta_rot_deg=theta_deg)
            try:
                prof_r = solve_profile("right", z_values, geometry, left_data, right_data, seismic, movement, gamma_w)
                prof_l = solve_profile("left", z_values, geometry, left_data, right_data, seismic, movement, gamma_w)
                SF, SM, W = self.compute_global_resultants(prof_r, prof_l, geometry, left_data, movement, gamma_w)
                score = (SF / F_ref) ** 2 + (SM / M_ref) ** 2
                out = (SF, SM, W, score)
                cache[key] = out
                return out
            except Exception:
                cache[key] = None
                return None

        def make_record(dx, theta_deg, zp, out):
            SF, SM, W, score = out
            return (float(dx), float(theta_deg), float(zp), float(W), float(SF), float(SM), float(score))

        def register(dx, theta_deg, zp):
            nonlocal best_record, best_score
            dx = clamp(dx, dx_abs_min, dx_abs_max)
            theta_deg = clamp(theta_deg, th_abs_min, th_abs_max)
            zp = clamp(zp, zp_abs_min, zp_abs_max)
            out = evaluate(dx, theta_deg, zp)
            if out is None:
                return None
            rec = make_record(dx, theta_deg, zp, out)
            _, _, _, W, SF, SM, score = rec
            if abs(SF) <= tol_F_practical and abs(SM) <= tol_M_practical:
                all_candidates.append(rec)
            if score < best_score:
                best_score = score
                best_record = rec
            return rec

        def sorted_unique_records(records, limit):
            seen = set()
            out = []
            for rec in sorted(records, key=lambda r: (r[6], r[3])):
                key = (round(rec[0], 8), round(rec[1], 8), round(rec[2], 8))
                if key in seen:
                    continue
                seen.add(key)
                out.append(rec)
                if len(out) >= limit:
                    break
            return out

        # LEVEL 1 — broad coarse scan. Keep several good starting regions.
        self.status_var.set("Auto search L1: broad coarse scan...")
        self._check_stop()
        level1_records = []
        for dx in linspace(dx0_min, dx0_max, 9):
            self._check_stop()
            for theta_deg in linspace(th0_min, th0_max, 9):
                for zp in linspace(zp0_min, zp0_max, 13):
                    rec = register(dx, theta_deg, zp)
                    if rec is not None:
                        level1_records.append(rec)

        if not level1_records:
            self.status_var.set("Auto: no valid state found in Level-1 scan")
            return

        seeds = sorted_unique_records(level1_records, limit=8)

        # Add a few physically meaningful seeds around the best coarse region.
        if best_record is not None:
            dx_b, th_b, zp_b, *_ = best_record
            extra_seed_points = [
                (max(dx_abs_min, 0.25 * dx_b), th_b, zp_b),
                (dx_b, max(th_abs_min, 0.50 * th_b), zp_b),
                (dx_b, th_b, clamp(z_top_L + 0.25 * geometry0.H_L, zp_abs_min, zp_abs_max)),
                (dx_b, th_b, clamp(z_top_L + 0.75 * geometry0.H_L, zp_abs_min, zp_abs_max)),
            ]
            for dx_s, th_s, zp_s in extra_seed_points:
                rec = register(dx_s, th_s, zp_s)
                if rec is not None:
                    seeds.append(rec)
            seeds = sorted_unique_records(seeds, limit=10)

        # LEVEL 2 — adaptive moving grid around each seed.
        level2_records = []

        def adaptive_from_seed(seed, seed_index):
            dx_c, th_c, zp_c, *_ = seed
            dx_span = max((dx0_max - dx0_min) / 4.0, 0.05 * H)
            th_span = max((th0_max - th0_min) / 4.0, 0.75)
            zp_span = max((zp0_max - zp0_min) / 4.0, 0.05 * H)

            local_best = seed
            local_best_score = seed[6]

            for cycle in range(7):
                self.status_var.set(f"Auto search L2: seed {seed_index + 1}/{len(seeds)}, moving grid {cycle + 1}/7...")
                self._check_stop()

                dx_lo = clamp(dx_c - 0.5 * dx_span, dx_abs_min, dx_abs_max)
                dx_hi = clamp(dx_c + 0.5 * dx_span, dx_abs_min, dx_abs_max)
                th_lo = clamp(th_c - 0.5 * th_span, th_abs_min, th_abs_max)
                th_hi = clamp(th_c + 0.5 * th_span, th_abs_min, th_abs_max)
                zp_lo = clamp(zp_c - 0.5 * zp_span, zp_abs_min, zp_abs_max)
                zp_hi = clamp(zp_c + 0.5 * zp_span, zp_abs_min, zp_abs_max)

                cycle_records = []
                for dx in linspace(dx_lo, dx_hi, 7):
                    self._check_stop()
                    for theta_deg in linspace(th_lo, th_hi, 7):
                        for zp in linspace(zp_lo, zp_hi, 7):
                            rec = register(dx, theta_deg, zp)
                            if rec is not None:
                                cycle_records.append(rec)

                if not cycle_records:
                    break

                cycle_best = min(cycle_records, key=lambda r: (r[6], r[3]))
                if cycle_best[6] < local_best_score:
                    local_best = cycle_best
                    local_best_score = cycle_best[6]

                dx_c, th_c, zp_c = cycle_best[0], cycle_best[1], cycle_best[2]
                moved_to_boundary = False

                if near(dx_c, dx_hi, dx_hi - dx_lo) and dx_hi < dx_abs_max:
                    dx_span *= 1.25
                    dx_c = min(dx_abs_max, dx_c + 0.25 * dx_span)
                    moved_to_boundary = True
                elif near(dx_c, dx_lo, dx_hi - dx_lo) and dx_lo > dx_abs_min:
                    dx_span *= 1.25
                    dx_c = max(dx_abs_min, dx_c - 0.25 * dx_span)
                    moved_to_boundary = True

                if near(th_c, th_hi, th_hi - th_lo) and th_hi < th_abs_max:
                    th_span *= 1.25
                    th_c = min(th_abs_max, th_c + 0.25 * th_span)
                    moved_to_boundary = True
                elif near(th_c, th_lo, th_hi - th_lo) and th_lo > th_abs_min:
                    th_span *= 1.25
                    th_c = max(th_abs_min, th_c - 0.25 * th_span)
                    moved_to_boundary = True

                if near(zp_c, zp_hi, zp_hi - zp_lo) and zp_hi < zp_abs_max:
                    zp_span *= 1.25
                    zp_c = min(zp_abs_max, zp_c + 0.25 * zp_span)
                    moved_to_boundary = True
                elif near(zp_c, zp_lo, zp_hi - zp_lo) and zp_lo > zp_abs_min:
                    zp_span *= 1.25
                    zp_c = max(zp_abs_min, zp_c - 0.25 * zp_span)
                    moved_to_boundary = True

                if not moved_to_boundary:
                    dx_span *= 0.50
                    th_span *= 0.50
                    zp_span *= 0.50

                dx_span = min(dx_abs_max - dx_abs_min, max(dx_span, 1e-5 * max(1.0, H)))
                th_span = min(th_abs_max - th_abs_min, max(th_span, 1e-4))
                zp_span = min(zp_abs_max - zp_abs_min, max(zp_span, 1e-5 * max(1.0, H)))

                if dx_span < 1e-4 * max(1.0, H) and th_span < 1e-3 and zp_span < 1e-4 * max(1.0, H):
                    break

            return local_best

        for i, seed in enumerate(seeds):
            rec = adaptive_from_seed(seed, i)
            if rec is not None:
                level2_records.append(rec)

        if level2_records:
            best_level2 = min(level2_records, key=lambda r: (r[6], r[3]))
            if best_record is None or best_level2[6] < best_record[6]:
                best_record = best_level2
                best_score = best_level2[6]

        # LEVEL 3 — local pattern refinement around the best Level-2 result.
        if best_record is not None:
            dx_step = max(0.02 * H, 1e-4 * max(1.0, H))
            th_step = max(0.20, 1e-4)
            zp_step = max(0.02 * H, 1e-4 * max(1.0, H))

            for it in range(60):
                self.status_var.set(f"Auto search L3: local pattern refinement {it + 1}/60...")
                self._check_stop()

                old_score = best_score
                dx_c, th_c, zp_c, *_ = best_record
                trial_records = []

                for ddx in (-dx_step, 0.0, dx_step):
                    self._check_stop()
                    for dth in (-th_step, 0.0, th_step):
                        for dzp in (-zp_step, 0.0, zp_step):
                            if ddx == 0.0 and dth == 0.0 and dzp == 0.0:
                                continue
                            rec = register(dx_c + ddx, th_c + dth, zp_c + dzp)
                            if rec is not None:
                                trial_records.append(rec)

                if trial_records:
                    trial_best = min(trial_records, key=lambda r: (r[6], r[3]))
                    if trial_best[6] < best_score:
                        best_record = trial_best
                        best_score = trial_best[6]

                if best_score >= old_score - 1e-14:
                    dx_step *= 0.5
                    th_step *= 0.5
                    zp_step *= 0.5

                if dx_step < 1e-6 * max(1.0, H) and th_step < 1e-5 and zp_step < 1e-6 * max(1.0, H):
                    break

        def unique_candidates_by_work(records):
            seen = set()
            unique = []
            for rec in sorted(records, key=lambda r: (r[3], r[6])):
                key = (round(rec[0], 8), round(rec[1], 8), round(rec[2], 8))
                if key in seen:
                    continue
                seen.add(key)
                unique.append(rec)
            return unique

        practical_candidates = unique_candidates_by_work(all_candidates)

        if practical_candidates:
            dx, theta_deg, zp, W, SF, SM, score = practical_candidates[0]
            status = "Auto: equilibrium candidates found; minimum-work solution selected"
        elif best_record is not None:
            dx, theta_deg, zp, W, SF, SM, score = best_record
            status = "Auto: NO candidate within tolerances; best approximate state shown"
        else:
            self.status_var.set("Auto: no valid state found")
            self.update_auto_solutions_table([], None, tol_F_practical, tol_M_practical, best_record=None)
            return

        bound_warnings = []
        if near(dx, dx_abs_min, dx_abs_max - dx_abs_min):
            bound_warnings.append("dx reached lower search limit")
        if near(dx, dx_abs_max, dx_abs_max - dx_abs_min):
            bound_warnings.append("dx reached absolute max")
        if near(theta_deg, th_abs_min, th_abs_max - th_abs_min):
            bound_warnings.append("theta reached lower search limit")
        if near(theta_deg, th_abs_max, th_abs_max - th_abs_min):
            bound_warnings.append("theta reached absolute max")
        if near(zp, zp_abs_min, zp_abs_max - zp_abs_min):
            bound_warnings.append("z_p reached lower bound")
        if near(zp, zp_abs_max, zp_abs_max - zp_abs_min):
            bound_warnings.append("z_p reached upper bound")

        self.var_dx_trans.set(dx)
        self.var_theta_rot.set(theta_deg)
        self.var_z_p.set(zp)

        self.var_auto.set(False)
        self.run_solver()
        self.var_auto.set(True)

        selected_record = (dx, theta_deg, zp, W, SF, SM, score)
        self.update_auto_solutions_table(
            practical_candidates,
            selected_record,
            tol_F_practical,
            tol_M_practical,
            best_record=best_record,
        )

        unique_warnings = []
        for w in warnings + bound_warnings:
            if w not in unique_warnings:
                unique_warnings.append(w)
        warning_text = ""
        if unique_warnings:
            warning_text = " | warnings: " + "; ".join(unique_warnings[:6])

        self.status_var.set(
            f"{status} | dx={dx:.6g}, θ={theta_deg:.6g}°, z_p={zp:.6g}, "
            f"ΣF={SF:.4g}, ΣM={SM:.4g}, W={W:.4g}, score={score:.3g}, "
            f"candidates={len(practical_candidates)}, tolF={tol_F_practical:.3g}, tolM={tol_M_practical:.3g}, "
            f"L1 seeds={len(seeds)}, evals={len(cache)}{warning_text}"
        )

    def _fmt_auto(self, value: Any, kind: str = "") -> str:
        """Compact numeric formatting for auto-search outputs."""
        try:
            v = float(value)
        except Exception:
            return str(value)
        if not math.isfinite(v):
            return "—"
        if kind in ("dx", "theta", "zp"):
            return f"{v:.5f}"
        if kind == "W":
            return f"{v:.3f}"
        if kind in ("SF", "SM"):
            return f"{v:.3f}"
        if kind == "score":
            return f"{v:.3e}" if abs(v) < 1e-3 or abs(v) >= 1e4 else f"{v:.5g}"
        return f"{v:.5g}"

    def _auto_sort_value(self, text: str) -> float | str:
        try:
            return float(str(text).replace("−", "-"))
        except Exception:
            return str(text)

    def _sort_auto_tree(self, col: str) -> None:
        """Sort the large Auto solutions table by the clicked column."""
        if not hasattr(self, "auto_tree"):
            return
        reverse = self._auto_tree_sort_reverse.get(col, False)
        items = []
        for item in self.auto_tree.get_children(""):
            values = self.auto_tree.item(item, "values")
            columns = self.auto_tree["columns"]
            try:
                idx = list(columns).index(col)
                value = values[idx]
            except Exception:
                value = ""
            items.append((self._auto_sort_value(value), item))
        items.sort(key=lambda x: x[0], reverse=reverse)
        for index, (_, item) in enumerate(items):
            self.auto_tree.move(item, "", index)
        self._auto_tree_sort_reverse[col] = not reverse

    def update_auto_solutions_table(
        self,
        candidates: list[tuple[float, float, float, float, float, float, float]],
        selected_record: Optional[tuple[float, float, float, float, float, float, float]],
        tol_F: float,
        tol_M: float,
        best_record: Optional[tuple[float, float, float, float, float, float, float]] = None,
    ) -> None:
        """Display auto-search candidates and a compact best-candidates summary."""
        if not hasattr(self, "auto_tree"):
            return

        if hasattr(self, "auto_summary_tree"):
            for item in self.auto_summary_tree.get_children():
                self.auto_summary_tree.delete(item)

        for item in self.auto_tree.get_children():
            self.auto_tree.delete(item)

        selected_key = None
        if selected_record is not None:
            selected_key = (round(selected_record[0], 8), round(selected_record[1], 8), round(selected_record[2], 8))

        # The summary is based on the rows visible in the large table. If there
        # are no accepted rows, it falls back to the best approximate state.
        summary_source = candidates if candidates else ([best_record] if best_record is not None else [])
        if summary_source and hasattr(self, "auto_summary_tree"):
            def abs_sf(rec): return abs(rec[4])
            def abs_sm(rec): return abs(rec[5])
            summary_rows = [
                ("min score", "score", min(summary_source, key=lambda r: r[6]), lambda r: r[6]),
                ("min work", "work", min(summary_source, key=lambda r: r[3]), lambda r: r[3]),
                ("min |ΣF|", "|ΣF|", min(summary_source, key=abs_sf), abs_sf),
                ("min |ΣM|", "|ΣM|", min(summary_source, key=abs_sm), abs_sm),
            ]
            for label, range_label, rec, getter in summary_rows:
                vals = [getter(r) for r in summary_source]
                rng = f"{self._fmt_auto(min(vals), 'score' if range_label == 'score' else '')} – {self._fmt_auto(max(vals), 'score' if range_label == 'score' else '')}"
                dx, theta_deg, zp, W, SF, SM, score = rec
                self.auto_summary_tree.insert(
                    "",
                    "end",
                    values=(
                        label,
                        rng,
                        self._fmt_auto(abs(dx), "dx"),
                        self._fmt_auto(theta_deg, "theta"),
                        self._fmt_auto(zp, "zp"),
                        self._fmt_auto(score, "score"),
                        self._fmt_auto(W, "W"),
                        self._fmt_auto(SF, "SF"),
                        self._fmt_auto(SM, "SM"),
                    ),
                    tags=("summary",),
                )

        if candidates:
            self.auto_info_var.set(
                f"Auto solutions within |ΣF| ≤ {tol_F:g} kN/m and |ΣM| ≤ {tol_M:g} kNm/m, sorted by increasing work."
            )
            for idx, rec in enumerate(candidates, start=1):
                dx, theta_deg, zp, W, SF, SM, score = rec
                key = (round(dx, 8), round(theta_deg, 8), round(zp, 8))
                tag = "selected" if key == selected_key else ("even" if idx % 2 == 0 else "odd")
                self.auto_tree.insert(
                    "",
                    "end",
                    values=(
                        idx,
                        self._fmt_auto(abs(dx), "dx"),
                        self._fmt_auto(theta_deg, "theta"),
                        self._fmt_auto(zp, "zp"),
                        self._fmt_auto(W, "W"),
                        self._fmt_auto(SF, "SF"),
                        self._fmt_auto(SM, "SM"),
                        self._fmt_auto(score, "score"),
                    ),
                    tags=(tag,),
                )
        else:
            self.auto_info_var.set(
                f"No auto solution within |ΣF| ≤ {tol_F:g} kN/m and |ΣM| ≤ {tol_M:g} kNm/m. Best approximate state shown below."
            )
            if best_record is not None:
                dx, theta_deg, zp, W, SF, SM, score = best_record
                self.auto_tree.insert(
                    "",
                    "end",
                    values=(
                        "best",
                        self._fmt_auto(abs(dx), "dx"),
                        self._fmt_auto(theta_deg, "theta"),
                        self._fmt_auto(zp, "zp"),
                        self._fmt_auto(W, "W"),
                        self._fmt_auto(SF, "SF"),
                        self._fmt_auto(SM, "SM"),
                        self._fmt_auto(score, "score"),
                    ),
                    tags=("selected",),
                )


    def compute_global_resultants(
        self,
        prof_r: dict[str, list[Any]],
        prof_l: dict[str, list[Any]],
        geometry: Geometry,
        left_data: SideData,
        movement: MovementData,
        gamma_w: float,
    ) -> tuple[float, float, float]:
        """Return signed global ΣF, ΣM about z_p, and work magnitude.

        +F = force to the left. Right-side p_h acts leftward; left-side p_h
        acts rightward. Left water above the soil surface is added separately.
        """
        z_p = geometry.z_p

        def integrate(profile: dict[str, list[Any]], force_sign: float):
            z = profile["z"]
            p = profile["p_h"]
            dx = profile["dx_tot"]
            quads = profile["quadrant"]
            F = M = W = 0.0
            for i in range(len(z) - 1):
                if quads[i] == "void" or quads[i + 1] == "void":
                    continue
                if any(v is None for v in (p[i], p[i + 1], dx[i], dx[i + 1])):
                    continue
                z0 = float(z[i]); z1 = float(z[i + 1]); dz = z1 - z0
                if dz <= 0.0:
                    continue
                f0 = force_sign * float(p[i])
                f1 = force_sign * float(p[i + 1])
                dx0 = float(dx[i])
                dx1 = float(dx[i + 1])
                F += 0.5 * (f0 + f1) * dz
                M += 0.5 * (f0 * (z0 - z_p) + f1 * (z1 - z_p)) * dz
                W += 0.5 * (abs(f0 * dx0) + abs(f1 * dx1)) * dz
            return F, M, W

        Fr, Mr, Wr = integrate(prof_r, +1.0)
        Fl, Ml, Wl = integrate(prof_l, -1.0)
        SF = Fr + Fl
        SM = Mr + Ml
        W = Wr + Wl

        left_water = self.integrate_left_water_above_surface(geometry, left_data, movement, gamma_w)
        if left_water:
            SF += left_water["F"]
            SM += left_water["M"]
            W += left_water["W"]

        return SF, SM, W

    def update_tables(self, point_left: PointSolveResult, point_right: PointSolveResult) -> None:
        for item in self.query_tree.get_children():
            self.query_tree.delete(item)

        sections: list[tuple[str, list[str]]] = [
            ("Location & Geometry", ["quadrant", "quadrant_type", "z_local", "H_quad", "beta_deg"]),
            ("Loads & Stresses", ["q_real", "q_upper", "sigma_v_geo", "sigma_v_total", "sigma_v_eff", "u"]),
            ("Displacements", ["dx_rot", "dx_tot_signed", "dx_tot_abs", "dx_max", "dx_M"]),
            ("Mobilization", ["m", "xi", "xi1", "xi2", "lambda_value"]),
            ("Coefficients", ["K_OE", "K_limit", "DeltaK", "K_XE", "slope_factor"]),
            ("Solution Constants", ["A0", "B1", "C1", "phi_m_deg", "c_m"]),
            ("Pressures", ["sigma_h_OE", "sigma_h_AE", "sigma_h_PE", "sigma_h_limit", "sigma_h_corrected", "p_h_final"]),
            ("Notes", ["notes"]),
        ]

        row_i = 0
        for title, keys in sections:
            self.query_tree.insert("", "end", values=(title, "", ""), tags=("section",))
            for key in keys:
                tag = "even" if row_i % 2 == 0 else "odd"
                self.query_tree.insert(
                    "",
                    "end",
                    values=(self._display_name(key), self._fmt(point_left.get(key)), self._fmt(point_right.get(key))),
                    tags=(tag,),
                )
                row_i += 1

    def update_profile_table(self, profile_left: dict[str, list[Any]], profile_right: dict[str, list[Any]]) -> None:
        for item in self.profile_tree.get_children():
            self.profile_tree.delete(item)

        n = min(len(profile_left["z"]), len(profile_right["z"]))

        def val(profile: dict[str, list[Any]], key: str, i: int) -> Any:
            try:
                return profile[key][i]
            except Exception:
                return None

        for i in range(n):
            raw_L = profile_left["raw_results"][i]
            raw_R = profile_right["raw_results"][i]

            dxL = val(profile_left, "dx_tot", i)
            dxR = val(profile_right, "dx_tot", i)
            state_L = get_state_label(dxL, raw_L.get("dx_max"), raw_L.get("quadrant_type"))
            state_R = get_state_label(dxR, raw_R.get("dx_max"), raw_R.get("quadrant_type"))

            vals = (
                self._fmt_profile(val(profile_left, "z", i), "z"),

                val(profile_left, "quadrant", i),
                state_L,
                self._fmt_profile(val(profile_left, "sigma_v", i), "stress"),
                self._fmt_profile(val(profile_left, "u", i), "stress"),
                self._fmt_profile(dxL, "disp"),
                self._fmt_profile(val(profile_left, "m", i), "coef"),
                self._fmt_profile(val(profile_left, "K_XE", i), "coef"),
                self._fmt_profile(val(profile_left, "p_h", i), "stress"),

                val(profile_right, "quadrant", i),
                state_R,
                self._fmt_profile(val(profile_right, "sigma_v", i), "stress"),
                self._fmt_profile(val(profile_right, "u", i), "stress"),
                self._fmt_profile(dxR, "disp"),
                self._fmt_profile(val(profile_right, "m", i), "coef"),
                self._fmt_profile(val(profile_right, "K_XE", i), "coef"),
                self._fmt_profile(val(profile_right, "p_h", i), "stress"),
            )
            self.profile_tree.insert("", "end", values=vals, tags=("even" if i % 2 == 0 else "odd",))

    def _fmt_profile(self, value: Any, kind: str = "") -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            if not math.isfinite(value):
                return "—"
            if kind == "z":
                return f"{value:.2f}"
            if kind == "disp":
                return f"{value:.4f}"
            if kind == "coef":
                return f"{value:.3g}"
            return f"{value:.2f}"
        return str(value)

    def _fmt(self, value: Any) -> str:
        if value is None:
            return "—"
        if isinstance(value, float):
            return f"{value:.3f}"   # <-- από 6g σε 3 decimals
        return str(value)

    def _display_name(self, key: str) -> str:
        mapping = {
            "beta_deg": "β",
            "q_real": "q (kPa)",
            "q_upper": "q_upper (kPa)",
            "sigma_v_geo": "σ_v,geo (kPa)",
            "sigma_v_total": "σ_v,total (kPa)",
            "sigma_v_eff": "σ'_v (kPa)",
            "u": "u (kPa)",
            "dx_rot": "dx_rot,signed (m)",
            "dx_tot_signed": "dx_tot,signed (m)",
            "dx_tot_abs": "|dx_tot| (m)",
            "phi_m_deg": "φ_m (deg)",
            "c_m": "c_m (kPa)",
            "sigma_h_eff_corrected": "σ'_h (kPa)",
            "sigma_h_corrected": "σ_h (kPa)",
            "sigma_h_OE": "σ_OE (kPa)",
            "sigma_h_AE": "σ_AE (kPa)",
            "sigma_h_PE": "σ_PE (kPa)",
            "z_local": "z_local (m)",
            "H_quad": "H_quad (m)",
            "beta_deg": "β",
            "q_real": "q (kPa)",
            "sigma_h_limit": "σ_limit (kPa)",
            "notes": "notes",
        }
        return mapping.get(key, key)

    def update_plots(
        self,
        profile_left: dict[str, list[Any]],
        profile_right: dict[str, list[Any]],
        geometry: Geometry,
        left_data: SideData,
        right_data: SideData,
        gamma_w: float,
    ) -> None:
        z_top_L = geometry.H_R - geometry.H_L

        def prepare(profile: dict[str, list[Any]], side: SideName) -> dict[str, list[float]]:
            z = profile["z"]
            quadrants = profile["quadrant"]
            side_ground_z = z_top_L if side == "left" else 0.0
            side_water_z = left_data.z_w if side == "left" else right_data.z_w

            def visible(value: Any, quadrant: Quadrant, sign: float = 1.0) -> float:
                if quadrant == "void" or value is None:
                    return float("nan")
                return sign * float(value)

            def visible_u(value: Any, quadrant: Quadrant, z_value: float) -> float:
                if quadrant != "void" and value is not None:
                    return float(value)

                # If the water table is above the ground surface, show the water
                # pressure in the water column above the soil surface instead of
                # leaving the plot blank in the void region.
                if side_water_z < side_ground_z and side_water_z <= z_value <= side_ground_z:
                    return gamma_w * (z_value - side_water_z)
                return float("nan")

            # Displacement convention for the plot: positive movement is to the left,
            # therefore positive dx is drawn to the left of the x=0 axis.
            return {
                "z": z,
                "quadrants": quadrants,
                "ground_z": side_ground_z,
                "water_z": side_water_z,
                "sigma_v": [visible(v, q) for v, q in zip(profile["sigma_v"], quadrants)],
                "u": [visible_u(v, q, zz) for v, q, zz in zip(profile["u"], quadrants, z)],
                "dx_plot": [visible(v, q, -1.0) for v, q in zip(profile["dx_tot"], quadrants)],
                "m": [visible(v, q) for v, q in zip(profile["m"], quadrants)],
                "K_XE": [visible(v, q) for v, q in zip(profile["K_XE"], quadrants)],
                "p_h": [visible(v, q, -1.0 if side == "left" else 1.0) for v, q in zip(profile["p_h"], quadrants)],
            }

        data = {"left": prepare(profile_left, "left"), "right": prepare(profile_right, "right")}
        z_axis_max = max(
            max(data["left"]["z"]) if data["left"]["z"] else 1.0,
            max(data["right"]["z"]) if data["right"]["z"] else 1.0,
        )

        for ax in self.plot_axes.values():
            ax.clear()
            ax.grid(True, alpha=0.3)

        def add_ground_water_lines(ax: Any, d: dict[str, Any]) -> None:
            ground_z = d["ground_z"]
            water_z = d["water_z"]

            if 0.0 <= ground_z <= z_axis_max:
                ax.axhline(ground_z, color="saddlebrown", linewidth=1.3, linestyle="-", label="ground")
            if 0.0 <= water_z <= z_axis_max:
                ax.axhline(water_z, color="blue", linewidth=1.2, linestyle="--", label="water")

        def finish_axis(ax: Any) -> None:
            # Force the depth axis to start at z=0 on both sides, even where
            # the left soil surface starts deeper than the right ground surface.
            ax.set_ylim(z_axis_max, 0.0)
            ax.set_ylabel("z (m)")

        def draw_column(side: SideName) -> None:
            d = data[side]
            prefix = side
            z = d["z"]
            quadrants = d["quadrants"]

            ax = self.plot_axes[f"{prefix}_stress"]
            self._shade_quadrants(ax, z, quadrants)
            add_ground_water_lines(ax, d)
            ax.plot(d["sigma_v"], z, color="saddlebrown", linewidth=2, label="σ_v")
            ax.plot(d["u"], z, color="blue", linewidth=2, label="u")
            ax.set_title("Vertical stress / pore pressure")
            ax.legend(fontsize=8, loc="best")
            finish_axis(ax)

            ax = self.plot_axes[f"{prefix}_disp"]
            self._shade_quadrants(ax, z, quadrants)
            add_ground_water_lines(ax, d)
            ax.plot(d["dx_plot"], z, label="dx_tot")
            ax.axvline(0.0, linewidth=1.0)
            ax.set_title("Total displacement")
            ax.set_xlabel("dx_tot (m): positive left ←   0   → negative")
            ax.legend(fontsize=8, loc="best")
            finish_axis(ax)

            ax = self.plot_axes[f"{prefix}_m"]
            self._shade_quadrants(ax, z, quadrants)
            add_ground_water_lines(ax, d)
            ax.plot(d["m"], z, label="m")
            ax.set_title("Mobilization m (-)")
            ax.legend(fontsize=8, loc="best")
            finish_axis(ax)

            ax = self.plot_axes[f"{prefix}_k"]
            self._shade_quadrants(ax, z, quadrants)
            add_ground_water_lines(ax, d)
            ax.plot(d["K_XE"], z, label="K_XE")
            ax.set_title("K_XE (-)")
            ax.legend(fontsize=8, loc="best")
            finish_axis(ax)

            ax = self.plot_axes[f"{prefix}_p"]
            self._shade_quadrants(ax, z, quadrants)
            add_ground_water_lines(ax, d)
            ax.plot(d["p_h"], z, label="p_h")
            ax.fill_betweenx(z, 0, d["p_h"], alpha=0.15)
            ax.axvline(0.0, linewidth=1.0)
            ax.set_title("Horizontal pressure")
            ax.set_xlabel("horizontal pressure p_h (kPa): left shown negative / right shown positive")
            ax.legend(fontsize=8, loc="best")
            finish_axis(ax)

        draw_column("left")
        draw_column("right")

        # One common heading per column; the individual plot titles no longer
        # repeat "Left side" and "Right side".
        self.fig.text(0.26, 0.985, "Left side", ha="center", va="top", fontsize=14, fontweight="bold")
        self.fig.text(0.74, 0.985, "Right side", ha="center", va="top", fontsize=14, fontweight="bold")
        self.fig.subplots_adjust(top=0.955, bottom=0.035, left=0.07, right=0.98, hspace=0.55, wspace=0.24)
        self.canvas.draw_idle()

    def _shade_quadrants(self, ax: Any, z: list[Any], quadrants: list[Any]) -> None:
        color_map = {"RA": "#dbeafe", "RP": "#fde68a", "LP": "#fecdd3", "LA": "#bbf7d0"}
        if not z:
            return
        start_i = 0
        for i in range(1, len(z) + 1):
            if i == len(z) or quadrants[i] != quadrants[start_i]:
                q = quadrants[start_i]
                if q in color_map:
                    z0 = z[start_i]
                    z1 = z[i - 1]
                    ax.axhspan(z0, z1, color=color_map[q], alpha=0.18, lw=0)
                start_i = i


    def update_pressure_xlim(self) -> None:
        try:
            xmin = self.var_xmin.get()
            xmax = self.var_xmax.get()
            if xmin < xmax:
                self.ax_p.set_xlim(xmin, xmax)
                self.canvas_p.draw_idle()
        except Exception:
            pass

    def update_pressure_diagram(
        self,
        geometry: Geometry,
        left_data: SideData,
        right_data: SideData,
        seismic: SeismicData,
        movement: MovementData,
        gamma_w: float,
        n_points: int,
    ) -> None:
        z_eps = _profile_epsilon(geometry.H_R)
        z_values = [z_eps + (geometry.H_R - z_eps) * i / (n_points - 1) for i in range(n_points)]
        prof_r = solve_profile("right", z_values, geometry, left_data, right_data, seismic, movement, gamma_w)
        prof_l = solve_profile("left", z_values, geometry, left_data, right_data, seismic, movement, gamma_w)

        ax = self.ax_p
        ax.clear()

        z_top_L = geometry.H_R - geometry.H_L

        z_r = prof_r["z"]
        z_l = prof_l["z"]
        q_r = prof_r["quadrant"]
        q_l = prof_l["quadrant"]

        def visible_value(value: Any, quadrant: Quadrant, sign: float = 1.0) -> float:
            if quadrant == "void" or value is None:
                return float("nan")
            return sign * value

        pr = [visible_value(v, q, 1.0) for v, q in zip(prof_r["p_h"], q_r)]
        pl = [visible_value(v, q, -1.0) for v, q in zip(prof_l["p_h"], q_l)]

        left_water_above = self.integrate_left_water_above_surface(
            geometry, left_data, movement, gamma_w, n_segments=max(50, min(300, n_points // 4))
        )
        lw_z = left_water_above["z_values"] if left_water_above else []
        lw_p = left_water_above["p_values"] if left_water_above else []

        r_sig_oe = [visible_value(v, q, 1.0) for v, q in zip(prof_r["sigma_h_OE"], q_r)]
        r_sig_ae = [visible_value(v, q, 1.0) for v, q in zip(prof_r["sigma_h_AE"], q_r)]
        r_sig_pe = [visible_value(v, q, 1.0) for v, q in zip(prof_r["sigma_h_PE"], q_r)]
        l_sig_oe = [visible_value(v, q, -1.0) for v, q in zip(prof_l["sigma_h_OE"], q_l)]
        l_sig_ae = [visible_value(v, q, -1.0) for v, q in zip(prof_l["sigma_h_AE"], q_l)]
        l_sig_pe = [visible_value(v, q, -1.0) for v, q in zip(prof_l["sigma_h_PE"], q_l)]

        def _finite_values(*series: list[float]) -> list[float]:
            vals: list[float] = []
            for seq in series:
                for value in seq:
                    if isinstance(value, (int, float)) and math.isfinite(value):
                        vals.append(float(value))
            return vals

        all_x_values = _finite_values(
            pr, pl, lw_p,
            r_sig_oe, r_sig_ae, r_sig_pe,
            l_sig_oe, l_sig_ae, l_sig_pe,
        )
        negative_values = [v for v in all_x_values if v < 0.0]
        positive_values = [v for v in all_x_values if v > 0.0]
        fallback_xlim = 200.0
        x_min = 1.1 * min(negative_values) if negative_values else -fallback_xlim
        x_max = 1.1 * max(positive_values) if positive_values else fallback_xlim
        if x_min >= 0.0:
            x_min = -fallback_xlim
        if x_max <= 0.0:
            x_max = fallback_xlim

        self.var_xmin.set(x_min)
        self.var_xmax.set(x_max)

        ax.grid(True, alpha=0.3)

        # Wall kept unchanged.
        ax.plot([0, 0], [0, geometry.H_R], color="black", linewidth=3)

        # In the pressure diagram, x is pressure, not physical distance.
        # Therefore the soil and water reference levels are drawn horizontally
        # and extended to the current x-axis limits.
        ax.plot([0.0, x_max], [0.0, 0.0], color="black", linewidth=1.2, label="Right reference level (z=0)")
        ax.plot([x_min, 0.0], [z_top_L, z_top_L], color="black", linewidth=1.2, label=f"Left reference level (z={z_top_L:.2f})")

        if 0.0 <= right_data.z_w <= geometry.H_R:
            ax.plot([0.0, x_max], [right_data.z_w, right_data.z_w], color="blue", linestyle="--", linewidth=1.0, label="Right water level")
        if 0.0 <= left_data.z_w <= geometry.H_R:
            ax.plot([x_min, 0.0], [left_data.z_w, left_data.z_w], color="blue", linestyle="--", linewidth=1.0, label="Left water level")

        ax.plot(0, geometry.z_p, marker="o", markersize=5, color="black", zorder=5)
        ax.plot(0, self.var_z_query.get(), marker="o", markersize=5, color="red", zorder=6, label="query z")

        def masked_by_quadrant(vals, quads, allowed):
            return [val if quad in allowed else float("nan") for val, quad in zip(vals, quads)]

        # Computed curves: bold black, with shaded area to the y-axis.
        ax.plot(pr, z_r, color="black", linewidth=2.0, label="Right computed")
        ax.fill_betweenx(z_r, 0.0, pr, alpha=0.12)
        ax.plot(pl, z_l, color="black", linewidth=2.0, label="Left computed")
        ax.fill_betweenx(z_l, 0.0, pl, alpha=0.12)

        if left_water_above:
            ax.plot(lw_p, lw_z, color="black", linewidth=2.0, label="Left water above surface")
            ax.fill_betweenx(lw_z, 0.0, lw_p, alpha=0.12)

        ax.plot(masked_by_quadrant(r_sig_oe, q_r, {"RA", "RP"}), z_r, color="black", linestyle="--", linewidth=1.0, label="Right σOE")
        ax.plot(masked_by_quadrant(l_sig_oe, q_l, {"LP", "LA"}), z_l, color="black", linestyle="--", linewidth=1.0, label="Left σOE")

        ax.plot(masked_by_quadrant(r_sig_ae, q_r, {"RA", "RP"}), z_r, color="green", linestyle="--", linewidth=1.0, label="Right σAE")
        ax.plot(masked_by_quadrant(l_sig_ae, q_l, {"LA"}), z_l, color="green", linestyle="--", linewidth=1.0, label="Left σAE")

        ax.plot(masked_by_quadrant(r_sig_pe, q_r, {"RP"}), z_r, color="red", linestyle="--", linewidth=1.0, label="Right σPE")
        ax.plot(masked_by_quadrant(l_sig_pe, q_l, {"LP", "LA"}), z_l, color="red", linestyle="--", linewidth=1.0, label="Left σPE")

        try:
            ax.set_xlim(self.var_xmin.get(), self.var_xmax.get())
        except:
            ax.set_xlim(x_min, x_max)

        ax.invert_yaxis()
        ax.set_title("Total pressure on the wall")
        ax.set_xlabel("Horizontal pressure p_h (kPa): left shown negative, right positive")
        ax.set_ylabel("z (m)")
        ax.legend(loc="best", fontsize=8)

        self.fig_p.tight_layout()
        self.canvas_p.draw_idle()

        results = []

        # Resultants are based on p_h only, because p_h is total horizontal
        # pressure. Water is not added a second time in this table.
        # Force direction is geometric and matches compute_global_resultants:
        #   right side pressure acts leftward  -> + sign, arrow ←
        #   left side pressure acts rightward  -> - sign, arrow →
        for quad in ["RA", "RP"]:
            res = self.integrate_quadrant(prof_r, quad, +1.0, geometry.z_p)
            results.append(("Right", quad, "←", res))

        for quad in ["LP", "LA"]:
            res = self.integrate_quadrant(prof_l, quad, -1.0, geometry.z_p)
            results.append(("Left", quad, "→", res))
        if left_water_above:
            results.append(("Left", "Water above surface", "→", left_water_above))

        for row in self.tree_res.get_children():
            self.tree_res.delete(row)

        sum_F = 0.0
        sum_M = 0.0
        sum_W = 0.0

        for side, quad, direction, res in results:
            if abs(res["F"]) < 1e-6:
                continue

            sum_F += res["F"]
            sum_M += res["M"]
            sum_W += res["W"]

            self.tree_res.insert(
                "",
                "end",
                values=(
                    side,
                    quad,
                    f"{res['z_upper']:.2f}",
                    f"{res['z_lower']:.2f}",
                    direction,
                    f"{res['F']:.2f}",
                    f"{res['M']:.2f}",
                    "CW" if res['M'] > 1e-9 else ("CCW" if res['M'] < -1e-9 else "—"),
                    f"{res['z_action']:.2f}",
                    f"{abs(res['W']):.4f}",
                )
            )

        self.tree_res.insert(
            "",
            "end",
            values=(
                "Σ",
                "",
                "",
                "",
                "",
                f"{sum_F:.2f}",
                f"{sum_M:.2f}",
                "CW" if sum_M > 1e-9 else ("CCW" if sum_M < -1e-9 else "—"),
                "",
                f"{abs(sum_W):.4f}",
            ),
            tags=("sum",),
        )
    def update_geometry_plot(
        self,
        geometry: Geometry,
        left_data: SideData,
        right_data: SideData,
        side: str,
        z_query: float,
        point: PointSolveResult,
    ) -> None:
        ax = self.ax_geom
        ax.clear()

        H_R = geometry.H_R
        H_L = geometry.H_L
        z_p = geometry.z_p
        z_top_L = H_R - H_L

        x_extent = 1.5
        tan_beta_R = math.tan(math.radians(right_data.beta_deg))
        tan_beta_L = math.tan(math.radians(left_data.beta_deg))

        # z is positive downward. Positive beta is drawn uphill away from the wall,
        # therefore z decreases as distance from the wall increases.
        zR_far = -x_extent * tan_beta_R
        zL_far = z_top_L - x_extent * tan_beta_L

        # Soil regions with sloping ground surfaces.
        ax.fill([0.0, x_extent, x_extent, 0.0], [0.0, zR_far, H_R, H_R], color="#dbeafe", alpha=0.55, label="Right soil")
        ax.fill([-x_extent, 0.0, 0.0, -x_extent], [zL_far, z_top_L, H_R, H_R], color="#fecdd3", alpha=0.55, label="Left soil")

        # Wall and ground surfaces.
        ax.plot([0.0, 0.0], [0.0, H_R], color="black", linewidth=2.0, label="wall")
        ax.plot([0.0, x_extent], [0.0, zR_far], color="saddlebrown", linewidth=1.8, label="Right ground")
        ax.plot([-x_extent, 0.0], [zL_far, z_top_L], color="saddlebrown", linewidth=1.8, label="Left ground")

        # Water levels, kept horizontal on each side.
        if 0.0 <= right_data.z_w <= H_R:
            ax.plot([0.0, x_extent], [right_data.z_w, right_data.z_w], color="blue", linestyle="--", linewidth=1.2, label="z_w_R")
        if z_top_L <= left_data.z_w <= H_R:
            ax.plot([-x_extent, 0.0], [left_data.z_w, left_data.z_w], color="blue", linestyle="--", linewidth=1.2, label="z_w_L")

        # Surface surcharge indication: two red lines parallel to the ground surface,
        # drawn 0.5 m and 0.25 m above it when q_R/q_L is positive.
        load_offset = 0.5
        load_offset2 = 0.25

        # Right side
        if right_data.q_real > 0.0:
            qR_x = [0.0, x_extent]

            # κύρια γραμμή
            qR_z = [-load_offset, zR_far - load_offset]
            ax.plot(qR_x, qR_z, color="red", linewidth=1.6, label="q_R")

            # δεύτερη γραμμή
            qR_z2 = [-load_offset2, zR_far - load_offset2]
            ax.plot(qR_x, qR_z2, color="red", linewidth=1.0)

            # label
            ax.text(
                0.5 * x_extent,
                0.5 * (qR_z[0] + qR_z[1]) - 0.08,
                f"q_R = {right_data.q_real:g}",
                color="red",
                ha="center",
                va="bottom",
                fontsize=9
            )

        # Left side
        if left_data.q_real > 0.0:
            qL_x = [-x_extent, 0.0]

            # κύρια γραμμή
            qL_z = [zL_far - load_offset, z_top_L - load_offset]
            ax.plot(qL_x, qL_z, color="red", linewidth=1.6, label="q_L")

            # δεύτερη γραμμή
            qL_z2 = [zL_far - load_offset2, z_top_L - load_offset2]
            ax.plot(qL_x, qL_z2, color="red", linewidth=1.0)

            # label
            ax.text(
                -0.5 * x_extent,
                0.5 * (qL_z[0] + qL_z[1]) - 0.08,
                f"q_L = {left_data.q_real:g}",
                color="red",
                ha="center",
                va="bottom",
                fontsize=9
            )
    
        # Markers only: black pivot point and red query point.
        ax.plot(0.0, z_p, marker="o", markersize=7, color="black", zorder=6, label="pivot")
        ax.plot(0.0, z_query, marker="o", markersize=6, color="red", zorder=6, label="query z")

        ax.text(0.55, 0.5 * min(z_p, H_R), "RA", ha="center", va="center", fontsize=12)
        ax.text(0.55, 0.5 * (max(z_p, 0.0) + H_R), "RP", ha="center", va="center", fontsize=12)
        if z_p > z_top_L:
            ax.text(-0.55, 0.5 * (z_top_L + z_p), "LP", ha="center", va="center", fontsize=12)
        ax.text(-0.55, 0.5 * (max(z_top_L, z_p) + H_R), "LA", ha="center", va="center", fontsize=12)

        y_min_candidates = [-0.5, zR_far, zL_far, right_data.z_w if 0.0 <= right_data.z_w <= H_R else 0.0]
        if right_data.q_real > 0.0:
            y_min_candidates.extend([-load_offset, zR_far - load_offset])
        if left_data.q_real > 0.0:
            y_min_candidates.extend([zL_far - load_offset, z_top_L - load_offset])
        y_min = min(y_min_candidates)
        y_max = H_R + 0.5
        ax.set_xlim(-x_extent - 0.2, x_extent + 0.2)
        ax.set_ylim(y_max, y_min - 0.2)
        ax.set_xticks([])
        ax.set_ylabel("z (m)")
        # No title in this tab; the drawing itself is self-explanatory.
        ax.grid(True, alpha=0.2)
        ax.legend(loc="best", fontsize=8)
        self.fig_geom.tight_layout()
        self.canvas_geom.draw_idle()


# ============================================================
# Optional smoke-test entry point
# ============================================================


def _example_setup() -> tuple[Geometry, SideData, SideData, SeismicData, MovementData, float]:
    """Minimal example values for future smoke tests."""
    geometry = Geometry(H_R=10.0, H_L=7.0, z_p=4.0)
    right_data = SideData(
        beta_deg=5.0,
        q_real=20.0,
        z_w=3.0,
        gamma=18.0,
        gamma_sat=20.0,
        c_prime=5.0,
        phi_prime_deg=30.0,
        E_s=20000.0,
        nu=0.30,
    )
    left_data = SideData(
        beta_deg=3.0,
        q_real=10.0,
        z_w=3.0,
        gamma=17.5,
        gamma_sat=19.5,
        c_prime=4.0,
        phi_prime_deg=28.0,
        E_s=18000.0,
        nu=0.32,
    )
    seismic = SeismicData(a_v=0.0, k_v=0.0, theta_eq_deg=0.0)
    movement = MovementData(dx_trans=0.01, theta_rot_deg=0.2)
    gamma_w = 9.81
    return geometry, left_data, right_data, seismic, movement, gamma_w


if __name__ == "__main__":
    app = CutSolverApp()
    app.mainloop()
