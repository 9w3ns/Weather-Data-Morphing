#! python 3
# GHPython Script: LCZ pixel grid (CSV) -> single colored Mesh
#
# Inputs:
#     Grid_CSV_Path  : String, path to bangkok_lcz_grid.csv (from
#                       data/fetch_lcz_grid.py -- run that first).
#     Meta_JSON_Path : String, path to bangkok_lcz_grid_meta.json (written
#                       alongside the CSV by the same script).
# Outputs:
#     Mesh          : Single Rhino Mesh, one flat-colored quad per grid
#                      cell -- a raster "pixel grid" rendered as real
#                      geometry, not a background image.
#     Legend_Text   : String describing which LCZ classes are present and
#                      how many cells each covers.
#     Legend_Mesh   : A second small Mesh, one flat-colored square swatch
#                      per LCZ class actually present, stacked in a column
#                      just to the right of the main grid -- the visual
#                      color key. Same LCZ_COLORS as the main Mesh, so
#                      it's guaranteed to match (no separately-drawn legend
#                      that could drift out of sync).
#     Legend_Points : FLAT list of Point3d, one per swatch (same order as
#                      Legend_Labels) -- anchor for a native Text Tag 3D so
#                      each swatch gets its class name/count printed next
#                      to it. Small list (<=18 items), safe to return
#                      directly (unlike the per-cell data -- see note below).
#     Legend_Labels : FLAT list of String, "LCZ n (Name): N cells", same
#                      order/count as Legend_Points.
#     Report        : String summary / error log.
#
# Unlike gh_data_matcher.py / gh_view_selector.py (which output flat lists
# of strings for *other* native GH components to assemble), this script
# builds the whole Mesh itself with RhinoCommon and returns ONE geometry
# object. A grid this size (tens of thousands of cells) would hit the same
# "Script component output channel breaks on big lists" issue noted in
# gh_geojson_to_curves.py if we tried to hand back parallel Point/Color
# lists -- a single Mesh object doesn't have that problem, so there's no
# need to round-trip through native Construct Mesh / Custom Preview here.
#
# Each cell gets its OWN 4 vertices (not shared with neighbors) so its
# color is flat / doesn't blend into adjacent cells -- this is what makes
# it look like a sharp pixel grid (matching the WRF LCZ figure) instead of
# a smoothly-interpolated surface.
#
# Coordinates in the CSV are already in the same local planar XY (meters,
# equirectangular, centered on the district geometry's mean vertex) that
# gh_geojson_to_curves.py uses -- so this Mesh lines up with your existing
# district Curves on the canvas with no extra alignment step.
#
# Wire: Grid_CSV_Path (Panel/File Path) + Meta_JSON_Path (Panel/File Path)
#   -> this component -> Mesh output -> native Custom Preview (mesh already
#   carries its own vertex colors, so Custom Preview's Colour input can be
#   left unset / white).
#
# For the color legend, wire in a second Custom Preview + a Text Tag 3D:
#   Legend_Mesh -> (another) Custom Preview
#   Legend_Points -> Text Tag 3D "Location" input
#   Legend_Labels -> Text Tag 3D "Text" input
# This draws a color-swatch column next to the pixel grid on the Rhino
# canvas, each swatch labeled with its LCZ number/name/cell count -- so
# "which color is which LCZ" is answered directly on the 3D view instead
# of needing to cross-reference LCZ_COLORS below by eye.
import csv
import json
import traceback

import Rhino.Geometry as rg
import System.Drawing as sd

# Same WUDAPT palette as data/gis/plot_lcz_map.py, kept in sync manually.
# Code 0 is not a WUDAPT class -- it's the Demuzere et al. LCZ_Filter band's
# own no-data/masked sentinel (pixels the classifier didn't confidently
# assign). Only shows up here because this script pulls raw per-pixel data
# (Phase 2b); the per-district majority vote (Phase 2 / plot_lcz_map.py)
# never surfaces it. Given an explicit entry so it renders as a distinct
# "no data" gray instead of tripping the generic unrecognized-code warning.
LCZ_COLORS = {
    0: (220, 220, 220),
    1: (139, 1, 1), 2: (204, 2, 0), 3: (252, 0, 1), 4: (190, 76, 3),
    5: (255, 102, 2), 6: (255, 152, 86), 7: (251, 237, 8), 8: (188, 188, 186),
    9: (255, 204, 167), 10: (87, 85, 90), 11: (0, 103, 0), 12: (5, 170, 5),
    13: (100, 132, 35), 14: (187, 219, 122), 15: (1, 1, 1),
    16: (253, 246, 174), 17: (106, 106, 255),
}
LCZ_NAMES = {
    0: "No data / masked",
    1: "Compact high-rise", 2: "Compact midrise", 3: "Compact low-rise",
    4: "Open high-rise", 5: "Open midrise", 6: "Open low-rise",
    7: "Lightweight low-rise", 8: "Large low-rise", 9: "Sparsely built",
    10: "Heavy industry", 11: "Dense trees", 12: "Scattered trees",
    13: "Bush, scrub", 14: "Low plants", 15: "Bare rock/paved",
    16: "Bare soil/sand", 17: "Water",
}
FALLBACK_COLOR = (200, 200, 200)

