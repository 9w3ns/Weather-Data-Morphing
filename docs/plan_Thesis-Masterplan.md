# Thesis Master Plan — Evening Thermal Refuge for a Warming Bangkok

*This is the single overview document. It tells the whole story from start to
finish in plain language. Two companion docs hold the technical detail when you
need it:*
- *`SiteSelectionMatrixGemini.md` — how to choose the site (the "where").*
- *`plan_Site-specific-local-morphing.md` — how to build the site's weather file (the "how hot").*

---

## The one-paragraph version

Bangkok's heat is worst in the **evening** (roughly 18:00–21:00), exactly when
office workers head home to residences that have baked all day. This thesis
designs a **civic center that acts as an evening thermal refuge** — a cool,
comfortable "third place" to wait out the evening heat before going home. To
design it honestly for a hotter future, we (1) **choose a site** using real
heat + urban data, (2) **build a custom weather file** for that exact site that
reflects both global climate change (to ~2050) and that neighborhood's local
heat, and (3) **feed that weather file into the building design and energy
simulation** so the architecture is tuned to the real conditions it will face.

---

## The whole workflow at a glance

```
PHASE 0  Concept        →  Why an evening refuge, and who it serves        [DONE]
PHASE 1  Choose site    →  Rank districts on heat + vulnerability + access  [IN PROGRESS]
PHASE 2  Pick the plot  →  Zoom into the winning district, find the land    [NEXT]
PHASE 3  Build weather  →  Make the site-specific future EPW file           [PLANNED]
PHASE 4  Design         →  Form-find the building for comfort (UTCI)        [PLANNED]
PHASE 5  Prove it works →  Energy + comfort simulation, write it up         [PLANNED]
```

You are near the start of **Phase 1**. Everything below walks through each phase
in order.

---

## PHASE 0 — The concept  *(done)*

**Goal:** A defensible reason the building exists.

- **The problem:** Evening is Bangkok's peak heat-stress window. Homes radiate
  stored daytime heat back at their occupants right as outdoor heat peaks.
- **The idea:** A public, non-commercial, thermally-optimized civic space —
  essentially a cooler, kinder alternative to escaping into a shopping mall.
- **Who it serves:** Everyone shifts their day around heat as the climate warms,
  but the people who *most need* a public refuge are middle-to-lower-income
  residents in dense low-rise housing without good air-conditioning. So we treat
  vulnerability as a **priority**, not a fence — the refuge should be *most
  valuable* to them while still open and useful to all.
- **Evidence base:** Behavioral research shows heat pushes activity into the
  evening/night; Bangkok's malls already prove all-income "cooling refuge"
  behavior exists. (Full citations in `SiteSelectionMatrixGemini.md` §5.)

---

## PHASE 1 — Choose the site (district)  *(in progress)*

**Goal:** Pick the best district(s), using data instead of intuition.

**How:** A scoring system (weighted multi-criteria analysis) over Bangkok's 50
districts, in three passes. Full method in `SiteSelectionMatrixGemini.md`.

1. **Filter first (Tier 0):** keep only districts that sit at a *threshold*
   between workplaces and homes — so the refuge can intercept commuters. A
   purely residential or purely office district is dropped here.
2. **Score what's left (Tier 1)** on four things:
   - **Evening heat** (35%) — how bad the evening heat island is.
   - **Housing vulnerability** (30%) — dense low-rise housing (LCZ 3) that traps
     heat and lacks A/C. *This is a weight, not a filter — a less-vulnerable
     district loses points but isn't excluded.*
   - **Transit access** (25%) — nearby train/interchange stations.
   - **Population** (10%) — how many people it serves.
3. **Shortlist:** take the **top 3** districts into Phase 2.

**Design choice — pick a contrast pair:** also carry **one low-heat "control"
district** (e.g. a cooler outer district) through the later steps. Comparing the
two is what *proves* the local weather correction matters, rather than just
asserting it.

**What's done:**
- ✅ Heat, vulnerability, and population data ready (`data/gis/bangkok_uhi_data.csv`).
- ✅ Scoring logic designed; a provisional ranking already exists (top of the
  list so far: Bueng Kum, Chatuchak, Bang Sue — all dense low-rise, severe
  evening heat).
