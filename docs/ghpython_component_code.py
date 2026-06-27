"""
Grasshopper Python Script for Weather Data Morphing
Inputs:
    Baseline_EPW : String (Path to baseline .epw file)
    Delta_Dir    : String (Path to directory containing delta CSVs)
    Repo_Dir     : String (Path to the Weather-Data-Morphing repository folder)
    SSP_Scenario : String or Int (e.g., 126, 245, 370, 585)
    Target_Year  : String or Int (e.g., 2030, 2050, 2070, 2090)
    Morph_Method : Int (0 = Belcher, 1 = BTWS)
    Run          : Boolean (Button to execute)
Outputs:
    Morphed_EPW  : String (Path to the new morphed .epw file)
    Report       : String (Summary of the morphing operation)
"""

import sys
import os
import time

# Initialize outputs
Morphed_EPW = None
Report = "Awaiting execution..."

if Run and Baseline_EPW and Delta_Dir and Repo_Dir:
    try:
        # 1. Add our repo's 'morphing' directory to sys.path so we can import our engine
        morphing_lib_path = os.path.join(Repo_Dir, "morphing")
        if morphing_lib_path not in sys.path:
            sys.path.append(morphing_lib_path)
            
        # 2. Import the engine (this will fail if Repo_Dir is wrong)
        from epw_morphing_engine import EPWMorphingEngine
        
        # 3. Construct the Delta CSV filename
        # Expected format: bangkok_ssp585_2070.csv
        csv_filename = "bangkok_ssp{}_{}.csv".format(SSP_Scenario, Target_Year)
        delta_csv_path = os.path.join(Delta_Dir, csv_filename)
        
        if not os.path.exists(delta_csv_path):
            Report = "ERROR: Delta CSV not found at:\n" + delta_csv_path
        else:
            # 4. Construct the output EPW filename
            method_str = "btws" if Morph_Method == 1 else "belcher"
            out_filename = "Bangkok_morphed_{}_ssp{}_{}.epw".format(method_str, SSP_Scenario, Target_Year)
            
            # Save it in the same directory as the baseline EPW for convenience
            out_path = os.path.join(os.path.dirname(Baseline_EPW), out_filename)
            
            # 5. Run the Engine!
            start_time = time.time()
            engine = EPWMorphingEngine(Baseline_EPW, delta_csv_path)
            engine.morph(method=method_str)
            engine.save(out_path)
            calc_time = time.time() - start_time
            
            # 6. Output success
            Morphed_EPW = out_path
            Report = (
                "SUCCESS!\n"
                "Method: {}\n"
                "Scenario: SSP{}\n"
                "Year: {}\n"
                "Time taken: {:.2f} seconds\n\n"
                "Saved to:\n{}"
            ).format(method_str.upper(), SSP_Scenario, Target_Year, calc_time, out_path)
            
    except Exception as e:
        import traceback
        Report = "ERROR:\n" + traceback.format_exc()
elif not Run:
    Report = "Press the Run button to execute morphing."
else:
    Report = "Missing inputs. Please ensure Baseline_EPW, Delta_Dir, and Repo_Dir are provided."
