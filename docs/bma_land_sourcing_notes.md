# Sourcing land under BMA ownership

Provenance note for the BMA land layer. Written so the thesis can cite where this
data came from, what it is not, and so nobody repeats the search below.

**Sweep date:** 2026-07-15. **Question:** which Bangkok land plots are owned by the
Bangkok Metropolitan Administration? The thesis proposes a civic centre on city
land, so this is a hard gate on site selection, not a nice-to-have.

---

## 1. The Excel file does not appear to be public

The starting hypothesis was a rumoured Excel file of BMA-owned plots. It could not
be found. What was checked:

| Source | Result |
|---|---|
| `data.bangkok.go.th` (BMA's own CKAN portal) | 169 datasets. Land **use** only (`การใช้ประโยชน์ที่ดิน`). No ownership dataset. |
| `data.go.th` (national open data) | The BMA organisation returns **0** datasets. Only property-**tax** aggregates by district (`gad0016`, `propertytax`). |
| `asset.bangkok.go.th` — *ตรวจสอบทรัพย์สินของกรุงเทพมหานคร*, สำนักการคลัง | **The system that actually holds this.** Login-gated; no public export. |
| `bmagis.bangkok.go.th` `/ckan`, `/greenparks` folders | HTTP 499 Token Required. |
| `cityplangis.bangkok.go.th` `SERVICE_PUBLIC/Parcel` | Public — but **geometry only**, see below. |
| Thai + English web search | No public file. |

**Conclusion: the authoritative registry exists but is not published.** If the real
file is ever needed, the path is a data request to **สำนักการคลัง** (BMA Finance
Office, which runs the asset registry) or **กองทะเบียนทรัพย์สินและพัสดุ**. Everything
below is a proxy built because that file was unavailable.

## 2. What is public, and what it gives you

### Cadastral parcels — real boundaries, zero ownership

BMA's City Planning department (`สำนักการวางผังและพัฒนาเมือง`) publishes an
unauthenticated ArcGIS service:

```
https://cityplangis.bangkok.go.th/arcgis/rest/services/SERVICE_PUBLIC/Parcel/MapServer/0
layer "รูปแปลงที่ดิน" | 2,220,982 polygons | wkid 32647 | f=geojson | maxRecordCount 1000
```

This is the real cadastral fabric for all 50 districts — a genuine upgrade on the
OSM `landuse` polygons used by `fetch_vacant_plots_osm.py`, which are tagging
artefacts rather than property boundaries.

**Its only attribute is `OBJECTID`.** No owner, no title deed (โฉนด), no land use,
not even a district. It answers *where the plot boundaries are* and never *whose
plot this is*. It publishes **no metadata date**, so its vintage is unknown.

Fetched by `data/fetch_bma_parcels.py`, district-scoped (all 2.2M parcels would be
2,200+ requests against a public government server). Bang Rak alone returns 13,708
parcels, median **61 m²** — Bangkok's shophouse grain.

### BMA-operated facilities — the ownership seed

Since ownership is unpublished, it is **inferred**: the city operates a facility,
so the city probably owns the land under it. Two sources, weighted differently by
`data/fetch_bma_facilities.py`:

1. **BMA open data** — `ที่ตั้งโรงเรียนในสังกัดกรุงเทพมหานคร` (`bma_school.csv`, 437
   schools with lat/lng). An authoritative BMA registry → `high`.
2. **OpenStreetMap** — broader coverage plus real footprint polygons, but
   `operator` tagging in Bangkok is sparse, so most rows can only be `low`.

`data/build_bma_land_layer.py` intersects the two: parcels under a BMA facility,
dissolved into whole sites with real areas.

## 3. The finding that matters: operating ≠ owning

The inference is not merely theoretically shaky. It **measurably broke, twice**, and
how it broke is the most useful thing in this document. Both failures are the same
lesson — *the city running a facility does not mean the city owns the ground* — and
both were caught only because the top results were audited individually.

### 3a. Temple land (ธรณีสงฆ์)

Bang Rak's first high-confidence results were 1 district office and 5 BMA schools.
Every school was a **วัด school**. Checked against OSM temple compounds:

| Site | Temple overlap |
|---|---|
| โรงเรียนวัดม่วงแค | 93% |
| โรงเรียนวัดหัวลำโพง | 87% |
| โรงเรียนวัดมหาพฤฒาราม | 79% |
| โรงเรียนวัดแก้วแจ่มฟ้า | 70% |
| โรงเรียนวัดสวนพลู | 54% |
| สำนักงานเขตบางรัก (district office) | **0%** |

BMA runs these schools; the **temple owns the ground**. Seeding off the school
claimed entire wat compounds as city land. `data/gis/bangkok_temple_land.geojson`
is now an explicit exclusion layer, and any site ≥25% covered by a temple is
demoted to `low` with its `temple_overlap_pct` recorded.

### 3b. Tenancy on a state-enterprise estate

Worse, and more instructive. Khlong Toei's "BMA school" (โรงเรียนชุมชนหมู่บ้านพัฒนา)
claimed a **single 240,443 m² parcel** — 24 hectares. That parcel is the **Port
Authority of Thailand estate** (ท่าเรือกรุงเทพ). The same parcel also contains the
National Housing Authority flats (แฟลตการเคหะคลองเตย), a mosque, a railway and
several other schools. PAT is a **state enterprise**; the land is not the city's.

`NOT_BMA_PATTERNS` could not catch this — the OSM `operator` tag is simply absent,
which is the normal case in Bangkok. The fix is therefore **geometric, needing no
tags**: a facility only justifies claiming land commensurate with its own
footprint. Where the containing parcel dwarfs the building, the facility is a
**tenant** on someone's estate. Sites are demoted when
`parcel_to_seed_ratio > 10` (polygon seeds) or, for point seeds where no footprint
exists, when area > 20,000 m².

**Generalise this.** The same gap certainly exists for classes still undetectable —
leased offices, ราชพัสดุ (Treasury) land the city merely occupies. A `high` rating
means **"no disqualifier found", not "title confirmed"**.

## 4. Result

Across the three Tier 1 districts (Bang Rak, Sathon, Khlong Toei), 13 candidate
sites were built and **10 were demoted** by the guards above. Three survive at
`high`, and all three are **district offices** — the one facility class
unambiguously on city land:

| Site | Area | Seed ratio | Nearest station |
|---|---|---|---|
| สำนักงานเขตคลองเตย | **12,199 m²** | 9.7 | 1,182 m |
| สำนักงานเขตสาทร | 2,938 m² | (point seed) | 2,610 m |
| สำนักงานเขตบางรัก | 2,134 m² | 2.0 | 713 m |

Each was audited against OSM: the Khlong Toei parcel contains **only** the
สำนักงานเขตคลองเตย townhall and its building — a genuine 1.2 ha city compound
(building plus yard), and the only surviving site with real room for a civic
centre.

Two findings worth arguing in the thesis:

1. **Bang Rak — the Tier 1 winner in `docs/SiteSelectionMatrixGemini.md` — has
   almost no city-owned land** (one 2,134 m² office). The UHI case and the
   land-availability case point at different districts. That tension needs an
   explicit answer, not an assumption.
2. **Khlong Toei is the only one of the three with a viable BMA site**, and it is
   a severe-UHI district — but note its `parcel_to_seed_ratio` of 9.7 sits just
   under the demotion threshold of 10. That threshold is a judgement call, not a
   measurement; see §5.8.

## 5. Limitations

1. **Inferred from operation, not read from a title.** Not legal evidence. Confirm
   with สำนักการคลัง or the Department of Lands before committing to any site.
2. **Vacant BMA land is invisible.** No facility → no seed. This finds *underused*
   city sites (district office car parks, tired markets, school edges), not empty
   ones. For vacant city land the one public lead is the **สวน 15 นาที** programme
   (`greener.bangkok.go.th`), where BMA screened 107 plots and reported 42 as
   BMA-owned — not yet wired up.
3. **Public ≠ BMA's.** Bangkok has extensive **Crown Property Bureau**, **State
   Railway (SRT)**, **Port Authority**, **Treasury (ราชพัสดุ)** and university land.
   National ministries sit on Treasury land, not the city's. `NOT_BMA_PATTERNS`
   drops these when tagged — but only **4 facilities city-wide** were caught that
   way, because OSM `operator` tags are sparse. **This tag filter is weak**; the
   geometric guard in §3b is what actually caught the Port Authority estate.
4. **Temple land** — see §3a. Detected, but only where OSM maps the compound. An
   unmapped wat is an undetected false positive.
5. **OSM operator sparsity** — of 2,537 candidate facilities only 502 reach `high`,
   and most of those come from the school registry rather than OSM tags. For a
   hard ownership gate this is the right trade: precision over recall.
6. **Point seeds under-measure.** A facility mapped as a point claims only the
   parcel under the point, not its grounds; `site_area_sqm` for
   `seed_geom == 'Point'` (e.g. สำนักงานเขตสาทร) is a **lower bound**.
7. **Parcel vintage unknown** — the service publishes no date.
8. **The oversized-parcel threshold is a judgement call.** `parcel_to_seed_ratio > 10`
   separated the Port Authority estate (ratio ~48) from real district-office
   compounds — but สำนักงานเขตคลองเตย passed at **9.7**, i.e. barely. The ratio
   conflates two different things: a genuinely low-coverage compound (a small
   building on its own yard — fine) and a tenant on a large estate (not fine). A
   district office with a bigger car park would be wrongly demoted. A better
   discriminator would be *"does this parcel contain other unrelated major
   facilities?"* — which is what actually distinguished the two cases on audit.
   Until then: **audit every surviving site individually**, as was done in §4.

## 6. Pipeline

```
data/fetch_bma_parcels.py       -> data/gis/bangkok_parcels_<district>.geojson
  (--around-facilities mode)       data/gis/bangkok_parcels_seeded_manifest.csv
data/fetch_bma_facilities.py    -> data/gis/bangkok_bma_facilities.geojson
                                   data/gis/bangkok_temple_land.geojson
data/build_bma_land_layer.py    -> data/gis/bangkok_bma_land.geojson
                                   data/gis/bangkok_bma_land_scored.csv
                                   docs/bangkok_bma_land_map.png
data/gis/gh_bma_land.py         -> Grasshopper curves (shared local XY frame)
```

Run from the repo root. Kept as a **parallel layer** to the vacant-plots Tier 2
work, not folded into its `rank_score` (those five weights sum to 1.0 by design,
and "looks empty" is a different question from "the city owns it").

## 7. Widening beyond Tier 1: the priority subset (seed-driven fetch)

The first pass fetched parcels for only three districts (Bang Rak, Sathon, Khlong
Toei), because the district-scoped fetch is heavy — Bang Rak alone is ~13,700
parcels. But **the facility seeds were never district-limited**:
`fetch_bma_facilities.py` runs city-wide (`ox.features_from_place("Bangkok,
Thailand")` plus the full 437-school registry), so `bangkok_bma_facilities.geojson`
already holds **2,537 seeds across all 50 districts** (502 high / 190 medium /
1,845 low). The only thing missing elsewhere was parcel *geometry*.

`fetch_bma_parcels.py --around-facilities` fills exactly that gap. It does **not**
re-crawl whole districts — parcels carry no owner attribute, so extra parcels are
only grey context, never a new ownership answer. Instead it buffers each seed
(footprint +50 m, point +150 m), dissolves the buffers into a handful of disjoint
envelopes (so clustered inner-city facilities cost one fetch each), and pulls only
the parcels underneath, across a **UHI/transit priority subset** of districts:

```
priority = { UHI_Tier == "Severe" }  ∪  { Intercept_Score_Pct >= 30 }  ∪  { Bang Na }
         = 21 districts   (see data/gis/bangkok_parcels_seeded_manifest.csv)
```

The rule is a CLI knob (`--min-tier`, `--intercept-min`, `--extra-districts`), not
folklore; `bangkok_parcels_seeded_manifest.csv` records which districts were fetched
`full` vs `seeded`, why each qualified, and the parcel count. The three Tier 1
districts keep their **full** cadastral files (not re-seeded unless `--force`); the
other 18 are **seeded**. `build_bma_land_layer.py` globs all parcel files unchanged.

**Two caveats this introduces:**

1. **Mixed parcel density.** The three Tier 1 districts have the full cadastral
   fabric; the 18 new ones have parcels only around BMA facilities. This is
   sufficient for the ownership question (a facility can only claim parcels it sits
   on), but the context basemap in `build`'s render is sparser outside Tier 1.
2. **Verification burden scales with the net.** Including low-confidence seeds
   across 21 districts surfaces many more `low` candidates. `high` still means "no
   disqualifier found", not "title confirmed" (see §3) — every surviving site is
   audited individually. Run `build_bma_land_layer.py --min-confidence low
   --min-area 500` to see the wider set; sort on `ownership_confidence` and
   `land_owner_risk`.