# Initialize outputs
Mesh = None
Legend_Text = ""
Legend_Mesh = None
Legend_Points = []
Legend_Labels = []
Report = "Awaiting inputs..."

if not (Grid_CSV_Path and Meta_JSON_Path):
    Report = "Provide Grid_CSV_Path and Meta_JSON_Path."
else:
    try:
        csv_path = str(Grid_CSV_Path).strip().strip('"').strip("'")
        meta_path = str(Meta_JSON_Path).strip().strip('"').strip("'")

        with open(meta_path, "r", encoding="utf-8") as f:
            meta = json.load(f)
        half_w = float(meta["cell_size_x_m"]) / 2.0
        half_h = float(meta["cell_size_y_m"]) / 2.0

        mesh = rg.Mesh()
        counts = {}
        unknown_codes = set()
        max_x = max_y = None

        with open(csv_path, "r", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                x = float(row["X"])
                y = float(row["Y"])
                code = int(row["LCZ_Code"])

                rgb = LCZ_COLORS.get(code)
                if rgb is None:
                    rgb = FALLBACK_COLOR
                    unknown_codes.add(code)
                color = sd.Color.FromArgb(rgb[0], rgb[1], rgb[2])

                i0 = mesh.Vertices.Add(x - half_w, y - half_h, 0.0)
                i1 = mesh.Vertices.Add(x + half_w, y - half_h, 0.0)
                i2 = mesh.Vertices.Add(x + half_w, y + half_h, 0.0)
                i3 = mesh.Vertices.Add(x - half_w, y + half_h, 0.0)
                mesh.Faces.AddFace(i0, i1, i2, i3)
                for _ in range(4):
                    mesh.VertexColors.Add(color)

                counts[code] = counts.get(code, 0) + 1
                max_x = x if max_x is None else max(max_x, x)
                max_y = y if max_y is None else max(max_y, y)

        mesh.Normals.ComputeNormals()
        mesh.Compact()
        Mesh = mesh

        legend_lines = [
            "LCZ {} ({}): {} cells".format(code, LCZ_NAMES.get(code, "Unknown"), n)
            for code, n in sorted(counts.items())
        ]
        Legend_Text = "\n".join(legend_lines)

        # Legend swatches: a column of squares just past the grid's right
        # edge, one per class actually present, biggest cell dimension x8
        # so each swatch reads clearly regardless of --scale. Guaranteed to
        # match the main Mesh's colors since both read the same LCZ_COLORS.
        swatch_half = max(half_w, half_h) * 8.0
        spacing = swatch_half * 2.4
        legend_x = max_x + swatch_half * 3.0
        legend_mesh = rg.Mesh()
        legend_points = []
        legend_labels = []
        for i, code in enumerate(sorted(counts.keys())):
            cx = legend_x
            cy = max_y - i * spacing
            rgb = LCZ_COLORS.get(code, FALLBACK_COLOR)
            color = sd.Color.FromArgb(rgb[0], rgb[1], rgb[2])

            i0 = legend_mesh.Vertices.Add(cx - swatch_half, cy - swatch_half, 0.0)
            i1 = legend_mesh.Vertices.Add(cx + swatch_half, cy - swatch_half, 0.0)
            i2 = legend_mesh.Vertices.Add(cx + swatch_half, cy + swatch_half, 0.0)
            i3 = legend_mesh.Vertices.Add(cx - swatch_half, cy + swatch_half, 0.0)
            legend_mesh.Faces.AddFace(i0, i1, i2, i3)
            for _ in range(4):
                legend_mesh.VertexColors.Add(color)

            legend_points.append(rg.Point3d(cx + swatch_half * 1.3, cy, 0.0))
            legend_labels.append("LCZ {} ({}): {} cells".format(
                code, LCZ_NAMES.get(code, "Unknown"), counts[code]))

        legend_mesh.Normals.ComputeNormals()
        legend_mesh.Compact()
        Legend_Mesh = legend_mesh
        Legend_Points = legend_points
        Legend_Labels = legend_labels

        Report = "Built mesh: {} cells, {} vertices, {} faces. Legend: {} classes.".format(
            sum(counts.values()), mesh.Vertices.Count, mesh.Faces.Count, len(counts))
        if unknown_codes:
            Report += "\nWARNING: unrecognized LCZ codes (colored gray): {}".format(
                ", ".join(str(c) for c in sorted(unknown_codes)))

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
