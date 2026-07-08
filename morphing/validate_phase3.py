"""
validate_phase3.py — Solar Physics Correction Validation
==========================================================
Validates Phase 3 (the GHI/DNI/DHI physics correction in
epw_morphing_engine.py) WITHOUT a third-party "future file" benchmark.

Why this is needed:
    belcher_vs_cura_validation.md validated the Belcher path by diffing
    against a real CURA-lab morphed EPW. No such benchmark exists for
    BTWS, because no third party publishes a BTWS-morphed Bangkok file.

Key insight this script relies on:
    The Phase 3 correction scales DNI and DHI by
        ratio = morphed_GHI / baseline_GHI
    This is algebraically independent of which method (Belcher or BTWS)
    produced morphed_GHI. If GHI = DNI*cos(theta) + DHI held for the
    baseline, then:
        DNI'*cos(theta) + DHI' = ratio*(DNI*cos(theta) + DHI)
                                = ratio*GHI = GHI'
    So Phase 3 can be validated as a self-contained unit: given ANY
    GHI morph (including the already CURA-validated Belcher path),
    does the closure equation hold afterwards? This sidesteps the
    "no BTWS ground truth" problem entirely — we are validating the
    correction step, not the BTWS temperature/radiation algorithm.

Important nuance discovered while building this: the baseline TMYx file
itself does NOT perfectly satisfy GHI = DNI*cos(theta) + DHI (real
measured/satellite EPW data rarely does — see Hamann et al. 2025's
finding of ~27% inconsistent hours in Vienna). So "closure residual is
non-zero" is not a Phase 3 bug — it is inherited from the source data.
The correct thing to test is the algebraic identity the ratio-scaling
approach actually guarantees, applied to the residual directly (not a
relative/percentage form, which blows up via division near sunrise
when GHI -> 0):
    residual        = GHI - DNI*cos(theta) - DHI
    ratio           = morphed_GHI / baseline_GHI
    expected_resid' = ratio * baseline_residual
    actual_resid'   = morphed_GHI - morphed_DNI*cos(theta) - morphed_DHI
    actual_resid' == expected_resid'   (for un-clipped hours, up to the
                                         EPW writer's 1-decimal rounding)

Four checks, run for both method="belcher" and method="btws":
    1. Correction fidelity — the morphed closure residual must equal
       ratio * baseline_residual for hours where DHI wasn't clipped;
       clipped hours are counted separately since the current clip
       (engine.py:388-389) adjusts DHI without re-solving DNI, which
       DOES break the identity.
    2. Physical invariants — DHI <= GHI, DNI >= 0, night hours == 0.
    3. Delta-target regression — does the morphed GHI's monthly mean
       match the input CSV's alpha_rsds / delta_rsds_* targets?
    4. BTWS-path sanity — confirms whether the BTWS solar branch in
       epw_morphing_engine.py actually executes for the given delta
       CSV, since it silently no-ops (falls back to Belcher stretch)
       when delta_rsds_max/min columns are absent.

Usage:
    python validate_phase3.py [path/to/deltas.csv]
"""

import sys
import os
import numpy as np

from epw_morphing_engine import EPWMorphingEngine, EPW_COLS

DEFAULT_EPW = r"..\data\epw\Bangkok_baseline_2026_TMYx.epw"
DEFAULT_DELTAS = r"..\data\deltas\bangkok_ssp585_2070.csv"


# ── Solar Position (NOAA/ASHRAE simplified solar geometry) ─────────

def parse_location(epw_path):
    """Reads latitude, longitude, and timezone from the EPW LOCATION line."""
    with open(epw_path, 'r') as f:
        loc = f.readline().strip().split(',')
    latitude = float(loc[6])
    longitude = float(loc[7])
    timezone = float(loc[8])
    return latitude, longitude, timezone


