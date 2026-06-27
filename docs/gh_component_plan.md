# Grasshopper Implementation Plan: EPW Morpher Component

This plan outlines how we will wrap our existing Python morphing engine into a native Grasshopper component using Rhino 8's CPython capabilities.

## 1. Component Interface (Inputs & Outputs)

We will create a GHPython component that acts as a bridge between the Grasshopper canvas and our `epw_morphing_engine.py`.

### Inputs
*   `Baseline_EPW` *(String)*: File path to the baseline `.epw` (e.g., `Bangkok_baseline_2026_TMYx.epw`).
*   `Delta_Dir` *(String)*: Directory path where your delta CSVs are stored.
*   `SSP_Scenario` *(String/Int)*: Value List input. Options: `126` (SSP1-2.6), `245` (SSP2-4.5), `370` (SSP3-7.0), `585` (SSP5-8.5).
*   `Target_Year` *(Int)*: Value List input. Options: `2030`, `2050`, `2070`, `2090`.
*   `Morph_Method` *(Int)*: Value List input. `0` = Normal Shift (Belcher), `1` = BTWS.
*   `Run` *(Boolean)*: A button to trigger the calculation.

### Outputs
*   `Morphed_EPW` *(String)*: File path to the newly generated future `.epw` file (ready to plug directly into the Ladybug Import EPW component).
*   `Report` *(String)*: A summary log of the morphing process for a GH text panel.

---

## 2. Dynamic Delta Loading

To make the component flexible, it will automatically construct the correct CSV file name based on your inputs. 

If `SSP_Scenario = 585` and `Target_Year = 2070`, the script will look for:
`Delta_Dir + "\bangkok_ssp585_2070.csv"`

*We will need to establish this strict naming convention for any future CSVs you download.*

---

## 3. The GHPython Script Logic

Instead of copying 500 lines of complex math directly into the Grasshopper component (which is hard to debug and update), we will use a much cleaner approach:

1.  **Link to Repo:** The GH script will dynamically add your `Weather-Data-Morphing/morphing/` directory to its Python path (`sys.path.append()`).
2.  **Import:** It will import our already-tested `EPWMorphingEngine`.
3.  **Execute:** It will run the engine just like a normal python script.
4.  **Save & Output:** It saves the new EPW file to a temporary or defined output folder, and passes the path out to Grasshopper.

This means if we ever improve the math in `btws_morpher.py`, the Grasshopper component automatically gets the update without needing to copy-paste code again.

---

## 4. Execution Steps

If you approve this plan, I will:
1.  Write the exact Python code you need to paste into the GHPython component.
2.  Set up the Grasshopper canvas for you (if Rhino is running, I can use the Rhino MCP tools to place the components, sliders, and value lists directly onto your canvas).
3.  Ensure the Ladybug components can successfully read the output file.
