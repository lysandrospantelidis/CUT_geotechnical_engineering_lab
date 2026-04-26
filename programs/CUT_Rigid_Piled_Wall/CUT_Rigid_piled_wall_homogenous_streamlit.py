# CUT_Rigid_piled_wall_homogenous_streamlit.py
from __future__ import annotations

import os
import math
from dataclasses import dataclass
from typing import Literal, Optional, TypedDict, Any

import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt


def resource_path(relative_path: str) -> str:
    base_path = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_path, relative_path)

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




APP_NAME = "CUT_Rigid_piled_wall_homogenous"
HOME_URL = "https://cut-apps.streamlit.app/"


def _example_setup() -> tuple[Geometry, SideData, SideData, SeismicData, MovementData, float]:
    geometry = Geometry(H_R=10.0, H_L=7.0, z_p=4.0)
    right_data = SideData(5.0, 20.0, 3.0, 18.0, 20.0, 5.0, 30.0, 20000.0, 0.30)
    left_data = SideData(3.0, 10.0, 3.0, 17.5, 19.5, 4.0, 28.0, 18000.0, 0.32)
    seismic = SeismicData(a_v=0.0, k_v=0.0, theta_eq_deg=0.0)
    movement = MovementData(dx_trans=0.01, theta_rot_deg=0.2)
    gamma_w = 9.81
    return geometry, left_data, right_data, seismic, movement, gamma_w

def integrate_left_water_above_surface(geometry: Geometry, left_data: SideData, movement: MovementData, gamma_w: float, n_segments: int = 200):
    z_top_L = geometry.H_R - geometry.H_L
    z_w = left_data.z_w
    if not (0.0 <= z_w < z_top_L):
        return None
    n = max(3, int(n_segments))
    z_vals = [z_w + (z_top_L - z_w) * i / (n - 1) for i in range(n)]
    u_vals = [gamma_w * (zz - z_w) for zz in z_vals]
    F = M = W = 0.0
    for i in range(n - 1):
        z0, z1 = z_vals[i], z_vals[i + 1]
        dz = z1 - z0
        if dz <= 0.0:
            continue
        f0, f1 = -u_vals[i], -u_vals[i + 1]
        dx0 = signed_total_displacement(movement.dx_trans, rotation_displacement(z0, geometry.z_p, movement.theta_rot_deg))
        dx1 = signed_total_displacement(movement.dx_trans, rotation_displacement(z1, geometry.z_p, movement.theta_rot_deg))
        F += 0.5 * (f0 + f1) * dz
        M += 0.5 * (f0 * (z0 - geometry.z_p) + f1 * (z1 - geometry.z_p)) * dz
        W += 0.5 * (abs(f0 * dx0) + abs(f1 * dx1)) * dz
    z_action = geometry.z_p + M / F if abs(F) > 1e-12 else float("nan")
    return {"F": F, "M": M, "z_action": z_action, "z_upper": z_w, "z_lower": z_top_L, "W": W, "z_values": z_vals, "p_values": [-u for u in u_vals]}


def compute_global_resultants(prof_r, prof_l, geometry: Geometry, left_data: SideData, movement: MovementData, gamma_w: float):
    z_p = geometry.z_p
    def integrate(profile, force_sign: float):
        z, p, dx, quads = profile["z"], profile["p_h"], profile["dx_tot"], profile["quadrant"]
        F = M = W = 0.0
        for i in range(len(z) - 1):
            if quads[i] == "void" or quads[i + 1] == "void":
                continue
            if any(v is None for v in (p[i], p[i + 1], dx[i], dx[i + 1])):
                continue
            z0, z1 = float(z[i]), float(z[i + 1])
            dz = z1 - z0
            if dz <= 0.0:
                continue
            f0, f1 = force_sign * float(p[i]), force_sign * float(p[i + 1])
            dx0, dx1 = float(dx[i]), float(dx[i + 1])
            F += 0.5 * (f0 + f1) * dz
            M += 0.5 * (f0 * (z0 - z_p) + f1 * (z1 - z_p)) * dz
            W += 0.5 * (abs(f0 * dx0) + abs(f1 * dx1)) * dz
        return F, M, W
    Fr, Mr, Wr = integrate(prof_r, +1.0)
    Fl, Ml, Wl = integrate(prof_l, -1.0)
    SF, SM, W = Fr + Fl, Mr + Ml, Wr + Wl
    lw = integrate_left_water_above_surface(geometry, left_data, movement, gamma_w)
    if lw:
        SF += lw["F"]; SM += lw["M"]; W += lw["W"]
    return SF, SM, W


def _fmt_float(x):
    try:
        return f"{float(x):.4g}"
    except Exception:
        return x


