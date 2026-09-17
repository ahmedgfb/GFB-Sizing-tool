# GFB Pipe Sizer — Handoff

_Last updated: 2026-09-17 · covers the gas schematic, on top of `5b634b6`_

A tool to draw building-services riser schematics and calculate pipe sizes, built from the logic in
GFB's residential pipe-sizing spreadsheet. The schematic style is modelled on GFB's issued drawing
**XH_3003 COLD WATER SCHEMATICS** and has been reviewed against it by Ahmed.

**One file, no install.** `GFB_Schematic_Drawing_Tool.html` (~175 KB, 2,732 lines) is entirely
self-contained — no build step, no dependencies, no internet. Double-click it, or use the hosted
copy at **https://ahmedgfb.github.io/GFB-Sizing-tool/**.

> Editing it means editing one HTML file with an embedded `<style>` and one `<script>`. There is no
> bundler and no module system; keep it that way — being a single double-clickable file is the
> tool's defining property.

---

## Current status

| Area | State |
|---|---|
| Cold water flow + sizing | **Done**, cell-matched to the workbook |
| Hot water flow (Phase 1) | **Done** — own sheet, per-dwelling HW table, 1.2 m/s |
| Static pressure / PRV / pump duty | **Done** — mirrors FRONT PAGE `N21:N81`, `L15`/`M15`/`N15`/`J12` |
| Undo / redo | **Done** — Ctrl+Z / Ctrl+Y, 60 steps |
| Print to PDF | **Done** — A3 landscape, one page, auto-named |
| Riser connection picker + HWUs | **Done** |
| Gas schematic + sizing | **Done** — own sheet, AS 5601-2022 tables, cell-matched to `GAS CALCS` |
| Hot water **return** (recirc) | Not started — next up |

---

## Using the tool

### Job setup (opens first)

Job name/number, basements, levels above ground (insert mezzanines with **＋** on a level row;
rename/remove any level), material + max velocity, mains-supply pressure inputs, and the riser list
(name, from → to level, dwellings per level). **Start drawing** builds a schematic with floor datum
lines, risers placed, and the mains already chained source → riser → riser in the ceiling.

**▤ Job setup** starts a new job. It warns first, and since it is now undoable, Ctrl+Z gets your
drawing back if you clear it by mistake.

### Commands

| Key | Command |
|---|---|
| `L` | **Draw pipe** — click a start (source, riser at *any* level, tee, HWU, or an existing pipe to T off), click orthogonal waypoints, click the end. `Enter`/double-click ends open. |
| `F` | **Fillet (radius 0)** — click two runs anywhere along them; the clicked sides trim/extend to a square corner and merge into one pipe. |
| `Ctrl+Z` | **Undo** (works even while a panel field has focus). |
| `Ctrl+Y` / `Ctrl+Shift+Z` | **Redo**. |
| `Esc` | Cancel draft / connect pick / back to Select. |
| `Del` | Delete selection. |
| `Z` / ⛶ Fit | Zoom extents. |
| Wheel / middle- or right-drag | Zoom at cursor / pan. |

### Connecting a riser anywhere on a run

Two ways, both built on the same one-shot **connect mode**:

- **New riser** → the dialog's **Connect** dropdown defaults to *"Pick a point on the run…"*. After
  **Add riser →**, hover snaps an orange marker to the nearest pipe with a dashed preview; click to
  tee off there. The riser **lands at the point you clicked** (nudged clear if it would collide with
  an existing riser within 120 px). `Esc` leaves the riser unconnected.
- **Existing riser** → **⇢ Reconnect feed** on the riser panel. Same picker; it removes the current
  feed pipe first, so you never end up double-fed. Use this to repair risers wired to the wrong
  place. **Feed at level** beside it moves the feed up/down the same riser without redrawing.

When the riser lands directly *on* the run, the two halves attach straight to it and **no tee is
created** — a tee there would need a zero-length feed pipe, which sizes as unconnected and draws as
a stray dot. Off the run, a tee is inserted and a main runs across in the ceiling.