def solar_zenith_cosine(month, day, hour, latitude, longitude, timezone):
    """
    Vectorized cos(theta_zenith) for each EPW hour using standard
    NOAA/ASHRAE solar position equations. EPW "hour" N is the interval
    ending at N:00, so the representative solar time uses (hour - 0.5).

    :param month, day, hour: np.ndarray (int) of EPW timestamp fields.
    :return: np.ndarray of cos(zenith), one value per hour.
    """
    days_in_month = np.array([0, 31, 59, 90, 120, 151, 181, 212, 243, 273, 304, 334])
    n = days_in_month[month - 1] + day  # day of year

    # Solar declination (degrees -> radians)
    declination = np.radians(23.45 * np.sin(np.radians(360.0 / 365.0 * (284 + n))))

    # Equation of time (minutes)
    B = np.radians(360.0 / 364.0 * (n - 81))
    eot = 9.87 * np.sin(2 * B) - 7.53 * np.cos(B) - 1.5 * np.sin(B)

    # Local standard time meridian
    lstm = 15.0 * timezone

    # Time correction (minutes) and local solar time (hours)
    time_correction = 4.0 * (longitude - lstm) + eot
    clock_hour = hour - 0.5  # midpoint of the EPW hour-ending interval
    local_solar_time = clock_hour + time_correction / 60.0

    # Hour angle (degrees -> radians)
    hour_angle = np.radians(15.0 * (local_solar_time - 12.0))

    lat_rad = np.radians(latitude)
    cos_zenith = (np.sin(lat_rad) * np.sin(declination) +
                  np.cos(lat_rad) * np.cos(declination) * np.cos(hour_angle))
    return np.clip(cos_zenith, -1.0, 1.0)


# ── Checks ──────────────────────────────────────────────────────────

def closure_residual(ghr, dni, dhi, cos_theta):
    """GHI - DNI*cos(theta) - DHI, in Wh/m^2. Zero iff closure holds exactly."""
    return ghr - dni * cos_theta - dhi


def check_correction_fidelity(label, baseline_ghr, baseline_resid,
                               morphed_ghr, morphed_resid,
                               dhi_exceeds_mask, sun_up_mask, tol=1.0):
    """
    Check 1: Phase 3 must neither fix nor worsen the baseline's closure
    error — ratio scaling implies actual_resid' == ratio*baseline_resid
    exactly, up to the ~0.05 Wh/m2 quantization from the EPW writer's
    ".1f" rounding on each of GHI/DNI/DHI (tol=1.0 gives ample margin).
    """
    check_mask = sun_up_mask & ~dhi_exceeds_mask & (baseline_ghr > 0)
    ratio = np.zeros_like(baseline_ghr)
    ratio[check_mask] = morphed_ghr[check_mask] / baseline_ghr[check_mask]
    expected_resid = ratio * baseline_resid

    drift = np.abs(morphed_resid[check_mask] - expected_resid[check_mask])
    n_drifted = int(np.sum(drift > tol))
    max_drift = float(np.max(drift)) if drift.size else 0.0

    n_clipped_daytime = int(np.sum(dhi_exceeds_mask & sun_up_mask))
    baseline_daytime_resid = baseline_resid[sun_up_mask & (baseline_ghr > 0)]

    print(f"  [{label}] Correction fidelity (actual vs ratio*baseline residual):")
    print(f"      baseline mean|residual|={np.mean(np.abs(baseline_daytime_resid)):.2f} Wh/m2 "
          f"(inherited from source EPW, not a Phase 3 defect)")
    print(f"      un-clipped hours violating identity: {n_drifted}/{int(np.sum(check_mask))} "
          f"(max drift={max_drift:.3f} Wh/m2, tol={tol})")
    print(f"      DHI-clipped daytime hours (identity NOT guaranteed here): {n_clipped_daytime}")
    return n_drifted, n_clipped_daytime


def check_invariants(label, ghr, dni, dhi):
    """Check 2: physical bounds that must never be violated."""
    dhi_exceeds = int(np.sum(dhi > ghr + 1e-6))
    dni_negative = int(np.sum(dni < -1e-6))
    night_mask = ghr <= 0
    night_leak = int(np.sum((np.abs(dni[night_mask]) > 1e-6) |
                             (np.abs(dhi[night_mask]) > 1e-6)))

    print(f"  [{label}] Invariants: DHI>GHI hours={dhi_exceeds}, "
          f"DNI<0 hours={dni_negative}, night-hour leakage={night_leak}")
    return dhi_exceeds, dni_negative, night_leak


def check_delta_targets(label, months, baseline_ghr, morphed_ghr, deltas):
    """Check 3: does the monthly mean GHI shift match the CSV target?"""
    print(f"  [{label}] Monthly mean GHI vs delta target:")
    max_err_pct = 0.0
    for m in range(1, 13):
        mask = months == m
        base_mean = np.mean(baseline_ghr[mask])
        morph_mean = np.mean(morphed_ghr[mask])
        d = deltas[m]

        if 'delta_rsds_mean' in d:
            target_mean = base_mean + d['delta_rsds_mean']
        else:
            alpha = d.get('alpha_rsds', 1.0)
            target_mean = base_mean * alpha

        err_pct = 100.0 * (morph_mean - target_mean) / target_mean if target_mean else 0.0
        max_err_pct = max(max_err_pct, abs(err_pct))
        print(f"      Month {m:2d}: morphed={morph_mean:7.2f}  "
              f"target={target_mean:7.2f}  err={err_pct:+.2f}%")

    return max_err_pct