def profile_dataframe(profile_left, profile_right) -> pd.DataFrame:
    rows = []
    n = min(len(profile_left["z"]), len(profile_right["z"]))
    for i in range(n):
        rows.append({
            "z (m)": profile_left["z"][i],
            "L quad": profile_left["quadrant"][i],
            "L state": get_state_label(profile_left["dx_tot"][i], profile_left["raw_results"][i].get("dx_max"), profile_left["raw_results"][i].get("quadrant_type")),
            "L σv": profile_left["sigma_v"][i],
            "L u": profile_left["u"][i],
            "L dx": profile_left["dx_tot"][i],
            "L m": profile_left["m"][i],
            "L KXE": profile_left["K_XE"][i],
            "L p": profile_left["p_h"][i],
            "R quad": profile_right["quadrant"][i],
            "R state": get_state_label(profile_right["dx_tot"][i], profile_right["raw_results"][i].get("dx_max"), profile_right["raw_results"][i].get("quadrant_type")),
            "R σv": profile_right["sigma_v"][i],
            "R u": profile_right["u"][i],
            "R dx": profile_right["dx_tot"][i],
            "R m": profile_right["m"][i],
            "R KXE": profile_right["K_XE"][i],
            "R p": profile_right["p_h"][i],
        })
    return pd.DataFrame(rows)




def _img_data_uri(filename: str) -> str:
    import base64
    path = resource_path(filename)
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("ascii")
    return f"data:image/png;base64,{data}"


def image_link_button(filename: str, href: str, width: int = 58, title: str = "") -> None:
    src = _img_data_uri(filename)
    st.markdown(
        f'<a href="{href}" title="{title}" target="_self">'
        f'<img src="{src}" style="width:{width}px; height:{width}px; object-fit:contain; cursor:pointer; border:0;" />'
        f'</a>',
        unsafe_allow_html=True,
    )


def plot_geometry(geometry: Geometry, left_data: SideData, right_data: SideData, z_query: float):
    fig, ax = plt.subplots(figsize=(8, 6))
    H_R, H_L, z_p = geometry.H_R, geometry.H_L, geometry.z_p
    z_top_L = H_R - H_L
    x_extent = 1.5
    zR_far = -x_extent * math.tan(math.radians(right_data.beta_deg))
    zL_far = z_top_L - x_extent * math.tan(math.radians(left_data.beta_deg))

    ax.fill([0, x_extent, x_extent, 0], [0, zR_far, H_R, H_R], color="#dbeafe", alpha=0.55, label="Right soil")
    ax.fill([-x_extent, 0, 0, -x_extent], [zL_far, z_top_L, H_R, H_R], color="#fecdd3", alpha=0.55, label="Left soil")
    ax.plot([0, 0], [0, H_R], color="black", linewidth=2.4, label="wall")
    ax.plot([0, x_extent], [0, zR_far], color="saddlebrown", linewidth=1.8, label="Right ground")
    ax.plot([-x_extent, 0], [zL_far, z_top_L], color="saddlebrown", linewidth=1.8, label="Left ground")

    if 0 <= right_data.z_w <= H_R:
        ax.plot([0, x_extent], [right_data.z_w, right_data.z_w], color="blue", linestyle="--", linewidth=1.2, label="z_w_R")
    if z_top_L <= left_data.z_w <= H_R:
        ax.plot([-x_extent, 0], [left_data.z_w, left_data.z_w], color="blue", linestyle="--", linewidth=1.2, label="z_w_L")

    load_offset, load_offset2 = 0.5, 0.25
    if right_data.q_real > 0.0:
        qR_x = [0.0, x_extent]
        qR_z = [-load_offset, zR_far - load_offset]
        qR_z2 = [-load_offset2, zR_far - load_offset2]
        ax.plot(qR_x, qR_z, color="red", linewidth=1.6, label="q_R")
        ax.plot(qR_x, qR_z2, color="red", linewidth=1.0)
        ax.text(0.5 * x_extent, 0.5 * (qR_z[0] + qR_z[1]) - 0.08, f"q_R = {right_data.q_real:g}", color="red", ha="center", va="bottom", fontsize=9)
    if left_data.q_real > 0.0:
        qL_x = [-x_extent, 0.0]
        qL_z = [zL_far - load_offset, z_top_L - load_offset]
        qL_z2 = [zL_far - load_offset2, z_top_L - load_offset2]
        ax.plot(qL_x, qL_z, color="red", linewidth=1.6, label="q_L")
        ax.plot(qL_x, qL_z2, color="red", linewidth=1.0)
        ax.text(-0.5 * x_extent, 0.5 * (qL_z[0] + qL_z[1]) - 0.08, f"q_L = {left_data.q_real:g}", color="red", ha="center", va="bottom", fontsize=9)

    ax.plot(0, z_p, "o", color="black", markersize=7, label="pivot")
    ax.plot(0, z_query, "o", color="red", markersize=6, label="query z")
    ax.text(0.55, 0.5 * min(z_p, H_R), "RA", ha="center", va="center", fontsize=12)
    ax.text(0.55, 0.5 * (max(z_p, 0) + H_R), "RP", ha="center", va="center", fontsize=12)
    if z_p > z_top_L:
        ax.text(-0.55, 0.5 * (z_top_L + z_p), "LP", ha="center", va="center", fontsize=12)
    ax.text(-0.55, 0.5 * (max(z_top_L, z_p) + H_R), "LA", ha="center", va="center", fontsize=12)
    y_min_candidates = [-0.5, zR_far, zL_far]
    if right_data.q_real > 0.0: y_min_candidates.extend([-load_offset, zR_far - load_offset])
    if left_data.q_real > 0.0: y_min_candidates.extend([zL_far - load_offset, z_top_L - load_offset])
    ax.set_xlim(-x_extent - 0.2, x_extent + 0.2)
    ax.set_ylim(H_R + 0.5, min(y_min_candidates) - 0.2)
    ax.set_xticks([])
    ax.set_ylabel("z (m)")
    ax.grid(True, alpha=0.25)
    ax.legend(fontsize=8, loc="best")
    fig.tight_layout()
    return fig


