#! python 3
import sys
import os
import time
import traceback

# Initialize outputs
Morphed_EPW = None
Report = "Awaiting execution..."

if not Run:
    Report = "Press the Run button to execute morphing."
elif not Baseline_EPW or not Delta_Dir or not Repo_Dir:
    Report = "Missing inputs. Please ensure Baseline_EPW, Delta_Dir, and Repo_Dir are provided."
else:
    try:
        # 1. Add our repo's 'morphing' directory to sys.path so we can import our engine
        morphing_lib_path = os.path.join(Repo_Dir, "morphing")
        if morphing_lib_path not in sys.path:
            sys.path.append(morphing_lib_path)
            
        # 2. Import the engine (this will fail if Repo_Dir is wrong)
        from epw_morphing_engine import EPWMorphingEngine
        
        # 3. Construct the Delta CSV filename
        csv_filename = "bangkok_ssp{}_{}.csv".format(int(SSP_Scenario), int(Target_Year))
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
        Report = "ERROR:\n" + traceback.format_exc()