def check_btws_path_engaged(label, deltas):
    """
    Check 4: the BTWS solar branch in epw_morphing_engine.py only runs
    if every month's delta row has 'delta_rsds_max'. Otherwise it
    silently falls back to Belcher stretch even when method="btws".
    """
    has_max_min = all('delta_rsds_max' in deltas[m] for m in range(1, 13))
    if label == "btws":
        status = "BTWS solar branch ENGAGED" if has_max_min else \
            "BTWS solar branch DID NOT ENGAGE — delta CSV lacks delta_rsds_max/min, " \
            "fell back to Belcher stretch"
        print(f"  [{label}] {status}")
    return has_max_min


def run_for_method(method, epw_path, delta_path, latitude, longitude, timezone,
                    baseline_rel_cache):
    print(f"\n{'='*65}")
    print(f"  PHASE 3 VALIDATION — method={method}")
    print(f"{'='*65}")

    engine = EPWMorphingEngine(epw_path, delta_path)
    engine.morph(method=method)

    months = engine._get_months()
    days = np.array([int(row[EPW_COLS['day']]) for row in engine.data_rows])
    hours = np.array([int(row[EPW_COLS['hour']]) for row in engine.data_rows])

    cos_theta = solar_zenith_cosine(months, days, hours, latitude, longitude, timezone)
    sun_up_mask = cos_theta > 0.01

    ghr = engine._get_column(EPW_COLS['global_horizontal_radiation'])
    dni = engine._get_column(EPW_COLS['direct_normal_radiation'])
    dhi = engine._get_column(EPW_COLS['diffuse_horizontal_radiation'])

    with open(epw_path, 'r') as f:
        baseline_lines = f.readlines()[8:]
    baseline_ghr = np.array([
        float(l.strip().split(',')[EPW_COLS['global_horizontal_radiation']])
        for l in baseline_lines if l.strip()
    ])
    baseline_dni = np.array([
        float(l.strip().split(',')[EPW_COLS['direct_normal_radiation']])
        for l in baseline_lines if l.strip()
    ])
    baseline_dhi = np.array([
        float(l.strip().split(',')[EPW_COLS['diffuse_horizontal_radiation']])
        for l in baseline_lines if l.strip()
    ])

    if baseline_rel_cache.get('resid') is None:
        baseline_rel_cache['resid'] = closure_residual(
            baseline_ghr, baseline_dni, baseline_dhi, cos_theta
        )
    baseline_resid = baseline_rel_cache['resid']
    morphed_resid = closure_residual(ghr, dni, dhi, cos_theta)
    dhi_exceeds_mask = dhi > ghr - 1e-6  # hours where the clip in engine.py fired

    n_drifted, n_clipped = check_correction_fidelity(
        method, baseline_ghr, baseline_resid, ghr, morphed_resid,
        dhi_exceeds_mask, sun_up_mask
    )
    dhi_exceeds, dni_neg, night_leak = check_invariants(method, ghr, dni, dhi)
    max_err_pct = check_delta_targets(method, months, baseline_ghr, ghr, engine.deltas)
    btws_engaged = check_btws_path_engaged(method, engine.deltas)

    passed = (n_drifted == 0 and dni_neg == 0 and night_leak == 0 and max_err_pct < 1.0)
    print(f"\n  Result: {'PASS' if passed else 'FAIL — see violations above'}")
    return passed, btws_engaged


def main():
    epw_path = DEFAULT_EPW
    delta_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DELTAS

    latitude, longitude, timezone = parse_location(epw_path)
    print(f"Location: lat={latitude}, lon={longitude}, tz=UTC+{timezone}")
    print(f"Baseline EPW: {os.path.basename(epw_path)}")
    print(f"Deltas:       {os.path.basename(delta_path)}")

    results = {}
    baseline_rel_cache = {'rel': None}
    for method in ("belcher", "btws"):
        results[method] = run_for_method(
            method, epw_path, delta_path, latitude, longitude, timezone,
            baseline_rel_cache
        )

    print(f"\n{'='*65}")
    print("  SUMMARY")
    print(f"{'='*65}")
    for method, (passed, btws_engaged) in results.items():
        note = ""
        if method == "btws" and not btws_engaged:
            note = "  (NOTE: solar radiation used Belcher fallback, not BTWS)"
        print(f"  {method:10s}: {'PASS' if passed else 'FAIL'}{note}")


if __name__ == "__main__":
    main()