`autoConnectRiser` (the *Nearest riser (automatic)* option) prefers a **riser or plant** and falls
back to the mains source only when neither exists — i.e. only for the genuinely first riser, where
the underground entry is the correct convention.

### Risers

- Click to edit: name, **Starts at** level, material/velocity overrides, **meter branch side**,
  **Individual HWUs** toggle, per-riser pressure R.L. overrides, and dwellings/LU per level.
- **Connections attach at any building level.** The riser extends itself with pass-through segments
  to reach one; the attach point sits 14 px above the meter branch where that level has meters.
- Meter branches render per the issued drawings: branch at the top of the level with its own Ø
  callout, meters hanging down, "N x CW METERS". Banks over 6 draw as a **two-row cluster** (max 20
  glyphs).
- **📌 Pin** on a pipe's *Attached at level* keeps that level when the riser's "Starts at" changes.

### Hot water units (cold sheet)

Two forms, both **symbol only — they add no cold-water demand and change no pipe size**:

- **⬓ HWU** — a central plant box: configuration (Gas/Elec × Central/Individual), unit name, model
  line, gas load MJ/hr, and an editable note defaulting to `REFER TO HOT WATER SCHEMATICS`. Draw the
  cold feed into it; the run is labelled **TO &lt;unit&gt;**.
- **Individual HWUs** — a riser tick-box. Puts an HWU glyph on every served level's meter branch and
  makes the label read `4 x CW METERS + 4 x HWU`.

> An HWU feed carries no flow. A zero-flow pipe would normally render grey with a `—` callout — the
> "no path from source" error style — so `sizePipes()` explicitly marks HWU feeds
> **connected-but-unsized** (`res[id].annot = <unit name>`). Keep that flag if you touch the sizing
> loop, or connecting an HWU will look like a broken network.

### Reading the drawing

- Ø callouts on riser segments, branches and mains; mains also show flow (L/s) and velocity (m/s).
  Blue = OK, **red = over the velocity limit**, grey `—` = **not sized**.
- Grey means not on a path from the source: look for a **red open circle** (unattached end) or a
  loop (ring mains are not supported; one pipe in any loop stays unsized).
- A ▶ arrow marks where the network feeds each riser. Below the ground line renders as earth; the
  mains supply sits underground.
- Clicking a pipe shows flow/size/velocity plus **size options** — one size down, recommended, one
  size up, each with its velocity.

### The gas sheet (Gas)

A third sheet beside Cold and Hot, drawn in ochre. Switching to it with the gas sheet empty
builds it from the cold-water risers — a **⛁ GAS SUPPLY** entry at ground plus one gas riser per
cold riser, **bottom-fed** (gas comes up from the meter assembly, unlike hot water coming down
from a roof plant). **⛁ Gas setup** rebuilds it later.

Everything else is the same tool: `L` to draw, the connect picker, meter branches, the level
editor. What changes is the arithmetic.

- The per-level table is **Dwellings + Plant MJ/hr** instead of Dwellings + LU.
- Callouts read `Ø50` over `544 MJ/hr`. There is **no velocity** — the table's pressure-drop band
  already fixes it.
- A **▧ Gas Plant** box can be placed on the sheet; it prints its own MJ/hr load.
- Meter branches read `4 x GAS METERS`, with the same two-row cluster over 6.
- The ◱ Pressure overlay is hidden: that engine is water static head.

