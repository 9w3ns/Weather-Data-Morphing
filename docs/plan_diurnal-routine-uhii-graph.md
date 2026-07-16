# Plan: Diurnal temperature + UHII graph with daily-routine overlay

## Context
The thesis argues Bangkok's evening (≈18:00–21:00) is the peak heat-stress window —
exactly when commuters return home. To make that visible, this builds a single
figure: **x = hour of day (0–23), y = air temperature (°C)**, showing the ambient
diurnal curve plus the district's urban heat-island bump, with an **office-worker
daily routine mapped on top** so the "return into peak evening heat → refuge
intercept" story is legible at a glance.

**Data note driving the design:** our UHII data (`bangkok_uhi_data.csv`) has only
two time points — *Night* and *Evening* — not a 24-hour curve. So the daytime UHI
shape is *modeled* (anchored to the two measured values), and that assumption is
flagged in the caption. UHII here is an **air-temperature** urban–rural differential,
so it is dimensionally correct to add onto the EPW dry-bulb (unlike LST, which is a
surface signal).

## Decisions (from the user)
- **Output:** matplotlib PNG → `visualization/routine_uhii_diurnal.png`, repo style.
- **UHII across 24h:** modeled smooth diurnal UHI curve anchored to the measured
  Evening + Night values (assumption flagged).
- **Scope:** **Din Daeng**, **HotDry** season, **today (2026) + 2050** morphed.
- **Routine:** office worker — wake 07:00, commute out 08–09, work 09–17 (AC),
  commute home 17–18, evening at home 18–21, sleep 22.

## Approach — new script `data/plot_routine_uhii_diurnal.py`
A single reproducible generator with an editable CONFIG block (district, season
months, SSP, routine dict, UHI diurnal anchors).

### 1. Ambient diurnal curve (y-axis base)
- Parse `data/epw/Bangkok_baseline_2026_TMYx.epw` and the pre-morphed
  `..._FUTURE_2050_ssp245.epw` directly for `month` (field 1) and `dry_bulb` (field
  6) — standard EPW layout; reuse the season-month idea from
  `morphing/plot_hourly_diff.py`. (No re-morphing needed — the 2050 EPWs already
  exist; `EPWMorphingEngine` remains the fallback.)
- **HotDry season = months [3,4,5]** (Mar–May; assumption, editable).
- Group those hours by hour-of-day → mean dry-bulb → a 24-value curve, for both
  2026 and 2050. Expect ~27–36 °C.

### 2. Modeled diurnal UHI (the "integrated UHII")
- Din Daeng HotDry anchors: **Evening ≈ 2.7 °C**, **Night ≈ 1.9 °C** (from
  `bangkok_uhi_data.csv`).
- Build `UHI(hour)` by `np.interp` (no scipy) over documented anchor points that
  encode standard UHI diurnal physics: near-zero at midday (urban≈rural), rising
  after sunset, **peaking in the evening window (anchored to 2.7)**, elevated
  overnight (anchored to 1.9), collapsing after sunrise. Only the daytime floor and
  peak-hour placement are assumptions; the evening/night magnitudes are data.
- **Urban curve = ambient + UHI(hour)** for each horizon.

### 3. Plot layers
- Ambient curves faint/dashed; **urban curves bold**; shade the gap between them as
  the **UHII contribution**. 2026 in a cool color family, 2050 in a warm one.
- **Routine overlay:** shaded vertical spans + labels (sleep, commute-out, work,
  commute-home) with the **18:00–21:00 evening window highlighted** as the refuge
  intercept; a callout arrow where the home-commute meets peak evening heat+UHI.
- Caption states: district/season/SSP, the modeled-UHI assumption, and that UHII is
  an air-temp differential.
- Save to `visualization/routine_uhii_diurnal.png` (dpi ~200).

## Reuse (don't re-implement)
- EPW parsing / `EPWMorphingEngine` — `morphing/epw_morphing_engine.py`.
- Season-month slicing + plot style — `morphing/plot_hourly_diff.py`.
- District UHII row — `data/gis/bangkok_uhi_data.csv`.

## Verification
- Assert 24-point curves; ambient within ~26–36 °C; **2050 curve strictly above
  2026**.
- Assert `UHI(hour)` hits anchors: evening-window mean ≈ 2.7, deep-night ≈ 1.9,
  midday < both.
- **Visually inspect the PNG** (read it back): evening UHII peak aligns with the
  18–21 routine band; routine spans placed at the right hours; legend/caption clear.

## Files
- **New:** `data/plot_routine_uhii_diurnal.py`
- **Generated:** `visualization/routine_uhii_diurnal.png`

## Honesty notes (put in caption / thesis)
- Daytime UHI shape is modeled, not measured (only Evening & Night are data).
- HotDry = Mar–May and 2050 = SSP2-4.5 are editable assumptions; SSP3-7.0 EPW is
  also available for a hotter variant.
- The routine is one representative office-worker persona, not a survey.
