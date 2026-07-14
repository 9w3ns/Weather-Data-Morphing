#! python 3
# GHPython Script: Bangkok rapid-transit network (CSV) -> points + edge curves
#
# Reads the two CSVs written by data/fetch_transit_network.py and rebuilds the
# rail network as Grasshopper geometry, aligned to the same local planar XY as
# your district Curves (gh_geojson_to_curves.py) and LCZ grid mesh
# (gh_lcz_grid_mesh.py) -- so it drops onto the existing canvas with no extra
# registration step.
#
# Inputs:
#     Nodes_CSV_Path : String, path to data/gis/bangkok_transit_nodes.csv
#     Edges_CSV_Path : String, path to data/gis/bangkok_transit_edges.csv
# Outputs:
#     Edge_Curves  : FLAT list of LineCurve, one per station-to-station link.
#                    *** This is the network to feed a centrality plugin. ***
#                    Interchange stations share identical endpoints across
#                    lines, so a graph builder (DeCodingSpaces Toolbox "Spatial
#                    Graph Analysis" / Urbano) will connect the lines correctly
#                    and let you compute Betweenness / Closeness / Degree.
#     Edge_Colors  : FLAT list of Color, same order as Edge_Curves, colored by
#                    line (BTS/MRT/etc.) -> wire with Edge_Curves into a Custom
#                    Preview to see the colored network.
#     Node_Points  : FLAT list of Point3d, one per station.
#     Node_Names   : FLAT list of String, station names (same order as points).
#     Node_Degrees : FLAT list of int, network degree per station (2 = mid-line,
#                    1 = terminus, >=3 = junction/interchange). Use to size or
#                    color the points so hubs stand out before you even run a
#                    plugin.
#     Node_Lines   : FLAT list of String, "|"-joined lines serving each station.
#     Legend_Text  : String, line -> color key + network summary.
#     Report       : String summary / error log.
#
# HOW TO GET CENTRALITY (route B):
#   Edge_Curves -> DeCodingSpaces Toolbox: "Graph From Curves" (or "Segment
#   Map") -> "Centrality (Betweenness/Closeness)" -> color/size Node_Points by
#   the returned values. Betweenness ~ "intercept potential" (through-flow),
#   which is the thesis's threshold/intercept concept made quantitative.
#   Alternatively feed Edge_Curves into Urbano as the network layer.
#
# List sizes here are small (~160 nodes / ~160 edges), so flat parallel lists
# are safe to return directly (unlike the tens-of-thousands-cell LCZ grid,
# which had to be baked into a single Mesh -- see gh_lcz_grid_mesh.py).
import csv
import traceback

import Rhino.Geometry as rg
import System.Drawing as sd

# Approximate official line colors (RGB).
LINE_COLORS = {
    "BTS Sukhumvit": (0, 164, 80),    "BTS Silom": (0, 104, 56),
    "MRT Blue": (30, 60, 150),        "MRT Purple": (130, 40, 140),
    "MRT Pink": (233, 30, 140),       "MRT Yellow": (250, 200, 0),
    "Gold Line": (196, 156, 60),      "ARL": (200, 30, 40),
}
MULTI_COLOR = (90, 90, 90)   # edge shared by >1 line
FALLBACK = (150, 150, 150)

Edge_Curves = []
Edge_Colors = []
Node_Points = []
Node_Names = []
Node_Degrees = []
Node_Lines = []
Legend_Text = ""
Report = "Awaiting inputs..."

if not (Nodes_CSV_Path and Edges_CSV_Path):
    Report = "Provide Nodes_CSV_Path and Edges_CSV_Path."
else:
    try:
        nodes_path = str(Nodes_CSV_Path).strip().strip('"').strip("'")
        edges_path = str(Edges_CSV_Path).strip().strip('"').strip("'")

        lines_present = set()
        with open(nodes_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                Node_Points.append(rg.Point3d(float(row["X"]), float(row["Y"]), 0.0))
                Node_Names.append(row.get("Name", ""))
                Node_Degrees.append(int(row.get("Degree", 0)))
                Node_Lines.append(row.get("Lines", ""))
                for ln in row.get("Lines", "").split("|"):
                    if ln:
                        lines_present.add(ln)

        with open(edges_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                a = rg.Point3d(float(row["From_X"]), float(row["From_Y"]), 0.0)
                b = rg.Point3d(float(row["To_X"]), float(row["To_Y"]), 0.0)
                Edge_Curves.append(rg.LineCurve(a, b))
                edge_lines = [x for x in row.get("Lines", "").split("|") if x]
                if len(edge_lines) == 1:
                    rgb = LINE_COLORS.get(edge_lines[0], FALLBACK)
                elif len(edge_lines) > 1:
                    rgb = MULTI_COLOR
                else:
                    rgb = FALLBACK
                Edge_Colors.append(sd.Color.FromArgb(*rgb))

        interchanges = sum(1 for d in Node_Degrees if d >= 3)
        legend = ["{}  RGB{}".format(ln, LINE_COLORS.get(ln, FALLBACK))
                  for ln in sorted(lines_present)]
        Legend_Text = ("Lines: {}\nStations: {}  Edges: {}  Junctions(deg>=3): {}"
                       "\n".format(len(lines_present), len(Node_Points),
                                   len(Edge_Curves), interchanges)
                       + "\n".join(legend))
        Report = "OK. {} stations, {} edges, {} lines, {} junctions.".format(
            len(Node_Points), len(Edge_Curves), len(lines_present), interchanges)

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