The sheet-wide inputs sit in the toolbar (the workbook's FRONT PAGE gas block): **Table**,
**Index length**, **MJ/hr each**, and a **⚖ Diversity** toggle. Index length is a dropdown of the
36 lengths the tables are tabulated at, because the workbook's `MATCH(...,0)` is an exact match
and anything else sizes as `-`. Each riser can override any of them — blank means inherit, shown
greyed, the same contract as material / velocity / the R.L. fields.

### Demand per dwelling is per riser, and mains blend correctly

A building rarely runs one appliance load throughout, so **Demand / dwelling (MJ/hr)** on the riser
panel overrides the sheet for that riser alone. The riser readout says which is in force —
`40 MJ/hr (sheet)` or `60 MJ/hr (this riser)`.

The important part is what happens **upstream**. A gas load is carried as
`{dwellings, demand, plantLoad}`, where `demand` is already multiplied by *each riser's own rate*
at that riser. So a main serving a 24-dwelling riser at 40 and an 18-dwelling riser at 60 carries
`24×40 + 18×60 = 2040` MJ/hr undiversified, and the diversity factor is still picked from the
combined head count of 42 — 514 MJ/hr, not the 423 a single sheet-wide 40 would give. `dwellings`
exists only to choose the diversity factor; never multiply it by a rate upstream of a riser.

Loads also carry a `mixed` flag, set when two sub-loads with different rates are added. It affects
nothing in the sizing — it is only so the pipe panel can say **blended** rather than quote a rate
no riser actually uses. When every riser is on one rate, all of this reduces exactly to the
workbook's `MAIN PIPE` sheet, which is what `tests/suite_perriser.js` asserts.

> Rate is per riser, matching the workbook (its column D is a single `$D$4` per riser block). It is
> **not** per level — a commercial ground floor at a different rate would need a new field.

### Plant on the gas sheet

The same **▧ Plant** box appears on the hot-water and gas sheets, and it means opposite things on
each — so the sizing engine treats it differently:

| | Hot water | Gas |
|---|---|---|
| Role | a **source** — the hot-water network starts here | a **load** — it burns gas |
| In `sizePipes` | included in `sources`, feeds the BFS | excluded; contributes `plantLoad` instead |
| Drawn | two-line box | three-line box, the third being its MJ/hr |

Getting that backwards is the thing to watch: if a plant were left in `sources` on the gas sheet,
every run beyond it would size off a supply that does not exist.

Draw the gas main (`L`) into the plant and every run upstream picks up its MJ/hr. The load is
added **after** diversity — plant is a firm demand and the dwelling curve must never discount it.

**The gas copy appears by itself.** Set a hot-water plant's configuration to **Gas · Central** or
**Gas · Individual** and it shows up on the gas sheet immediately, at the *same coordinates* — the
two schematics share their geometry, so the plant reads as one object in one place in the building.
No rebuild, and it does not wait for a load to be typed.

`syncGasPlants()` maintains it. The copy carries `linkedTo` (the hot-water node's id) and:

- **Name, configuration and load are shared both ways.** Editing them on either sheet writes to the
  hot-water node and syncs back, so the gas load can be typed where you are actually sizing gas.
  Editing the copy directly would just be reverted on the next sync, which reads as a field
  refusing to take a value.
- **Position follows** the hot-water plant — until the copy is dragged on the gas sheet, after
  which it is yours and the mirror stops moving it (tracked by `syncedX`/`syncedY`).
- **Switching to Electric, or deleting the plant, removes the copy** — but only while nothing is
  drawn to it. If there is pipework attached it stays put (unlinked, and flagged as electric in its
  panel); silently deleting someone's drawn runs is worse than a box that explains itself.
- The copy arrives **unconnected**: it sits where the plant sits and the gas run into it is yours
  to draw, since any route the tool guessed would usually be wrong.

**`render()` guarantees it.** The mirror is part of the document, so rather than relying on every
edit path remembering to sync, `render()` calls `syncGasPlants()` whenever the gas sheet is shown.
It is also called from the plant panel's handlers, the end of a plant drag, entry to the gas sheet
and `loadState` (so older files gain the copy), but none of those are load-bearing any more.

The one thing that must stay true: `syncGasPlants()` returns immediately while `restoring`, so the
render inside `restoreDoc` cannot resurrect a node undo has just removed. Do not remove that guard.

Clicking the sheet tab you are already on now re-renders instead of doing nothing — `switchService`
ignores a switch to the current sheet, which left the obvious "this looks stale, let me click the
tab" gesture with no effect.

There are two ways to put plant load on the sheet, and both are legitimate: this plant box, or the
**Plant MJ/hr** column on a riser's level table for something that hangs off that level. They add
up the same way.

> **Diversity is applied once, to the cumulative dwelling count, and diversified loads are never
> added.** The curve is steeply non-linear (1 dwelling → 1.00, 67 → 0.203, 80+ → 0.195), so
> summing two risers' diversified demands the way the cold-water mains accumulate would undersize
> every shared main. `sizePipes()` carries `{dwellings, plantLoad}` up the tree and diversifies at
> each pipe; `riserInfo[].exports` holds the same pair rather than a flow. Keep that shape if you
> touch the gas path — `tests/suite_gas.js` guards it.

Plant loads (MJ/hr on a level) are added **after** diversity, undiversified.

### Pressure, PRVs and pump duty (◱ Pressure)

Mirrors the workbook's FRONT PAGE. Enter the seven R.L. / pressure values on the **mains supply**
(source panel) and every riser inherits them; **blank = inherit, typed = override**, same pattern as
material/velocity. Inherited values show greyed as placeholders.

- Static profile per level: `P[i] = minPressure + 10 × floorToFloor × (topServed − i)`.
- A level over **500 kPa** (`maxStatic`) flags a **PRV**, set to 500 kPa, with a limit line on the
  riser and a count of affected dwellings.
- Pump duty (`L15`/`M15`/`N15`) and max pressure in pipe (`J12`) appear on the riser panel.
- Constants live in `PRESSURE_DEFAULTS`. `mirrorSheetWarningBug: false` is deliberate — the
  workbook's A6 warning subtracts `(RL pump − RL main)` as metres from a kPa quantity with no ×10;
  set it `true` to reproduce the sheet exactly.

### Print to PDF (⎙ PDF)

Opens the browser print dialog with the filename pre-filled as **`25642 Cold Water Schematic`**
(job number + sheet; falls back to job name, then bare sheet name). Choose *Save as PDF*. A3
landscape, one page, whole drawing, with a title block bottom-right (Goldfish & Bay, job, job no.,
sheet, date, blank Drawn/Checked rules). Your on-screen zoom is restored afterwards.

The filename is a **suggestion**, not a forced save — Chrome/Edge take it from `document.title`.
Forcing a silent download would need an inlined PDF library (~350 KB) whose SVG converter has known
gaps around `<pattern>` fills and `paint-order` halos, so the PDF could silently differ from screen.
Printing the live SVG is exact, vector, and dependency-free.

### Undo / redo

Full-state snapshots (`state` is plain data; `render()` + `renderPanel()` rebuild everything from
it). 60 steps, in memory only — not saved to the job file. Typing in one field coalesces into a
single step (700 ms window). Undo **never moves the camera** and never flips the ◱ Pressure toggle,
but it *does* follow the sheet the edit happened on.

Covers everything, including Load, Start drawing and HW setup.

### Save / Load

**Save** downloads `<jobno>.json` — **format v6**:
`{version, building, settings, activeService, services, nextId}`. `services.cw` / `services.hw` /
`services.gas` each hold their own `network` (material, maxVelocity, supply R.L.s — plus
`network.gas` for the gas sheet's table/index length/MJ per dwelling/diversity/tolerance),
`nodes`, `pipes`. v1–v5 files migrate automatically on load: a v5 file gains an empty gas sheet
with the workbook defaults, and every riser level gains `mj: 0`.

---

## Sizing method (mirrors the spreadsheet's Cold Water logic)

- **Dwelling demand:** `Q = 0.03N + 0.4554·√N` (L/s), N = cumulative dwellings served.
- **Loading units:** converted via the PSFR curve extracted from the workbook.
- **Hot water demand:** the workbook's per-dwelling table (`HOT WATER DATA`, 1→0.40 … 100→7.50 L/s,
  then the CW dwelling curve beyond 100) — **no loading-unit term** — at 1.2 m/s.
- **Pipe selection:** smallest standard pipe (Copper Type B or Stainless Steel) whose capacity at the
  max velocity meets the flow — the spreadsheet's exact-or-next-larger `XLOOKUP` behaviour.
  `capacity = π(ID/2000)² × vmax × 1000`.
- **Mains accumulation:** BFS from the source; each main carries everything downstream (per-riser
  diversified flows add arithmetically — **water only**, see the gas method below).
- **Riser segments size away from the feed point** (bottom-, top- or mid-fed) and include flow
  exported at a level to feed other risers. Demand below a riser's start level is excluded.
- Reference data (PSFR curve, pipe ID/DN tables) was **extracted from the workbook, not retyped**.

## Gas sizing method (mirrors the workbook's GAS CALCS sheet)

Per level, working **down** from the top of the riser — the workbook's columns C..H:

| | Formula |
|---|---|
| Cumulative dwellings `C` | `SUM(I_row : I_last)` — this level and everything above |
| Undiversified demand `E` | `C × demand per dwelling` (FRONT PAGE `D14`, default 40 MJ/hr) |
| Diversity `F` | `VLOOKUP(C, 'GAS DATA'!F9:G88, 2, TRUE)`, or `1` with diversity off |
| Adjusted demand `G` | `C = 0 ? Σplant : F × E + Σ(plant load at this level and above)` |
| Pipe size `H` | smallest DN whose table capacity ≥ `G × tolerance` |

- **Tolerance** is FRONT PAGE `B15` as a percent; **blank means ×1.1**.
- **Capacity** is `INDEX(table_row, MATCH(index length, header, 0))` — exact match on the index
  length, so only the 36 tabulated lengths (2, 4 … 320 m) are valid.
- Four AS 5601-2022 tables are embedded: **F.12** / **F.13** (copper, 0.75 / 1.5 kPa drop) and
  **F.24** / **F.25** (steel), all extracted from the workbook's hidden `GAS DATA` sheet.
- DN15 is included. GFB's standalone `GFB_Gas Pipe Sizing - V5` template skips it (its selector
  jumps 10 → 20); the master's `GAS CALCS` does not, and the master is what we mirror.

---

## Validated vs not

**Cell-matched to the workbook.** `verify_against_workbook.py` re-checks it on demand — stdlib only
(no openpyxl; it reads the `.xlsx` as a zip via `zipfile` + `ElementTree`):

```
py verify_against_workbook.py     # 17 checks, exit 0 = pass
```

It covers the PSFR curve, both ID/DN tables, capacity bands, the demand formulas, a
**45,000-point selection sweep** (0.001–45 L/s × 4 material/velocity combinations), and — new with
gas — all four AS 5601 capacity grids (1,800 cells), the 80-row diversity curve, a monotonicity
guard, a 4,782-lookup gas selection sweep, and **all 61 rows of `GAS CALCS` columns G and H**
reproduced from the sheet's own inputs. It carries `MIRRORED_JS` fingerprints of `areaM2` /
`maxFlowForVel` / `selectPipe` / `gasDiversity` / `gasCapacity` / `selectGasPipe` / `gasAdjusted` /
`gasTolerance`, so the Python mirror cannot silently drift from the JavaScript.

> **Sheets and table blocks are located by name and by their own headers, never by position.**
> They used to be hardcoded as `sheetN.xml` and `row 5 + i`. The master has since gained an
> `RCW CALCS` sheet, which shifted every file index from 4 up and had the script silently reading
> `GAS DATA` as `COLD WATER DATA` — it was checking the wrong cells and had stopped meaning
> anything. Don't reintroduce positional lookups.

Three **intentional deviations** are printed as notes, not failures:

1. The workbook raises the HW limit to 2.0 m/s for stainless; the tool keeps 1.2 m/s for both
   materials (per-material auto-default not wired — use the manual override).
2. Stainless callouts show the raw stainless size, not the workbook's DN column mapping.
3. Gas table F.12, DN65 at an index length of 4 m, reads **137776 MJ/h** — impossible (12× its
   neighbours, and above DN80 at the same length). It is in *every* copy checked: the master, all
   six Ellen Street `V5` sheets and the Resizing copy, so it is a defect in GFB's template, not a
   corrupted file. The tool carries that one cell as `null`, so a lookup landing on it reports
   "not tabulated" rather than a wrong size. Only a 4 m index length is affected. **Worth fixing in
   the template from the printed standard.**

⚠️ **Workbook provenance.** The master used for verification is
`XXXXX_GFB_Pipe Sizing Sheet.xlsx`. A second copy, `GFB_Pipe_Sizing_AllSheetsVisible.xlsx`, was
found to be **corrupted** — its RISER 1 copper column oversizes across 0.568–1.686 L/s. Do not
verify against that file.

### ⚠️ Open: the cold-water table no longer matches the master

Four checks currently **FAIL**, and they are not gas. The master's `COLD WATER DATA` pipe selector
now lists **9** sizes starting at DN20 copper / DN22 stainless — the **DN15 row has been deleted**.
`HOT WATER DATA` still has all 10 and still matches. The tool's `PIPE_TABLES` (shared by both water
sheets) still includes DN15, so for any cold-water run small enough to reach it the tool says DN15
where the current workbook says DN20/DN22.

