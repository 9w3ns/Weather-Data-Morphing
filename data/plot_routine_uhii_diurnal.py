"""Diurnal air-temperature + urban-heat-island graph with a daily-routine overlay.

x = hour of day (0-23), y = air temperature (deg C). For one district and season it
shows the ambient diurnal curve (from EPW dry-bulb) plus the district's urban
heat-island bump, for today (2026) and a morphed future (2050), with an office-
worker daily routine mapped on top -- so the "commute home into the peak evening
heat + UHI" (the refuge intercept) reads at a glance.

Honesty notes (also printed on the figure):
  * UHII data has only Night + Evening measured points, so the daytime UHI shape is
    MODELLED (anchored to those two values), not measured.
  * UHII here is an AIR-temperature urban-rural differential -> correct to add onto
    EPW dry-bulb (unlike LST, which is a surface signal).
  * HotDry = Mar-May and 2050 = SSP2-4.5 are editable assumptions.

Output: visualization/routine_uhii_diurnal.png
"""
import os
import csv
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch

# --------------------------------------------------------------------------- #
# CONFIG (everything tunable lives here)
# --------------------------------------------------------------------------- #
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
EPW_2026 = os.path.join(BASE, "data", "epw", "Bangkok_baseline_2026_TMYx.epw")
EPW_2050 = os.path.join(BASE, "data", "epw",
                        "Bangkok_baseline_2026_TMYx_FUTURE_2050_ssp245.epw")
UHI_CSV = os.path.join(BASE, "data", "gis", "bangkok_uhi_data.csv")
OUT_PNG = os.path.join(BASE, "visualization", "routine_uhii_diurnal.png")

DISTRICT = "Din Daeng District"
SEASON_NAME = "Hot-Dry"
SEASON_MONTHS = [3, 4, 5]                 # Mar-May
EVE_COL, NIGHT_COL = "UHII_HotDry_Evening_C", "UHII_HotDry_Night_C"
MIDDAY_UHI_FLOOR = 0.2                     # modelled daytime min (assumption)

LABEL_2026, LABEL_2050 = "2026 (today)", "2050 (SSP2-4.5)"
C_2026, C_2050 = "#2166AC", "#B2182B"     # colorblind-safe cool/warm pair
INK, MUTED = "#222222", "#6b6b6b"

# Office-worker routine: (start_hour, end_hour, label)
ROUTINE = [
    (0, 7, "Sleep"),
    (8, 9, "Commute\nout"),
    (9, 17, "Work (indoors / AC)"),
    (17, 18, "Commute\nhome"),
    (18, 21, "Evening at home"),
    (22, 24, "Sleep"),
]
EVENING_WINDOW = (18, 21)                  # the refuge-intercept highlight


# --------------------------------------------------------------------------- #
def read_epw_diurnal(path, months):
    """Mean dry-bulb (deg C) by hour-of-day (0-23) over the given months."""
    sums, counts = np.zeros(24), np.zeros(24)
    with open(path, encoding="utf-8", errors="ignore") as f:
        for _ in range(8):            # skip the 8 EPW header lines
            next(f)
        for row in csv.reader(f):
            if len(row) < 7:
                continue
            month, hour, drybulb = int(row[1]), int(row[3]), float(row[6])
            if month in months:
                h = (hour - 1) % 24   # EPW hour is 1-24
                sums[h] += drybulb
                counts[h] += 1
    return sums / np.maximum(counts, 1)


