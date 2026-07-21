# Plan: spread the BMA land search beyond the three Tier-1 districts

**Status:** APPROVED & implemented 2026-07-20. Subset = 21 districts
(`Severe ∪ intercept≥30 ∪ Bang Na`); `build` runs at `--min-area 500`; provenance
manifest (§6.4) included. Implemented as `fetch_bma_parcels.py --around-facilities`.
**Trigger:** "district tier may not be as important as site-specific" — evaluate
candidate city land wherever it is, not only in Bang Rak / Sathon / Khlong Toei.
**Decisions locked (from grilling):** coverage = **UHI/transit priority subset
(~20 districts)**; seeds = **all confidences (high + medium + low)**.

---

## 1. The realisation that makes this cheap

The three-district limit was **only ever on Stage 1 (parcels)**. Stage 2
(`fetch_bma_facilities.py`) already fetches **all of Bangkok**:

- `ox.features_from_place("Bangkok, Thailand", ...)` → OSM facilities citywide
- the full 437-school BMA registry → citywide

`bangkok_bma_facilities.geojson` therefore already holds **2,537 facility seeds in
all 50 districts** (502 high / 190 medium / 1,845 low). We are **not missing any
city-operated sites** outside the three districts — we only lack the *parcel
geometry* under the ones elsewhere.

**Consequence:** we do NOT re-crawl 2.2M parcels. We fetch parcels **only where
BMA facility seeds are**, inside the priority subset. Full-district parcel fetching
is rejected: parcels carry no owner attribute, so extra parcels become grey context
only — they never produce a new ownership answer. (Vacant BMA land stays invisible
either way; that limitation is unchanged and out of scope here.)

## 2. Defining the priority subset (data-driven, parameterised)

From `bangkok_uhi_data.csv` and `bangkok_intercept_scores.csv`:

```
priority = { UHI_Tier == "Severe" }  ∪  { Intercept_Score_Pct >= 30 }
```

- **UHI_Tier == "Severe"** → 18 districts (the heat case).
- **Intercept_Score_Pct >= 30** → Bang Rak, Yan Nawa, Sathon, Bang Kho Laem,
  Din Daeng, Khlong Toei (the transit-interception case). All but **Yan Nawa** and
  **Khlong Toei** are already Severe.

**Union = 20 districts:**

> Pom Prap Sattru Phai, Samphanthawong, Din Daeng, Phaya Thai, Phra Nakhon,
> Ratchathewi, Bang Rak, Khlong San, Pathum Wan, Bang Sue, Bangkok Yai, Thon Buri,
> Dusit, Sathon, Bang Phlat, Chatuchak, Bang Kho Laem, Vadhana, Yan Nawa,
> Khlong Toei

The three current districts are all inside this set, so **17 new districts** get
added. The threshold (`Severe`, `intercept >= 30`) is a CLI/config knob, so the set
is easy to widen or narrow in review — it is not hard-coded folklore.

## 3. The fetch change: seed-driven, not district-driven

Add a mode to `fetch_bma_parcels.py` (`--around-facilities`), reusing the existing
`query_envelope` + `fetch_recursive` machinery:

1. Load `bangkok_bma_facilities.geojson`; load districts; compute the priority
   subset (§2).
2. Keep only facilities whose location falls inside the subset (point-in-union).
   All confidences kept — no `ownership_confidence` filter here; the seed set is
   deliberately wide and `build_bma_land_layer.py` does the ranking downstream.
3. Buffer each seed in metres (UTM47N): **polygon footprint + 50 m**, **point
   ± 150 m** (parcels can be large; this guarantees the containing parcel is
   returned). These feed `build`'s existing match logic, which only ever claims
   parcels the footprint intersects, or the single parcel under a point.
4. `unary_union` the buffered seeds → disjoint blobs. This **merges clustered
   facilities in dense inner districts into one envelope each**, cutting redundant
   requests. Fetch each blob's bounding box with `fetch_recursive` (its recursive
   split already handles any envelope that trips the 1000-feature cap — provably
   complete).
5. De-duplicate parcels on `OBJECTID`; assign `district` by centroid-in-district
   (existing convention); tag `fetch_mode = "seeded"` for provenance.
6. Write per-district `bangkok_parcels_<slug>.geojson` — **same filename
   convention**, so `build_bma_land_layer.py`'s glob picks them up with **zero
   changes to Stage 3**.

**Do not overwrite the three existing full-parcel files.** Skip any district that
already has a `bangkok_parcels_<slug>.geojson` unless `--force` is passed. Bang Rak
/ Sathon / Khlong Toei keep their full cadastral context; the 17 new districts get
seeded (sparse-but-sufficient) parcels.

### Cost

~20 districts × facilities ≈ **1,000–1,300 seeds** in-subset (of 2,537 citywide).
After the `unary_union` merge, realistically **~400–700 fetch envelopes**. At
0.5 s/request + recursion + HTTP caching (re-runs free): **~5–12 min**, gentle on
the one public government server.

## 4. Downstream (no code change, just re-run)

```
python data/fetch_bma_parcels.py --around-facilities      # new mode, 17 new districts
python data/build_bma_land_layer.py --min-confidence low --min-area 2000
python  # (Grasshopper) gh_bma_land.py  -> curves
```

- Run `build` at `--min-confidence low` so medium/low seeds surface; the temple and
  oversized-parcel guards still demote false positives, and `land_owner_risk` /
  `ownership_confidence` remain the columns to sort and filter on.
- `--min-area 2000` unchanged (a civic centre needs real land). Open to lowering
  if you want to see smaller site-specific candidates — flag in review.

## 5. Docs

Add a section to `docs/bma_land_sourcing_notes.md`: the priority-subset definition,
the seed-driven method, and **two new caveats** —
1. **Mixed parcel density.** The 3 original districts have full cadastral fabric;
   the 17 new ones have parcels only around facilities. Fine for the ownership
   question, but the context map (§9 in `build`) is sparser outside the original 3.
2. **Verification burden scales with the net.** Including low-confidence seeds
   across 20 districts will produce many more `low` candidates. `high` still means
   "no disqualifier found", not "title confirmed" — every surviving site is audited
   individually, as before.

## 6. Open questions for review

1. **Subset threshold** — happy with `Severe ∪ intercept>=30` (20 districts), or
   push to all Medium-tier too (~34 districts)?
2. **`--min-area`** — keep 2,000 m², or lower to catch smaller site-specific plots?
3. **Point-seed buffer (150 m)** — fine, or tighter to reduce stray parcels?
4. **Provenance** — worth writing a `bangkok_parcels_seeded_manifest.csv` (which
   districts were seeded vs full, seed counts) for the thesis methods section?