This predates the gas work and was hidden by the positional-lookup bug above. It has been left
**unfixed on purpose**: dropping DN15 would change cold-water sizes on issued drawings, and whether
GFB intends DN15 to be unavailable for cold water is an engineering decision, not a code one.
Decide it, then either drop DN15 from the cold-water table or add it to the notes as a deliberate
deviation.

**Not cell-matched — engineering judgement, spot-check before relying on:**

- **Feed-point-aware riser segments and riser-to-riser export flows** — sound, but the workbook only
  sizes bottom-fed risers, so there is nothing to compare against.
- **PRV detection and the PRV set pressure** — our extension; the workbook has no PRV column.
- **Headloss (kPa/100 m)** — not implemented in this tool.
- **Mid-riser booster pumps** — only the common case (pump flow vs dwelling demand at a level).
- **Gas mains serving more than one riser** — the arithmetic is the `MAIN PIPE` sheet's (one
  diversity factor on the total dwelling count) and is tested, but GFB runs one workbook per riser,
  so a multi-riser gas main has no single sheet to compare against.
- **Gas mains blending different demand/dwelling rates** — `Σ(dwellings × that riser's rate)` with
  diversity from the combined head count. It reduces to the workbook whenever one rate is in play,
  but the workbook cannot express more than one, so the mixed case is our generalisation. Spot-check
  the first job that uses it.