def _visible_series(profile, key, sign=1.0):
    return [float("nan") if q == "void" or v is None else sign * float(v) for v, q in zip(profile[key], profile["quadrant"])]


def plot_pressure(profile_left, profile_right, geometry: Geometry, left_data: SideData, right_data: SideData, movement: MovementData, gamma_w: float):
    fig, ax = plt.subplots(figsize=(8, 9))
    z_top_L = geometry.H_R - geometry.H_L
    z_r, z_l = profile_right["z"], profile_left["z"]
    q_r, q_l = profile_right["quadrant"], profile_left["quadrant"]
    pr = _visible_series(profile_right, "p_h", 1.0)
    pl = _visible_series(profile_left, "p_h", -1.0)
    r_oe = _visible_series(profile_right, "sigma_h_OE", 1.0)
    r_ae = _visible_series(profile_right, "sigma_h_AE", 1.0)
    r_pe = _visible_series(profile_right, "sigma_h_PE", 1.0)
    l_oe = _visible_series(profile_left, "sigma_h_OE", -1.0)
    l_ae = _visible_series(profile_left, "sigma_h_AE", -1.0)
    l_pe = _visible_series(profile_left, "sigma_h_PE", -1.0)

    lw = integrate_left_water_above_surface(geometry, left_data, movement, gamma_w)
    lw_p = lw["p_values"] if lw else []
    vals = [v for seq in [pr, pl, r_oe, r_ae, r_pe, l_oe, l_ae, l_pe, lw_p] for v in seq if isinstance(v, (int, float)) and math.isfinite(v)]
    xmax = max([200.0] + [abs(v) * 1.15 for v in vals])

    ax.plot([0, 0], [0, geometry.H_R], color="black", linewidth=3)
    ax.plot([0, xmax], [0, 0], color="black", linewidth=1.2, label="Right reference level")
    ax.plot([-xmax, 0], [z_top_L, z_top_L], color="black", linewidth=1.2, label="Left reference level")
    if 0 <= right_data.z_w <= geometry.H_R:
        ax.plot([0, xmax], [right_data.z_w, right_data.z_w], color="blue", linestyle="--", linewidth=1.0, label="Right water level")
    if 0 <= left_data.z_w <= geometry.H_R:
        ax.plot([-xmax, 0], [left_data.z_w, left_data.z_w], color="blue", linestyle="--", linewidth=1.0, label="Left water level")

    ax.plot(pr, z_r, color="black", linewidth=2, label="Right computed")
    ax.fill_betweenx(z_r, 0, pr, alpha=0.12)
    ax.plot(pl, z_l, color="black", linewidth=2, label="Left computed")
    ax.fill_betweenx(z_l, 0, pl, alpha=0.12)
    if lw:
        ax.plot(lw["p_values"], lw["z_values"], color="black", linewidth=2, label="Left water above surface")
        ax.fill_betweenx(lw["z_values"], 0, lw["p_values"], alpha=0.12)

    def masked(vals, quads, allowed):
        return [v if q in allowed else float("nan") for v, q in zip(vals, quads)]
    ax.plot(masked(r_oe, q_r, {"RA", "RP"}), z_r, color="black", linestyle="--", linewidth=1.0, label="Right σOE")
    ax.plot(masked(l_oe, q_l, {"LP", "LA"}), z_l, color="black", linestyle="--", linewidth=1.0, label="Left σOE")
    ax.plot(masked(r_ae, q_r, {"RA", "RP"}), z_r, color="green", linestyle="--", linewidth=1.0, label="Right σAE")
    ax.plot(masked(l_ae, q_l, {"LA"}), z_l, color="green", linestyle="--", linewidth=1.0, label="Left σAE")
    ax.plot(masked(r_pe, q_r, {"RP"}), z_r, color="red", linestyle="--", linewidth=1.0, label="Right σPE")
    ax.plot(masked(l_pe, q_l, {"LP", "LA"}), z_l, color="red", linestyle="--", linewidth=1.0, label="Left σPE")

    ax.plot(0, geometry.z_p, "o", color="black", zorder=5)
    ax.set_xlim(-xmax, xmax)
    ax.invert_yaxis()
    ax.set_xlabel("Horizontal pressure p_h (kPa): left negative, right positive")
    ax.set_ylabel("z (m)")
    ax.set_title("Total pressure on the wall")
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7, loc="best")
    fig.tight_layout()
    return fig


