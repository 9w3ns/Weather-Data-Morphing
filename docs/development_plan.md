# Weather Data Morphing Tool - Development Plan

## Overview
This document outlines the roadmap for developing a custom, Python-based EnergyPlus Weather (.epw) data morphing tool for Bangkok. The tool is designed to project future weather conditions (e.g., 2070 SSP5-8.5) and is specifically tailored for building performance simulation and data-driven architectural design.

The methodology heavily relies on the theories and algorithms discussed in the 2025 paper: *"Advanced Weather Data Morphing for Future Climate-Based Building Simulation"* by Hamann et al., specifically addressing the limitations found in existing morphing tools.

---

## Phase 1: The EPW Data Engine
**Goal:** Build the infrastructure to read, process, and write standard `.epw` files.
*   **EPW Parser:** Develop a Python script using `pandas` to ingest a baseline `.epw` file, correctly parsing the header rows and extracting the 8,760 hours of data across all 35+ fields.
*   **EPW Writer:** Implement an exporter that safely reconstructs the modified data back into a strict `.epw` format that Grasshopper, Ladybug, and Honeybee can read without errors.

## Phase 2: Implementation of Morphing Algorithms
**Goal:** Program the mathematical models to morph the baseline climate data into future projections.
*   **BTWS for Temperature & GHI:** Implement the **Bounded Temperature Weighted Stretch (BTWS)** algorithm (Eames et al., 2024) for Dry Bulb Temperature and Global Horizontal Radiation. This normalizes the data and applies a transfer function to accurately preserve projected changes in daily minimums, maximums, and means without breaking physical limits.
*   **Secondary Variables:** Implement the enhanced Belcher/Jentsch formulas (2012) for modifying Relative Humidity, Dew Point Temperature, Precipitation, and Wind Speed to ensure physical consistency.

## Phase 3: The Solar Physics Correction
**Goal:** Fix known limitations in existing solar morphing methodologies.
*   **The Problem:** Morphing Global Horizontal Radiation (GHI) alone without adjusting its components can result in physically impossible data (e.g., Diffuse Horizontal Irradiance exceeding GHI).
*   **The Solution:** Add a mathematical correction step. After GHI is morphed, scale Direct Normal Irradiance (DNI) and Diffuse Horizontal Irradiance (DHI) by `ratio = morphed_GHI / baseline_GHI`, which algebraically guarantees $GHI' = DNI' \cdot \cos(\theta) + DHI'$ holds wherever it held in the baseline — implemented in `epw_morphing_engine.py::_morph_solar_radiation`.
*   **Validation:** No third-party BTWS-morphed benchmark file exists (unlike Belcher, which has the CURA-lab file), so Phase 3 is validated as a self-contained unit instead of by diffing against a ground-truth future file — see `docs/belcher_vs_cura_validation.md` § "Phase 3 Validation" and `morphing/validate_phase3.py`. Confirmed: the ratio identity holds for 4108/4366 daytime hours to within EPW rounding precision; known gap is 258 near-zero-GHI hours where the DHI clip doesn't re-solve DNI, and the BTWS solar branch doesn't currently engage because the delta CSVs lack `delta_rsds_max`/`delta_rsds_min`.

## Phase 4: Integration and Workflow Handoff
**Goal:** Seamlessly integrate the morphed data into the architectural design workflow.
*   **Delta Processing:** Provide a simple interface (e.g., a `.csv` configuration file) to input CMIP6 monthly climate deltas ($\Delta T_{mean}$, $\Delta T_{max}$, $\Delta T_{min}$, etc.) specific to Bangkok.
*   **Data Validation:** Generate automated charts comparing the baseline vs. morphed EPW to visually confirm the "UTCI Floor Shift" before beginning architectural simulations.
*   **Grasshopper Handoff:** Ensure the final `.epw` output flawlessly connects with the existing Anemone/Ladybug Cellular Automata form-finding workflow to drive the spatial design of the Public Thermal Transit Hub.
