# Plan: 3-season evening UHII average — supplementary + diagnostic

## Context
The site-evaluation UHI criterion currently uses a single season's evening value,
`UHII_HotDry_Evening_C`, as its primary driver (`data/build_site_selection_matrix.py`
line 63, weighted 0.7 within the 35% UHI criterion). The question: can we average the
evening UHII across the **three seasons** (CoolDry / HotDry / Wet) per district, and
is that average *relevant*?

**Finding (from a read-only analysis of `bangkok_uhi_data.csv`):** the average is
trivial to compute, but a *plain* 3-season mean is **less** thesis-relevant than the
hot-season peak and would be misleading as the primary driver, because:

- Season magnitudes differ: cool-dry evening UHII averages **3.13 °C**, hot-dry
  **2.16**, wet **2.05** — a plain mean is dominated by the **cool-dry** season,
  which has the *highest* UHI intensity but the *lowest* heat-health danger (cool
  ambient temperatures).
- The seasons disagree on which districts are worst (cool-dry vs hot-dry evening
  correlation ≈ **0.40**). Top-6 by hot-dry (Don Mueang, Sai Mai, Bang Khen —
  peripheral open areas) is nearly disjoint from top-6 by 3-season mean (Din Daeng,
  Phaya Thai, Chatuchak — dense core). **Din Daeng moves #12 → #2.** So the metric
  choice materially changes the winners.

So the average is valuable as a **robustness / seasonal-consistency diagnostic**,
not as a replacement primary — the chosen role below.

## Decision
**Supplementary + diagnostic.** Keep `UHII_HotDry_Evening_C` as the MCDA primary
(unchanged). Add derived evening columns and a sensitivity check.

## Approach

### 1. `data/merge_uhi_data.py` — add 3 derived columns at the source
After the six `UHII_COLUMNS` are populated per district, compute from the three
`*_Evening_C` values and append to `fieldnames` (after `UHII_COLUMNS`):

| Column | Definition | Purpose |
|---|---|---|
| `UHII_Eve_Mean_C`  | mean(CoolDry, HotDry, Wet) evening | cross-season average |
| `UHII_Eve_Peak_C`  | max of the three | worst-season evening |
| `UHII_Eve_Range_C` | max − min | seasonal consistency (**low = hot every evening season**) |

Round to 2 dp to match existing columns. Regenerate `bangkok_uhi_data.csv` by
running the script (added here, not hand-edited, so it stays reproducible).

### 2. `data/build_site_selection_matrix.py` — diagnostic only, primary untouched
- `load_rows()`: also read `UHII_Eve_Mean_C` (and `UHII_Eve_Range_C`) into each row.
  The primary `"evening"` field stays `UHII_HotDry_Evening_C` — **no change to
  `WEIGHTS`, `score()`, or the primary ranking.**
- Add a diagnostic `eve_metric_sensitivity(rows, base_top3)` mirroring the existing
  `sensitivity()` pattern: re-score with the evening driver swapped to the 3-season
  **mean** (and optionally **peak**), print `STABLE`/`CHANGED` for the top-3 and the
  alternate top-5. This directly answers "is the ranking robust to the evening
  metric?" and surfaces the Din Daeng shift.
- Add `UHII_Eve_Mean_C` and `UHII_Eve_Range_C` to the output `site_selection_scores.csv`
  as **informational (non-scored)** columns — cheap, and useful for GH coloring /
  the sensitivity narrative.

### 3. `docs/SiteSelectionMatrixGemini.md` — document the judgment
In the §2 metric caveat / §3 criterion-1 area, add a short note: seasonal evening
average computed as a diagnostic; cool-dry dominates magnitude but is least
dangerous, so hot-dry retained as primary; cross-season ranking instability
(≈0.40 corr, Din Daeng #12→#2) recorded; `UHII_Eve_Range_C` flags all-season-hot
districts. Include the key numbers above.

## Reuse (don't re-implement)
- `minmax()`, `score()`, and the `sensitivity()` scenario-loop pattern —
  `data/build_site_selection_matrix.py`.
- `UHII_COLUMNS` + `fieldnames` assembly — `data/merge_uhi_data.py`.

## Verification
- Run `merge_uhi_data.py`; assert the 3 new columns exist and match a hand calc for
  a spot district (Din Daeng evening 4.0 / 2.7 / 2.8 → Mean **3.17**, Peak 4.0,
  Range 1.3).
- Run `build_site_selection_matrix.py`; **regression:** the primary top-3 and every
  `score` / `s_uhi` value must be **identical** to the pre-change output (proves the
  primary is untouched). Confirm the new diagnostic prints the mean-driver top-3
  (Din Daeng should climb) with a STABLE/CHANGED verdict.

## Files
- **Edit:** `data/merge_uhi_data.py`, `data/build_site_selection_matrix.py`,
  `docs/SiteSelectionMatrixGemini.md`
- **Regenerated:** `data/gis/bangkok_uhi_data.csv`, `data/gis/site_selection_scores.csv`

## Relevance verdict (the answer to the question)
Yes, computable — but the plain 3-season average is **not** a better primary than
the hot-season evening peak (it dilutes the danger season and reshuffles the
ranking). It **is** relevant as a **consistency/robustness diagnostic**:
`UHII_Eve_Mean_C` for a sensitivity check, `UHII_Eve_Range_C` to flag districts that
are hot across *all* evening seasons. That supplementary role is what this plan
implements.