def plot_all_profiles(profile_left, profile_right, geometry: Geometry, left_data: SideData, right_data: SideData, gamma_w: float):
    fig, axes = plt.subplots(5, 2, figsize=(16, 20), sharey=True)
    axes = axes.flatten()
    z_top_L = geometry.H_R - geometry.H_L
    datasets = [(profile_left, "Left side", -1.0, left_data.z_w, z_top_L), (profile_right, "Right side", 1.0, right_data.z_w, 0.0)]
    keys = [("sigma_v", "Vertical stress σv"), ("dx_tot", "Total displacement dx"), ("m", "Mobilization m"), ("K_XE", "KXE"), ("p_h", "Horizontal pressure p")]
    for col, (profile, side_title, sign_p, water_z, ground_z) in enumerate(datasets):
        for row, (key, title) in enumerate(keys):
            ax = axes[row*2 + col]
            z = profile["z"]
            q = profile["quadrant"]
            if key == "p_h":
                x = [float("nan") if qq == "void" or v is None else sign_p * float(v) for v, qq in zip(profile[key], q)]
            elif key == "dx_tot":
                x = [float("nan") if qq == "void" or v is None else -float(v) for v, qq in zip(profile[key], q)]
            else:
                x = [float("nan") if qq == "void" or v is None else float(v) for v, qq in zip(profile[key], q)]
            ax.plot(x, z)
            ax.axhline(ground_z, color="saddlebrown", linewidth=1.0)
            ax.axhline(water_z, color="blue", linestyle="--", linewidth=1.0)
            ax.grid(True, alpha=0.3)
            ax.set_title(f"{side_title} — {title}")
            ax.set_ylim(geometry.H_R, 0.0)
            ax.set_ylabel("z (m)")
    fig.tight_layout()
    return fig


def integrate_quadrant(profile, quadrant_name, force_sign, z_p):
    z, quads, p, dx = profile["z"], profile["quadrant"], profile["p_h"], profile["dx_tot"]
    F = M = W = 0.0
    z_used = []
    for i in range(len(z) - 1):
        if quads[i] != quadrant_name or quads[i + 1] != quadrant_name:
            continue
        if any(v is None for v in (p[i], p[i + 1], dx[i], dx[i + 1])):
            continue
        z0, z1 = float(z[i]), float(z[i + 1])
        dz = z1 - z0
        if dz <= 0: continue
        f0, f1 = force_sign * float(p[i]), force_sign * float(p[i + 1])
        F += 0.5 * (f0 + f1) * dz
        M += 0.5 * (f0 * (z0 - z_p) + f1 * (z1 - z_p)) * dz
        W += 0.5 * (abs(f0 * float(dx[i])) + abs(f1 * float(dx[i + 1]))) * dz
        z_used.extend([z0, z1])
    return {"F": F, "M": M, "z_action": z_p + M / F if abs(F) > 1e-12 else float("nan"), "z_upper": min(z_used) if z_used else float("nan"), "z_lower": max(z_used) if z_used else float("nan"), "W": W}


def _adverse_label(value: float, adverse_when_positive: bool) -> str:
    if abs(value) <= 1e-9: return "—"
    adverse = value > 0.0 if adverse_when_positive else value < 0.0
    return "δυσμενές" if adverse else "ευνοϊκό"


def resultants_dataframe(profile_left, profile_right, geometry: Geometry, left_data: SideData, movement: MovementData, gamma_w: float) -> pd.DataFrame:
    rows = []
    results = []
    for quad in ["RA", "RP"]: results.append(("Right", quad, "←", integrate_quadrant(profile_right, quad, +1.0, geometry.z_p)))
    for quad in ["LP", "LA"]: results.append(("Left", quad, "→", integrate_quadrant(profile_left, quad, -1.0, geometry.z_p)))
    lw = integrate_left_water_above_surface(geometry, left_data, movement, gamma_w)
    if lw: results.append(("Left", "Water above surface", "→", lw))
    sum_F = sum_M = sum_W = 0.0
    for side, quad, direction, res in results:
        if abs(res["F"]) < 1e-6: continue
        sum_F += res["F"]; sum_M += res["M"]; sum_W += res["W"]
        rows.append({"Side": side, "Quadrant": quad, "z upper (m)": res["z_upper"], "z lower (m)": res["z_lower"], "Force dir.": direction, "ΣF signed (kN/m)": res["F"], "F effect": _adverse_label(res["F"], True), "ΣM signed (kNm/m)": res["M"], "M effect": _adverse_label(res["M"], False), "Moment dir.": "CW" if res["M"] > 1e-9 else ("CCW" if res["M"] < -1e-9 else "—"), "z action (m)": res["z_action"], "Work (kN·m/m)": abs(res["W"])})
    rows.append({"Side": "Σ", "Quadrant": "", "z upper (m)": "", "z lower (m)": "", "Force dir.": "", "ΣF signed (kN/m)": sum_F, "F effect": _adverse_label(sum_F, True), "ΣM signed (kNm/m)": sum_M, "M effect": _adverse_label(sum_M, False), "Moment dir.": "CW" if sum_M > 1e-9 else ("CCW" if sum_M < -1e-9 else "—"), "z action (m)": "", "Work (kN·m/m)": abs(sum_W)})
    return pd.DataFrame(rows)