- **Gas index length** — the tool asks for it; it does not compute it from the drawing. The number
  is still the designer's, exactly as in the workbook.

---

## How to test a change

**There is now a test folder, and it is committed.**

```
py tests/run_all.py                # 192 assertions + the water regression diff
py verify_against_workbook.py      # the reference data, against the workbook
```

A Python driver injects a suite as an extra `<script>` into the **real** HTML file, loads it
headless with `--headless=old --dump-dom --virtual-time-budget=30000`, and reads assertions back
out of a `<pre id="results">`. See `tests/README.md`. Three things matter:

- Use `--headless=old`, **not** `--headless=new` — the new mode produces no output with `--dump-dom`.
- From PowerShell, `& $browser` drops stdout; use `System.Diagnostics.ProcessStartInfo` with
  `RedirectStandardOutput`, or run the driver from Python/Bash.
- **Edge may emit nothing at all.** Edge 153 on this machine returned empty stdout for every
  command, `--version` included, so the runner now prefers **Chrome**. `GFB_TEST_BROWSER` overrides.
- Decode stdout as UTF-8 — the DOM is full of `Ø` and `·`.

`tests/suite_water_regression.js` is the safety net for changes that are only meant to touch one
sheet: `run_all.py` runs it against `git show HEAD:` and the working copy and requires the two to be
identical. The gas work passed it across 167 lines of sizes, pressure profile and SVG text.