def read_uhi_anchors(csv_path, district, eve_col, night_col):
    with open(csv_path, encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if r["District"] == district:
                return float(r[eve_col]), float(r[night_col])
    raise ValueError("District not found: " + district)


def modelled_uhi_diurnal(eve, night, floor):
    """Smooth 24h UHI(hour) anchored to measured Evening (peak) + Night values.
    Shape encodes standard UHI physics: ~floor at midday, rising after sunset to
    the evening peak, elevated overnight, collapsing after sunrise. Only the
    midday floor and peak-hour placement are assumptions; eve/night are data."""
    anchors_h = [0, 4, 7, 10, 13, 16, 18, 19.5, 21, 22, 24]
    anchors_v = [night, night, 0.55 * night, 0.30 * night + 0.5 * floor, floor,
                 0.40 * eve, 0.85 * eve, eve, 0.90 * eve,
                 0.6 * eve + 0.2 * night, night]
    return np.interp(np.arange(24), anchors_h, anchors_v)


def main():
    os.makedirs(os.path.dirname(OUT_PNG), exist_ok=True)
    hours = np.arange(24)

    amb_2026 = read_epw_diurnal(EPW_2026, SEASON_MONTHS)
    amb_2050 = read_epw_diurnal(EPW_2050, SEASON_MONTHS)
    eve, night = read_uhi_anchors(UHI_CSV, DISTRICT, EVE_COL, NIGHT_COL)
    uhi = modelled_uhi_diurnal(eve, night, MIDDAY_UHI_FLOOR)

    urb_2026, urb_2050 = amb_2026 + uhi, amb_2050 + uhi

    # ---- verification (printed) ------------------------------------------- #
    ev_h = list(range(EVENING_WINDOW[0], EVENING_WINDOW[1] + 1))
    print("Ambient 2026 range: {:.1f}-{:.1f} C | 2050 range: {:.1f}-{:.1f} C"
          .format(amb_2026.min(), amb_2026.max(), amb_2050.min(), amb_2050.max()))
    print("2050 warmer than 2026 at every hour:", bool(np.all(amb_2050 > amb_2026)))
    print("UHI: peak {:.2f} (anchor eve {:.1f}) | deep-night {:.2f} (anchor {:.1f})"
          " | midday {:.2f}".format(uhi.max(), eve, uhi[2], night, uhi[13]))
    print("Evening-window UHI mean: {:.2f}".format(uhi[ev_h].mean()))

    # ---- plot ------------------------------------------------------------- #
    plt.rcParams.update({"font.size": 11, "axes.edgecolor": "#cccccc"})
    fig, ax = plt.subplots(figsize=(13, 7.2))

    # routine spans (recessive, behind everything); labels along the bottom
    ymin, ymax = 24, max(urb_2050.max(), urb_2026.max()) + 1.5
    for s, e, label in ROUTINE:
        is_eve = (s, e) == EVENING_WINDOW
        ax.axvspan(s, e, ymin=0, ymax=1,
                   color=("#F4A259" if is_eve else "#e9edf2"),
                   alpha=(0.35 if is_eve else 0.55), zorder=0, lw=0)
        ax.text((s + e) / 2, ymin + 0.25, label, ha="center", va="bottom",
                fontsize=8.5, color=(INK if is_eve else MUTED),
                fontweight=("bold" if is_eve else "normal"), zorder=1)

    # ambient (faint dashed) + urban (bold) + shaded UHII gap, per horizon
    for amb, urb, c, lab in [(amb_2026, urb_2026, C_2026, LABEL_2026),
                             (amb_2050, urb_2050, C_2050, LABEL_2050)]:
        ax.fill_between(hours, amb, urb, color=c, alpha=0.12, zorder=2)
        ax.plot(hours, amb, "--", color=c, lw=1.4, alpha=0.55, zorder=3,
                label="{} ambient".format(lab))
        ax.plot(hours, urb, "-", color=c, lw=2.6, zorder=4,
                label="{} + urban heat island".format(lab))

    # callout on the evening intercept
    ax.annotate("Commute home into peak\nevening heat + UHI\n(refuge intercept)",
                xy=(19, urb_2050[19]), xytext=(9.2, ymax - 1.3),
                fontsize=9.5, color=INK, fontweight="bold", ha="left",
                arrowprops=dict(arrowstyle="->", color=INK, lw=1.4), zorder=6)

    # UHII magnitude annotation (free upper-left)
    ax.text(0.3, ymax - 0.4,
            "Din Daeng {} UHI:  Evening +{:.1f}°C / Night +{:.1f}°C (measured)"
            .format(SEASON_NAME, eve, night),
            fontsize=9, color=MUTED, ha="left", va="top", zorder=6)

    ax.set_xlim(0, 23)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks(range(0, 24, 2))
    ax.set_xticklabels(["{:02d}:00".format(h) for h in range(0, 24, 2)])
    ax.set_xlabel("Hour of day")
    ax.set_ylabel("Air temperature (°C)")
    ax.set_title("Din Daeng — diurnal air temperature + urban heat island, {} season\n"
                 "office-worker routine mapped onto the day".format(SEASON_NAME),
                 fontsize=13, fontweight="bold")
    ax.grid(True, axis="y", color="#eeeeee", zorder=0)
    ax.legend(loc="upper right", framealpha=0.92, fontsize=8.5, ncol=1)

    fig.text(0.01, 0.008,
             "Ambient = EPW dry-bulb, mean over Mar-May; 2050 = morphed SSP2-4.5. "
             "Daytime UHI shape is MODELLED (anchored to measured Evening & Night); "
             "UHII is an air-temperature differential. Source: bangkok_uhi_data.csv, data/epw/.",
             fontsize=7.5, color=MUTED)

    plt.tight_layout(rect=(0, 0.02, 1, 1))
    plt.savefig(OUT_PNG, dpi=200)
    print("Saved", OUT_PNG)


if __name__ == "__main__":
    main()
