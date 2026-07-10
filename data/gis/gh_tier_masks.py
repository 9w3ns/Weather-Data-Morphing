#! python 3
# GHPython Script: UHI_Tier -> per-tier mask strings
#
# Inputs:
#     UHI_Tier : List of String, from gh_data_matcher.py ("Severe"/"Medium"/"Low").
# Outputs:
#     Is_Severe : List of String ("True"/"False"), True where UHI_Tier == "Severe".
#     Is_Medium : List of String ("True"/"False"), True where UHI_Tier == "Medium".
#     Is_Low    : List of String ("True"/"False"), True where UHI_Tier == "Low".
#
# Output as text, not Python bool -- bool is very likely subject to the same
# output-marshalling failure we already hit with plain int/float lists in
# this Script component (only strings have proven reliable). Wire each
# straight into a native Dispatch component's "Pattern" input -- GH's own
# native type system casts "True"/"False" text to Boolean on the receiving
# side, which is a different (working) boundary than the Script component's
# output.
import traceback

Is_Severe = []
Is_Medium = []
Is_Low = []
Report = "Awaiting UHI_Tier..."

if not UHI_Tier:
    Report = "Provide UHI_Tier."
else:
    try:
        severe_count = medium_count = low_count = 0
        for tier in UHI_Tier:
            t = str(tier).strip()
            is_severe = (t == "Severe")
            is_medium = (t == "Medium")
            is_low = (t == "Low")
            Is_Severe.append(str(is_severe))
            Is_Medium.append(str(is_medium))
            Is_Low.append(str(is_low))
            severe_count += is_severe
            medium_count += is_medium
            low_count += is_low

        Report = "{} Severe, {} Medium, {} Low, {} unrecognized.".format(
            severe_count, medium_count, low_count,
            len(UHI_Tier) - severe_count - medium_count - low_count,
        )
    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