Anything asserting on **undo** must use `defer()` — `pushUndo` commits its snapshot on a
`setTimeout(...,0)`, so a synchronous check reads stale state and looks like a tool bug.

For PDF output, `--print-to-pdf` exercises the real print stylesheet, so page count and page size can
be asserted rather than assumed (parse `/Type /Page` and `/MediaBox` out of the PDF bytes). The gas
sheet was confirmed at one page, 1191 × 842 pt = A3 landscape.

**Verify numerically, not visually.** Three real bugs in this codebase looked fine in a screenshot:
overlapping HW mains carrying conflicting Ø callouts, a connect-mode feed pipe that collapsed to a
single point, and — in the gas work — the standing temptation to add two risers' diversified loads,
which draws perfectly and undersizes the main.

> The five earlier suites (undo 98, connect 60, hwu 41, regress 37, hit-probe 8) were written in a
> scratchpad at `5b634b6` and lost. They are **not** in `tests/` — only the gas, UI and water
> regression suites are. Re-creating the undo and connect suites is the remaining housekeeping job.

---

## Known limitations

- One feed per riser is assumed; extra feeds are treated as exports, and a second feed into an
  already-reached riser becomes a non-tree edge that renders grey.
- Ring mains / loops are not sized — one pipe in any loop stays unsized.
- Changing the building level list after drawing keeps attachments but does not re-space existing
  pipe waypoints.