- ✅ Confirmed the "informal settlement" housing type (LCZ 7) simply isn't in the
  available maps, so we use dense low-rise (LCZ 3) as the vulnerability measure.

**What's left to do:**
- ⏳ **Gather transit data** — count train/interchange stations per district
  (from OpenStreetMap). This is the one missing ingredient before the ranking is
  final.
- ⏳ **Confirm the control district** for the contrast pair.
- ⏳ **Run the final ranking** and lock the top 3 + control.

---

## PHASE 2 — Pick the actual plot  *(next)*

**Goal:** Go from a district to a specific buildable piece of land.

Within each shortlisted district:
1. Draw a **500 m walking radius** around its major transit stations.
2. Overlay the city land-use map to find the exact line where commercial meets
   residential (the commuter-intercept threshold).
3. Use satellite/street imagery to spot a real, underused, buildable plot
   (e.g. a parking lot or low-density corner) in that zone.

**Output:** The final thesis site — one plot, with a name and coordinates.

---

## PHASE 3 — Build the site's weather file  *(planned)*

**Goal:** A custom future weather file (EPW) for that exact plot, so the design
responds to the real climate it will face — not a generic Bangkok average.

This happens in two layers on top of a standard Bangkok weather file:

- **Layer 1 — Future climate (already built).** The existing morphing engine
  (`morphing/epw_morphing_engine.py`) shifts the weather file to a future decade
  (e.g. 2050) using global climate-model data already in `data/deltas/`.
- **Layer 2 — Local neighborhood heat (to build).** Add the site's own measured
  evening heat-island bump on top, using the district's numbers from
  `bangkok_uhi_data.csv`. Full recipe (which hours, which seasons) is in
  `plan_Site-specific-local-morphing.md`.

**Optional cross-check (Track B):** independently re-create the local heat effect
with a physics tool (Dragonfly/Urban Weather Generator). If both methods agree,
that's a strong result for the thesis.

**Good news from recent research:** a 2026 Bangkok study confirms that a city's
*extra* heat over the countryside stays roughly stable over time even as overall
temperatures rise — which is exactly why this two-layer approach is sound.

**Output:** One weather file for the chosen site (and one for the control
district), ready for simulation.

---

## PHASE 4 — Design the building  *(planned)*

**Goal:** Shape the architecture for evening comfort.

Feed the site's weather file into the existing design toolchain
(Ladybug / Honeybee / Anemone form-finding, per `docs/development_plan.md`
Phase 4). Optimize the form for outdoor/semi-outdoor comfort (UTCI) across the
17:00–21:00 window, and design 3–4 hours of evening *program* (food, recreation,
social space) so people actually stay.

---

## PHASE 5 — Prove it works  *(planned)*

**Goal:** Show, with numbers, that the site-specific design matters.

1. Run a comparison energy + comfort simulation across three weather files:
   plain today's-Bangkok, future-Bangkok-only, and **future + this site's local
   heat**.
2. The difference is your headline result: how much the local correction (and
   careful site choice) changes predicted comfort and cooling load.
3. Write up method + limitations honestly (surface-vs-air heat data, typical-year
   assumptions, the dropped informal-settlement class — all already noted in the
   companion docs).

---

## Your immediate next actions (just these three)

1. **Get the transit station counts per district** (OpenStreetMap) — the last
   piece Phase 1 needs.
2. **Pick the control district** for the contrast pair.
3. Tell me when those are ready and I'll **build the scoring script** so the
   final district ranking pops out automatically.

Everything after that unlocks in order. You don't need to hold the whole thing
in your head — just do step 1.

---

## Where each detail lives

| If you need… | Look in |
|---|---|
| The full scoring method, weights, data sources | `SiteSelectionMatrixGemini.md` |
| The evidence base for the evening-refuge concept | `SiteSelectionMatrixGemini.md` §1 & §5 |
| Exactly how the local-heat weather layer is built | `plan_Site-specific-local-morphing.md` |
| The raw district heat/LCZ/population data | `data/gis/bangkok_uhi_data.csv` |
| Future-climate shift data (SSP scenarios) | `data/deltas/` |