def query_dataframe(point_left, point_right) -> pd.DataFrame:
    keys = ["quadrant", "quadrant_type", "z_local", "H_quad", "beta_deg", "q_real", "q_upper", "sigma_v_geo", "sigma_v_total", "u", "dx_rot", "dx_tot_signed", "dx_tot_abs", "dx_max", "dx_M", "m", "K_OE", "K_limit", "DeltaK", "K_XE", "slope_factor", "A0", "B1", "C1", "phi_m_deg", "c_m", "sigma_h_OE", "sigma_h_AE", "sigma_h_PE", "sigma_h_limit", "sigma_h_corrected", "p_h_final", "notes"]
    return pd.DataFrame([{"Quantity": k, "Left": point_left.get(k), "Right": point_right.get(k)} for k in keys])


def run_auto_solver_streamlit(geometry0, left_data, right_data, seismic, gamma_w, n_points, tol_F_practical, tol_M_practical):
    H = geometry0.H_R
    z_top_L = geometry0.H_R - geometry0.H_L
    n_search = max(81, min(181, int(n_points)))
    z_eps = _profile_epsilon(H)
    z_values = [z_eps + (H - z_eps) * i / (n_search - 1) for i in range(n_search)]
    dx_abs_min, dx_abs_max = 0.0, max(0.50, 0.50 * H)
    th_abs_min, th_abs_max = 0.0, 12.0
    zp_abs_min, zp_abs_max = max(0.0, min(H, z_top_L)), H
    dx0_min, dx0_max = dx_abs_min, min(dx_abs_max, max(0.30 * H, 0.50))
    th0_min, th0_max = th_abs_min, min(th_abs_max, 6.0)
    zp0_min, zp0_max = zp_abs_min, zp_abs_max
    F_ref = max(1.0, right_data.gamma * H * H)
    M_ref = max(1.0, F_ref * H)
    if tol_F_practical <= 0.0: tol_F_practical = max(0.5, 1e-3 * F_ref)
    if tol_M_practical <= 0.0: tol_M_practical = max(1.0, 1e-3 * M_ref)
    cache, all_candidates = {}, []
    best_record, best_score = None, float("inf")

    def linspace(a, b, n):
        if n <= 1 or abs(b - a) < 1e-15: return [0.5 * (a + b)]
        return [a + (b - a) * i / (n - 1) for i in range(n)]
    def clamp(v, lo, hi): return min(hi, max(lo, float(v)))
    def near(value, bound, span): return abs(value - bound) <= max(1e-10, 0.015 * max(abs(span), 1e-12))
    def evaluate(dx, theta_deg, zp):
        dx = clamp(dx, dx_abs_min, dx_abs_max); theta_deg = clamp(theta_deg, th_abs_min, th_abs_max); zp = clamp(zp, zp_abs_min, zp_abs_max)
        key = (round(dx, 12), round(theta_deg, 12), round(zp, 12))
        if key in cache: return cache[key]
        try:
            geometry = Geometry(geometry0.H_R, geometry0.H_L, zp)
            movement = MovementData(dx, theta_deg)
            prof_r = solve_profile("right", z_values, geometry, left_data, right_data, seismic, movement, gamma_w)
            prof_l = solve_profile("left", z_values, geometry, left_data, right_data, seismic, movement, gamma_w)
            SF, SM, W = compute_global_resultants(prof_r, prof_l, geometry, left_data, movement, gamma_w)
            out = (SF, SM, W, (SF / F_ref) ** 2 + (SM / M_ref) ** 2)
        except Exception:
            out = None
        cache[key] = out
        return out
    def make_record(dx, theta_deg, zp, out):
        SF, SM, W, score = out
        return (float(dx), float(theta_deg), float(zp), float(W), float(SF), float(SM), float(score))
    def register(dx, theta_deg, zp):
        nonlocal best_record, best_score
        out = evaluate(dx, theta_deg, zp)
        if out is None: return None
        rec = make_record(dx, theta_deg, zp, out)
        if abs(rec[4]) <= tol_F_practical and abs(rec[5]) <= tol_M_practical:
            all_candidates.append(rec)
        if rec[6] < best_score:
            best_record, best_score = rec, rec[6]
        return rec
    def sorted_unique(records, limit):
        seen, out = set(), []
        for rec in sorted(records, key=lambda r: (r[6], r[3])):
            key = (round(rec[0], 8), round(rec[1], 8), round(rec[2], 8))
            if key in seen: continue
            seen.add(key); out.append(rec)
            if len(out) >= limit: break
        return out

    level1 = []
    prog = st.progress(0, text="Auto search L1: broad coarse scan...")
    total_l1 = 9*9*13; count = 0
    for dx in linspace(dx0_min, dx0_max, 9):
        for theta_deg in linspace(th0_min, th0_max, 9):
            for zp in linspace(zp0_min, zp0_max, 13):
                rec = register(dx, theta_deg, zp)
                if rec is not None: level1.append(rec)
                count += 1
                if count % 25 == 0: prog.progress(min(0.30, 0.30*count/total_l1), text="Auto search L1: broad coarse scan...")
    if not level1:
        return [], None, tol_F_practical, tol_M_practical, len(cache), "Auto: no valid state found"
    seeds = sorted_unique(level1, 8)
    if best_record is not None:
        dx_b, th_b, zp_b, *_ = best_record
        for s in [(max(dx_abs_min, 0.25*dx_b), th_b, zp_b), (dx_b, max(th_abs_min, 0.5*th_b), zp_b), (dx_b, th_b, clamp(z_top_L + 0.25*geometry0.H_L, zp_abs_min, zp_abs_max)), (dx_b, th_b, clamp(z_top_L + 0.75*geometry0.H_L, zp_abs_min, zp_abs_max))]:
            rec = register(*s)
            if rec is not None: seeds.append(rec)
        seeds = sorted_unique(seeds, 10)

    level2 = []
    for si, seed in enumerate(seeds):
        dx_c, th_c, zp_c, *_ = seed
        dx_span = max((dx0_max-dx0_min)/4, 0.05*H); th_span = max((th0_max-th0_min)/4, 0.75); zp_span = max((zp0_max-zp0_min)/4, 0.05*H)
        local_best = seed
        for cycle in range(7):
            prog.progress(0.30 + 0.50*((si*7+cycle+1)/max(1, len(seeds)*7)), text=f"Auto search L2: seed {si+1}/{len(seeds)}, moving grid {cycle+1}/7...")
            dx_lo, dx_hi = clamp(dx_c-0.5*dx_span, dx_abs_min, dx_abs_max), clamp(dx_c+0.5*dx_span, dx_abs_min, dx_abs_max)
            th_lo, th_hi = clamp(th_c-0.5*th_span, th_abs_min, th_abs_max), clamp(th_c+0.5*th_span, th_abs_min, th_abs_max)
            zp_lo, zp_hi = clamp(zp_c-0.5*zp_span, zp_abs_min, zp_abs_max), clamp(zp_c+0.5*zp_span, zp_abs_min, zp_abs_max)
            cycle_records = []
            for dx in linspace(dx_lo, dx_hi, 7):
                for theta_deg in linspace(th_lo, th_hi, 7):
                    for zp in linspace(zp_lo, zp_hi, 7):
                        rec = register(dx, theta_deg, zp)
                        if rec is not None: cycle_records.append(rec)
            if not cycle_records: break
            cycle_best = min(cycle_records, key=lambda r: (r[6], r[3]))
            if cycle_best[6] < local_best[6]: local_best = cycle_best
            dx_c, th_c, zp_c = cycle_best[0], cycle_best[1], cycle_best[2]
            moved = False
            if near(dx_c, dx_hi, dx_hi-dx_lo) and dx_hi < dx_abs_max: dx_span *= 1.25; dx_c = min(dx_abs_max, dx_c+0.25*dx_span); moved=True
            elif near(dx_c, dx_lo, dx_hi-dx_lo) and dx_lo > dx_abs_min: dx_span *= 1.25; dx_c = max(dx_abs_min, dx_c-0.25*dx_span); moved=True
            if near(th_c, th_hi, th_hi-th_lo) and th_hi < th_abs_max: th_span *= 1.25; th_c = min(th_abs_max, th_c+0.25*th_span); moved=True
            elif near(th_c, th_lo, th_hi-th_lo) and th_lo > th_abs_min: th_span *= 1.25; th_c = max(th_abs_min, th_c-0.25*th_span); moved=True
            if near(zp_c, zp_hi, zp_hi-zp_lo) and zp_hi < zp_abs_max: zp_span *= 1.25; zp_c = min(zp_abs_max, zp_c+0.25*zp_span); moved=True
            elif near(zp_c, zp_lo, zp_hi-zp_lo) and zp_lo > zp_abs_min: zp_span *= 1.25; zp_c = max(zp_abs_min, zp_c-0.25*zp_span); moved=True
            if not moved: dx_span *= 0.5; th_span *= 0.5; zp_span *= 0.5
        level2.append(local_best)
    if level2:
        best_l2 = min(level2, key=lambda r: (r[6], r[3]))
        if best_record is None or best_l2[6] < best_record[6]: best_record = best_l2; best_score = best_l2[6]

    if best_record is not None:
        dx_step = max(0.02*H, 1e-4*max(1.0,H)); th_step = max(0.20, 1e-4); zp_step = max(0.02*H, 1e-4*max(1.0,H))
        for it in range(60):
            prog.progress(0.80 + 0.20*((it+1)/60), text=f"Auto search L3: local pattern refinement {it+1}/60...")
            old_score = best_score; dx_c, th_c, zp_c, *_ = best_record; trials = []
            for ddx in (-dx_step,0.0,dx_step):
                for dth in (-th_step,0.0,th_step):
                    for dzp in (-zp_step,0.0,zp_step):
                        if ddx == dth == dzp == 0.0: continue
                        rec = register(dx_c+ddx, th_c+dth, zp_c+dzp)
                        if rec is not None: trials.append(rec)
            if trials:
                tb = min(trials, key=lambda r:(r[6], r[3]))
                if tb[6] < best_score: best_record, best_score = tb, tb[6]
            if best_score >= old_score - 1e-14: dx_step *= .5; th_step *= .5; zp_step *= .5
            if dx_step < 1e-6*max(1.0,H) and th_step < 1e-5 and zp_step < 1e-6*max(1.0,H): break
    prog.empty()
    practical = []
    seen=set()
    for rec in sorted(all_candidates, key=lambda r:(r[3], r[6])):
        key=(round(rec[0],8),round(rec[1],8),round(rec[2],8))
        if key in seen: continue
        seen.add(key); practical.append(rec)
    selected = practical[0] if practical else best_record
    status = "Auto: equilibrium candidates found; minimum-work solution selected" if practical else "Auto: NO candidate within tolerances; best approximate state shown"
    return practical, selected, tol_F_practical, tol_M_practical, len(cache), status