- **A feed landing below a riser's start level** draws meter banks on the levels in between, but
  those contribute **zero flow** to `riserSegments` — and `selectPipe(0, …)` returns the *smallest*
  DN rather than nothing, so the leg silently shows `Ø15 @ 0.00 L/s`. Worth fixing now that the
  connect picker puts feeds at sane levels.
- R.L. fields lose keyboard focus after each character: `bindRlFields` calls `renderPanel()` on every
  keystroke and `renderPanel` does `body.innerHTML=''`. The per-level dwellings/LU inputs deliberately
  avoid this (they skip `renderPanel`), and **the gas override fields now do too** — `bindGasFields`
  re-renders the drawing plus the `#gasout` readout and the level badges, never the whole panel.
  The R.L. fields are the last ones left with the defect; the fix is the same shape.
- **Gas:** one index length per sheet (overridable per riser), entered rather than measured — the
  tables are only tabulated at 36 lengths, so it is a dropdown. A run whose real effective length
  differs materially from the sheet's index length is not separately accounted for, exactly as in
  the workbook.
- **Gas:** the diversity curve stops at 80 dwellings and the workbook's `VLOOKUP(...,TRUE)` holds
  the last factor (0.195) beyond it. A 300-dwelling main therefore uses 0.195, which is what the
  `MAIN PIPE` sheet does too — but it is a flat extrapolation, not tabulated data.
- The wide (140 px) riser hit-pad is suppressed outside Select mode so it stops covering the mains.
  In Select mode it is retained, but a geometric contest still hands the click to a pipe when the
  pipe is genuinely nearer.

---

## Open items / next steps

1. **Decide the cold-water DN15 question.** Four workbook checks fail on it — see *Validated vs
   not*. It changes cold-water sizes, so it needs an engineering decision before a code change.
2. **Hot water return (recirculation).** Start simplified (recirc as a fraction of flow, or a
   velocity-based minimum ~0.9 m/s, drawn as a parallel Ø HWR line), then upgrade to the workbook's
   heat-loss method (`HWR CALCS` / `HOT WATER RETURN DATA`: insulation, water/ambient temps) plus
   circulating-pump head.
3. **Fix the below-start feed case** (zero-flow legs showing Ø15).
4. **Re-create the undo and connect suites** in `tests/` — the gas, UI and water suites are
   committed, those two are still missing.
5. **Tell whoever maintains the gas template** about F.12 DN65 @ 4 m (see the notes).
6. **Surface headloss** once validated.
7. Per-material HW velocity default (stainless 2.0 m/s) instead of a manual override.
8. Gas extras deferred from this pass: LPG, non-dwelling appliance loading, a meter/regulator
   schedule, and computing the index length from the drawing rather than asking for it.
