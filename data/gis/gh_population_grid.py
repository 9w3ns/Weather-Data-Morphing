#! python 3
# GHPython Script: population grid (CSV) -> single continuous-coloured Mesh
#
# Renders data/gis/bangkok_lcz_grid_population.csv as one flat-shaded quad per
# 200 m cell, coloured by a chosen population field on a perceptually-uniform
# heat ramp (inferno). Same 200 m grid + local XY frame as gh_lcz_grid_mesh.py,
# so it overlays the LCZ mesh, satellite basemap and BMA sites with no registration.
#
# Same "build the whole Mesh here and return ONE object" approach as
# gh_lcz_grid_mesh.py (a Script component's output channel breaks on tens of
# thousands of parallel Point/Colour items; a single Mesh doesn't).
#
# Inputs:
#   Grid_CSV_Path : String, path to bangkok_lcz_grid_population.csv (from
#                   data/build_worldpop_lcz_grid.py). Any grid CSV with X, Y and
#                   the chosen value column works.
#   Field         : String, which column to colour by. Default "pop_defacto_2020".
#                   Later columns (once built): pop_registered_2020,
#                   pop_nonreg_2020, pop_defacto_2050, pop_registered_2050,
#                   pop_nonreg_2050.
#   Cell_Size     : Float, cell size in metres (default 200 -- matches the LCZ grid).
#   Max_Value     : Float, people/cell mapped to the top of the ramp. <= 0 => auto
#                   (99th percentile, so a few extreme cells don't wash out the map).
# Outputs:
#   Mesh        : Single Rhino Mesh, one flat-coloured quad per cell (vertex colours
#                 baked in) -> straight into native Custom Preview (leave its Colour
#                 input unset).
#   Legend_Text : String -- field, min/max/mean, and the Max_Value used for scaling.
#   Report      : String summary / error log.
#
# Wire: Grid_CSV_Path (Panel/File Path) + Field (Panel) + Cell_Size (Slider) +
#   Max_Value (Slider) -> this component -> Mesh -> Custom Preview.
import csv
import traceback

import Rhino.Geometry as rg
import System.Drawing as sd

# Inferno control stops (0..1) -- perceptually uniform, colour-blind friendly, the
# standard for density heatmaps. Swap if you want a different ramp.
RAMP = [
    (0.00, (0, 0, 4)), (0.25, (87, 15, 109)), (0.50, (187, 55, 84)),
    (0.75, (249, 140, 10)), (1.00, (252, 255, 164)),
]

# Initialize outputs
Mesh = None
Legend_Text = ""
Report = "Awaiting inputs..."


def clean_path(p):
    return str(p).strip().strip('"').strip("'")


def ramp_color(t):
    """t in [0,1] -> System.Drawing.Color along the inferno stops."""
    if t <= 0:
        r, g, b = RAMP[0][1]
        return sd.Color.FromArgb(r, g, b)
    if t >= 1:
        r, g, b = RAMP[-1][1]
        return sd.Color.FromArgb(r, g, b)
    for i in range(len(RAMP) - 1):
        t0, c0 = RAMP[i]
        t1, c1 = RAMP[i + 1]
        if t0 <= t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0.0
            r = int(c0[0] + f * (c1[0] - c0[0]))
            g = int(c0[1] + f * (c1[1] - c0[1]))
            b = int(c0[2] + f * (c1[2] - c0[2]))
            return sd.Color.FromArgb(r, g, b)
    r, g, b = RAMP[-1][1]
    return sd.Color.FromArgb(r, g, b)


if not Grid_CSV_Path:
    Report = "Provide Grid_CSV_Path."
else:
    try:
        field = str(Field).strip() if "Field" in globals() and Field else "pop_defacto_2020"
        cell = float(Cell_Size) if "Cell_Size" in globals() and Cell_Size not in (None, "") else 200.0
        max_in = float(Max_Value) if "Max_Value" in globals() and Max_Value not in (None, "") else 0.0
        half = cell / 2.0

        rows = []
        with open(clean_path(Grid_CSV_Path), "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            if field not in reader.fieldnames:
                raise ValueError("Field '{}' not in CSV columns: {}".format(
                    field, reader.fieldnames))
            for row in reader:
                try:
                    rows.append((float(row["X"]), float(row["Y"]), float(row[field])))
                except (ValueError, TypeError):
                    continue

        vals = [v for _, _, v in rows]
        if not vals:
            raise ValueError("No numeric rows for field '{}'.".format(field))

        if max_in > 0:
            vmax = max_in
        else:
            s = sorted(vals)
            vmax = s[int(0.99 * (len(s) - 1))] or max(s) or 1.0  # 99th pct, guard 0
        vmax = vmax if vmax > 0 else 1.0

        mesh = rg.Mesh()
        for x, y, v in rows:
            t = v / vmax
            if t < 0:
                t = 0.0
            if t > 1:
                t = 1.0
            color = ramp_color(t)
            i0 = mesh.Vertices.Add(x - half, y - half, 0.0)
            i1 = mesh.Vertices.Add(x + half, y - half, 0.0)
            i2 = mesh.Vertices.Add(x + half, y + half, 0.0)
            i3 = mesh.Vertices.Add(x - half, y + half, 0.0)
            mesh.Faces.AddFace(i0, i1, i2, i3)
            for _ in range(4):
                mesh.VertexColors.Add(color)

        mesh.Normals.ComputeNormals()
        mesh.Compact()
        Mesh = mesh

        vmin = min(vals)
        vmean = sum(vals) / len(vals)
        Legend_Text = ("Field: {}\nmin {:.0f} | mean {:.1f} | max {:.0f} people/cell\n"
                       "Colour ramp top (Max_Value) = {:.0f} {}").format(
            field, vmin, vmean, max(vals), vmax,
            "(auto 99th pct)" if max_in <= 0 else "(manual)")
        Report = "Built grid mesh: {} cells, {} faces. Total {:,.0f} people.".format(
            len(rows), mesh.Faces.Count, sum(vals))

    except Exception:
        Report = "ERROR:\n" + traceback.format_exc()