def auto_dataframe(records):
    return pd.DataFrame([{"#": i+1, "|dx| (m)": abs(r[0]), "θ_rot (deg)": r[1], "z_p (m)": r[2], "Work (kN·m/m)": r[3], "ΣF (kN/m)": r[4], "ΣM (kNm/m)": r[5], "score (-)": r[6]} for i, r in enumerate(records)])


def main():
    st.set_page_config(page_title=APP_NAME, layout="wide")
    geometry_d, left_d, right_d, seismic_d, movement_d, gamma_w_d = _example_setup()
    st.title(APP_NAME)

    # Image buttons: Run and Home are clickable images, not separate button+image pairs.
    c_run, c_stop, c_home, c_about = st.columns([1, 1, 1, 1])
    with c_run:
        image_link_button("cut.png", "?run=1", width=66, title="Run")
    with c_stop:
        if st.button("Stop", use_container_width=True):
            st.session_state.stop_requested = True
            st.warning("Stop requested. In Streamlit this applies at the next rerun/calculation checkpoint.")
    with c_home:
        image_link_button("home.png", HOME_URL, width=66, title="Home")
    with c_about:
        if st.button("About", use_container_width=True):
            st.info("CUT_Rigid_piled_wall_homogenous\n\nVersion: Streamlit v1.1\n\nAuthor: Dr Lysandros Pantelidis, Cyprus University of Technology\n\nEducational tool — no warranty. Use at your own risk. Free of charge.")

    with st.sidebar:
        st.header("Input data")
        st.subheader("Geometry")
        H_L = st.number_input("Left H (m)", value=float(geometry_d.H_L), step=0.1)
        H_R = st.number_input("Right H (m)", value=float(geometry_d.H_R), step=0.1)
        z_p = st.number_input("z_p (m, pivot point)", value=float(st.session_state.get("auto_zp", geometry_d.z_p)), step=0.1)
        geometry = Geometry(float(H_R), float(H_L), float(z_p))
        st.subheader("Surface and water")
        beta_L = st.number_input("β_L (deg)", value=float(left_d.beta_deg), step=0.1)
        beta_R = st.number_input("β_R (deg)", value=float(right_d.beta_deg), step=0.1)
        q_L = st.number_input("q_L (kPa)", value=float(left_d.q_real), step=1.0)
        q_R = st.number_input("q_R (kPa)", value=float(right_d.q_real), step=1.0)
        z_w_L = st.number_input("z_w_L (m)", value=float(left_d.z_w), step=0.1)
        z_w_R = st.number_input("z_w_R (m)", value=float(right_d.z_w), step=0.1)
        gamma_w = st.number_input("γ_w (kN/m³)", value=float(gamma_w_d), step=0.01)
        st.subheader("Soil properties")
        cL1, cL2 = st.columns(2)
        with cL1:
            st.markdown("**Left side**")
            gamma_L = st.number_input("γ_L (kN/m³)", value=float(left_d.gamma), step=0.1)
            gamma_sat_L = st.number_input("γsat_L (kN/m³)", value=float(left_d.gamma_sat), step=0.1)
            c_L = st.number_input("c'_L (kPa)", value=float(left_d.c_prime), step=0.1)
            phi_L = st.number_input("φ'_L (deg)", value=float(left_d.phi_prime_deg), step=0.1)
            E_L = st.number_input("E_s,L (kPa)", value=float(left_d.E_s), step=100.0)
            nu_L = st.number_input("ν_L (-)", value=float(left_d.nu), min_value=0.0, max_value=0.49, step=0.01)
        with cL2:
            st.markdown("**Right side**")
            gamma_R = st.number_input("γ_R (kN/m³)", value=float(right_d.gamma), step=0.1)
            gamma_sat_R = st.number_input("γsat_R (kN/m³)", value=float(right_d.gamma_sat), step=0.1)
            c_R = st.number_input("c'_R (kPa)", value=float(right_d.c_prime), step=0.1)
            phi_R = st.number_input("φ'_R (deg)", value=float(right_d.phi_prime_deg), step=0.1)
            E_R = st.number_input("E_s,R (kPa)", value=float(right_d.E_s), step=100.0)
            nu_R = st.number_input("ν_R (-)", value=float(right_d.nu), min_value=0.0, max_value=0.49, step=0.01)
        left_data = SideData(float(beta_L), float(q_L), float(z_w_L), float(gamma_L), float(gamma_sat_L), _regularize_c_prime(float(c_L)), float(phi_L), float(E_L), float(nu_L))
        right_data = SideData(float(beta_R), float(q_R), float(z_w_R), float(gamma_R), float(gamma_sat_R), _regularize_c_prime(float(c_R)), float(phi_R), float(E_R), float(nu_R))
        st.subheader("Seismic")
        k_v = st.number_input("k_v = a_v (-)", value=float(seismic_d.a_v), step=0.01)
        k_h = st.number_input("k_h = a_h (-)", value=float(seismic_d.k_v), step=0.01)
        theta_eq_deg = math.degrees(math.atan2(float(k_h), 1.0 - float(k_v)))
        seismic = SeismicData(float(k_v), float(k_v), theta_eq_deg)
        st.subheader("Movement")
        dx_trans = st.number_input("dx_trans (m)", value=float(st.session_state.get("auto_dx", movement_d.dx_trans)), step=0.001, format="%.6f")
        theta_rot = st.number_input("θ_rot (deg)", value=float(st.session_state.get("auto_theta", movement_d.theta_rot_deg)), step=0.01)
        auto = st.checkbox("Auto equilibrium search", value=False)
        tol_F = st.number_input("tol |ΣF| (kN/m)", value=10.0, step=1.0)
        tol_M = st.number_input("tol |ΣM| (kNm/m)", value=50.0, step=1.0)
        movement = MovementData(float(dx_trans), float(theta_rot))
        st.subheader("Run controls")
        z_query = st.number_input("query z (m, red dot)", value=2.0, step=0.1)
        n_points = st.number_input("n profile points (-)", min_value=11, max_value=5000, value=1000, step=10)

    try:
        if geometry.H_R <= geometry.H_L:
            st.error("Geometry restriction violated: H_R must be greater than H_L."); st.stop()
        z_top_L = geometry.H_R - geometry.H_L
        if right_data.z_w < 0.0:
            st.error("Water level restriction violated: z_w_R cannot be above the right ground surface."); st.stop()
        if left_data.z_w < z_top_L:
            st.error(f"Water level restriction violated: z_w_L must be ≥ H_R - H_L = {z_top_L:.3f}."); st.stop()

        auto_records = []
        selected_record = None
        auto_status = "Run Auto equilibrium search to populate this tab."
        if auto:
            auto_records, selected_record, tol_F, tol_M, evals, auto_status = run_auto_solver_streamlit(geometry, left_data, right_data, seismic, float(gamma_w), int(n_points), float(tol_F), float(tol_M))
            if selected_record is not None:
                dx, theta, zp, W_sel, SF_sel, SM_sel, score_sel = selected_record
                st.session_state.auto_dx, st.session_state.auto_theta, st.session_state.auto_zp = dx, theta, zp
                movement = MovementData(dx, theta)
                geometry = Geometry(geometry.H_R, geometry.H_L, zp)
                st.success(f"{auto_status} | dx={dx:.6g}, θ={theta:.6g}°, z_p={zp:.6g}, ΣF={SF_sel:.4g}, ΣM={SM_sel:.4g}, W={W_sel:.4g}, evals={evals}")

        z_eps = _profile_epsilon(geometry.H_R)
        z_values = [z_eps + (geometry.H_R - z_eps) * i / (int(n_points) - 1) for i in range(int(n_points))]
        profile_left = solve_profile("left", z_values, geometry, left_data, right_data, seismic, movement, float(gamma_w))
        profile_right = solve_profile("right", z_values, geometry, left_data, right_data, seismic, movement, float(gamma_w))
        point_left = solve_point(float(z_query), "left", geometry, left_data, right_data, seismic, movement, float(gamma_w))
        point_right = solve_point(float(z_query), "right", geometry, left_data, right_data, seismic, movement, float(gamma_w))
        SF, SM, W = compute_global_resultants(profile_right, profile_left, geometry, left_data, movement, float(gamma_w))

        m1, m2, m3 = st.columns(3)
        m1.metric("ΣF (kN/m)", f"{SF:.3f}")
        m2.metric("ΣM (kNm/m)", f"{SM:.3f}")
        m3.metric("Work (kN·m/m)", f"{W:.4f}")

        tab_geom, tab_plots, tab_pressure, tab_query, tab_profile, tab_auto = st.tabs(["Geometry", "Plots", "Pressure diagrams", "Query z table", "Profile table", "Auto solutions"])
        with tab_geom:
            st.pyplot(plot_geometry(geometry, left_data, right_data, float(z_query)), clear_figure=True)
        with tab_plots:
            st.pyplot(plot_all_profiles(profile_left, profile_right, geometry, left_data, right_data, float(gamma_w)), clear_figure=True)
        with tab_pressure:
            st.dataframe(resultants_dataframe(profile_left, profile_right, geometry, left_data, movement, float(gamma_w)), use_container_width=True)
            st.pyplot(plot_pressure(profile_left, profile_right, geometry, left_data, right_data, movement, float(gamma_w)), clear_figure=True)
        with tab_query:
            st.dataframe(query_dataframe(point_left, point_right), use_container_width=True)
        with tab_profile:
            st.dataframe(profile_dataframe(profile_left, profile_right), use_container_width=True)
        with tab_auto:
            st.write(auto_status)
            if selected_record is not None:
                st.subheader("Selected auto solution")
                st.dataframe(auto_dataframe([selected_record]), use_container_width=True)
            st.subheader("Accepted candidates")
            st.dataframe(auto_dataframe(auto_records), use_container_width=True)
    except Exception as exc:
        st.exception(exc)


if __name__ == "__main__":
    main()