9. Optional: PFE table + CSV export, and a PRV schedule — both deferred from the pressure work.

---

## Change log

- **2026-09-17 — Gas schematic.** Third sheet, sized from AS 5601-2022 tables F.12/F.13/F.24/F.25
  with the workbook's diversity curve; mirrors `GAS CALCS` for all 61 published rows and the
  `MAIN PIPE` sheet. Save format v6. Committed a `tests/` folder (109 assertions + a water
  regression diff) and extended `verify_against_workbook.py` with five gas checks. Demand per
  dwelling is per riser, and mains serving risers at different rates blend them correctly. A
  gas-fired HW plant appears on the gas sheet automatically, in the same position, where it is a
  load rather than a source. Fixed that
  script's sheet and row lookups, which had been silently reading the wrong cells since the master
  gained an `RCW CALCS` sheet. Cold and hot water provably unchanged.
- **2026-08-19 — HWU on the cold sheet** (`5b634b6`). Central `hwu` terminal node (config, model,
  gas load, note) plus per-riser individual HWUs on meter branches. Symbol only; feeds flagged
  connected-but-unsized so they don't read as errors. Cold-water sizes provably unchanged.
- **2026-08-19 — Riser connection picker** (`89bced6`). Connect mode with hover preview; riser lands
  at the clicked point; ⇢ Reconnect feed for existing risers. Fixed three click-blockers (callouts
  stealing clicks, 140 px riser pads covering mains, hit width shrinking with zoom) and stopped
  `autoConnectRiser` dragging mains underground.
- **2026-08-19 — Undo / redo** (`5609673`). Snapshot-based, 60 steps, coalesced typing. Also fixed
  Ctrl+Z being bound to `fitView()`.
- **2026-08-19 — Print to PDF** (`9d61ed8`). A3 landscape, title block, auto-named from the job.
- **2026-08 — Pressure / PRV / pump duty** (`6a68209`, `2b0b3b4`, `926a050`, `2e87f03`), plus
  supply-level R.L. inheritance and readability fixes.
- **2026-07-31 — GitHub Pages** (`fc76f94`) and the workbook verification script (`c388d1f`).
- **2026-07-24 — Hot water flow (Phase 1).** Per-service state, Cold/Hot toggle, roof HW Plant,
  ♨ HW setup.

---

## Files in this folder

| File | What it is |
|---|---|
| `GFB_Schematic_Drawing_Tool.html` | **The tool.** Everything is in here. Double-click to open. |
| `verify_against_workbook.py` | Re-checks the sizing tables (water **and** gas) against the master workbook. `py verify_against_workbook.py`, exit 0 = pass. |
| `tests/` | The browser suites and their runner. `py tests/run_all.py`. See `tests/README.md`. |
| `index.html` | GitHub Pages entry point; redirects to the tool so it keeps its descriptive filename. |
| `.nojekyll` | Stops Pages running Jekyll over the repo. |
| `GFB_Pipe_Sizer_HANDOFF.md` | This document. |

**Referenced but not stored here** (keep them to hand — the verification script needs the workbook):

| File | Where |
|---|---|
| `XXXXX_GFB_Pipe Sizing Sheet.xlsx` | The master workbook. Was in `~/Downloads`. Verified against. |
| `GFB_Pipe_Sizing_AllSheetsVisible.xlsx` | Second copy — **corrupted**, see above. Do not verify against. |
| `XH_3003_COLD WATER SCHEMATICS-Model.pdf` | The issued drawing used as the visual reference. |
| `GFB_Gas Pipe Sizing - V5 - *.xlsx` | GFB's standalone per-riser gas sheets (Ellen Street `22058`, `C-GAS`). Same method as the master's `GAS CALCS`; useful as worked examples. Note its selector skips DN15 and it carries a second bad F.12 cell (DN125 @ 100 m = 1523) that the master does not. |
| `gfb_pipe_sizer.zip` | Older Python/Streamlit reference engine. Superseded by the HTML tool. |
