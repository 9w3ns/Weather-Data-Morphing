"""
Standalone LCZ choropleth for Bangkok districts -- no Grasshopper/Rhino
required. Reads bangkok_districts.geojson + bangkok_lcz_data.csv directly,
so it's useful for sanity-checking the per-district LCZ classification
(e.g. "why does district X show as LCZ 6?") against the source data,
independent of whatever curve order / matching happened on the GH canvas.

Usage:
    python data/gis/plot_lcz_map.py
    python data/gis/plot_lcz_map.py --highlight "Sathon"
    python data/gis/plot_lcz_map.py --out lcz_map.png
"""
import argparse
import csv
import json
import os

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection

# Official WUDAPT LCZ palette (Stewart & Oke 2012 / Demuzere et al. 2022).
LCZ_COLORS = {
    1: "#8b0101", 2: "#cc0200", 3: "#fc0001", 4: "#be4c03", 5: "#ff6602",
    6: "#ff9856", 7: "#fbed08", 8: "#bcbcba", 9: "#ffcca7", 10: "#57555a",
    11: "#006700", 12: "#05aa05", 13: "#648423", 14: "#bbdb7a",
    15: "#010101", 16: "#fdf6ae", 17: "#6a6aff",
}
LCZ_NAMES = {
    1: "Compact high-rise", 2: "Compact midrise", 3: "Compact low-rise",
    4: "Open high-rise", 5: "Open midrise", 6: "Open low-rise",
    7: "Lightweight low-rise", 8: "Large low-rise", 9: "Sparsely built",
    10: "Heavy industry", 11: "Dense trees", 12: "Scattered trees",
    13: "Bush, scrub", 14: "Low plants", 15: "Bare rock/paved",
    16: "Bare soil/sand", 17: "Water",
}


def normalize_name(name):
    n = str(name).strip().lower()
    for token in ("khet ", " district"):
        n = n.replace(token, "")
    return n.strip()


def load_lcz_data(csv_path):
    data = {}
    with open(csv_path, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            data[normalize_name(row["District"])] = row
    return data


def polygon_rings(geometry):
    """Yield (exterior, [holes]) coordinate lists for Polygon/MultiPolygon."""
    if geometry["type"] == "Polygon":
        coords = geometry["coordinates"]
        yield coords[0], coords[1:]
    elif geometry["type"] == "MultiPolygon":
        for coords in geometry["coordinates"]:
            yield coords[0], coords[1:]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--highlight", default=None,
                         help="District name substring to outline in the plot title/border")
    parser.add_argument("--out", default=None,
                         help="Save PNG to this path instead of showing interactively")
    args = parser.parse_args()

    base_dir = os.path.dirname(os.path.abspath(__file__))
    geojson_path = os.path.join(base_dir, "bangkok_districts.geojson")
    csv_path = os.path.join(base_dir, "bangkok_lcz_data.csv")

    with open(geojson_path, encoding="utf-8") as f:
        geojson = json.load(f)
    lcz_data = load_lcz_data(csv_path)

    fig, ax = plt.subplots(figsize=(11, 11))
    patches, colors = [], []
    unmatched = []

    for feat in geojson["features"]:
        name = feat["properties"]["District"]
        clean = normalize_name(name)
        row = lcz_data.get(clean)
        if row is None:
            unmatched.append(name)
            code = None
        else:
            code = int(row["LCZ_Code"])
        color = LCZ_COLORS.get(code, "#cccccc")

        is_hl = args.highlight and args.highlight.lower() in clean

        for exterior, holes in polygon_rings(feat["geometry"]):
            xy = [(pt[0], pt[1]) for pt in exterior]
            poly = Polygon(xy, closed=True)
            patches.append(poly)
            colors.append(color)
            ax.add_patch(Polygon(
                xy, closed=True, facecolor="none",
                edgecolor="#000000" if is_hl else "#555555",
                linewidth=2.5 if is_hl else 0.5, zorder=5 if is_hl else 2,
            ))

        # Centroid label (simple average of exterior ring, fine for compact districts).
        ring = list(polygon_rings(feat["geometry"]))[0][0]
        cx = sum(p[0] for p in ring) / len(ring)
        cy = sum(p[1] for p in ring) / len(ring)
        label = name.replace(" District", "")
        conf = " ({}%)".format(row["LCZ_Confidence_Pct"]) if row else ""
        ax.text(cx, cy, "{}\nLCZ {}{}".format(label, code if code else "?", conf),
                fontsize=5.5, ha="center", va="center", zorder=6,
                weight="bold" if is_hl else "normal")

    pc = PatchCollection(patches, facecolor=colors, edgecolor="none", zorder=1)
    ax.add_collection(pc)

    ax.autoscale_view()
    ax.set_aspect("equal")
    ax.axis("off")
    title = "Bangkok districts by dominant LCZ (Demuzere et al. 2022 global map)"
    if args.highlight:
        title += "  -- highlighting '{}'".format(args.highlight)
    ax.set_title(title, fontsize=13)

    # Legend: only classes actually present in the data.
    present = sorted({int(r["LCZ_Code"]) for r in lcz_data.values()})
    handles = [
        plt.Rectangle((0, 0), 1, 1, facecolor=LCZ_COLORS[c])
        for c in present
    ]
    labels = ["LCZ {} ({})".format(c, LCZ_NAMES.get(c, "?")) for c in present]
    ax.legend(handles, labels, loc="upper left", bbox_to_anchor=(1.0, 1.0),
               fontsize=8, frameon=False, title="Dominant LCZ")

    if unmatched:
        print("WARNING: no LCZ data matched for: {}".format(", ".join(unmatched)))

    plt.tight_layout()
    if args.out:
        plt.savefig(args.out, dpi=200, bbox_inches="tight")
        print("Saved to {}".format(args.out))
    else:
        plt.show()


if __name__ == "__main__":
    main()
