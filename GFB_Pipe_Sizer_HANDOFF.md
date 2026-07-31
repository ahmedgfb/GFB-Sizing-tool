# GFB Pipe Sizer — Handoff Summary

_Last updated: 2026-07-20_

A tool to draw building-services riser schematics and calculate cold-water pipe sizes, built from the logic in GFB's residential pipe-sizing spreadsheet (`GFB_Pipe_Sizing_AllSheetsVisible.xlsx`). The schematic style is modelled on GFB's issued drawing **XH_3003 COLD WATER SCHEMATICS** and has been reviewed against it by Ahmed.

## Current status

**Cold water + hot-water _flow_ (Phase 1). Two deliverables:**

1. **`GFB_Schematic_Drawing_Tool.html`** — the main tool. Self-contained; double-click to open in any browser. No install, no internet, nothing to configure. This is the one to actually use.
2. **`gfb_pipe_sizer.zip`** — Python/Streamlit version of the same core calculations, kept as the validated reference. Its `tests/` are where the sizing is checked against the workbook. Superseded for day-to-day use; its UI does **not** have the drawing features below.

## Using the drawing tool

### Job setup page (opens first)
Enter job name/number, basements, levels above ground (insert mezzanines with the **＋** button on a level row; rename/remove any level), material + max velocity, and the riser list (name, from → to level, dwellings per level). **Start drawing** opens a pre-populated schematic: floor datum lines, risers placed and already connected to the mains supply. **▤ Job setup** in the toolbar starts a new job (it warns before clearing — Save first).

**Interconnecting mains run in the ceiling.** The mains enters each riser at its start level, and riser-to-riser runs cross **straight through the ceiling of that level** — tight under the slab above and clear of the meter branches (the attach point is already offset above a branch where the level has meters). Any feed point can be moved afterwards via a pipe's **Attached at level** + 📌 pin.

### Commands (AutoCAD-style)
| Key | Command |
|---|---|
| `L` | **Draw pipe** — click a start (source, riser at *any* level, tee, or an existing pipe to T off), click orthogonal waypoints, click the end. `Enter`/double-click ends open; clicking mid-pipe auto-inserts a tee. |
| `F` | **Fillet (radius 0)** — click two runs anywhere along them; the clicked sides trim/extend to a square corner and merge into one pipe. Works on attached and crossing runs. |
| `Esc` | Cancel draft / back to Select. |
| `Del` | Delete selection. |
| `Z` / ⛶ Fit | Zoom extents. |
| Mouse wheel | Zoom at cursor. |
| Middle- or right-drag | Pan (the browser context menu is suppressed on the canvas). |

### Risers
- Click a riser to edit: name, **Starts at** level (changeable anytime — base-feed pipes follow the base unless 📌 pinned, see below), material/velocity overrides, **meter branch side** (left default, flip right), and dwellings/LU per level. The top of the riser follows the highest level with demand.
- **Connections attach at any building level.** The riser extends itself with pass-through segments to reach a connection; the attach point sits slightly above the meter branch when that level has meters.
- Meter branches render per the issued drawings: branch at the top of the level with its own Ø callout, meters hanging down, "N x CW METERS" label. Banks over 6 meters draw as a **two-row cluster** (meters stacked in pairs per column, up to 20 glyphs).
- **Pinning a feed:** select a pipe attached to a riser — the panel shows each riser end's **Attached at level** (editable) with a **📌 Pin** checkbox. A pinned attachment keeps its level when the riser's "Starts at" changes (e.g. keep the feed below the riser start; the riser passes through to reach it).

### Reading the drawing
- Ø callouts (Ø25, Ø40 …) on riser segments, branches and mains; mains also show flow (L/s) and velocity (m/s). Blue = OK, **red = over the velocity limit**, grey "—" = **not sized**.
- A grey pipe means it is not on a path from the source: look for a **red open circle** (an unattached end — delete and redraw with `L`) or a loop (ring mains are not supported; one pipe in any loop stays unsized).
- A ▶ arrow marks where the network feeds each riser. Below the ground line is rendered as earth (soil hatch); the mains supply sits underground.
- Clicking a pipe shows its flow/size/velocity plus **size options**: the recommended size with one size down and one size up, each with its velocity at the pipe's flow (over-limit options flag red).

### Hot water (Phase 1 — flow only)
A **`Cold` / `Hot` sheet toggle** (top-left) switches between two independent schematics that share the building levels; each sheet keeps its own nodes, pipes, material and velocity.
- The hot-water feed is a roof **HW Plant** (▧ HW Plant; Elec/Gas × Central/Individual, plus a gas-load MJ/hr field stored for the future gas schematic). Draw the flow main from the plant down into each riser's **top** level so segments size downward from the roof.
- **♨ HW setup** builds the hot-water sheet from the cold-water risers automatically: a roof plant + mirrored HW risers, each connected at its top level (also runs once when you first switch to an empty Hot sheet).
- **HW demand** uses the workbook's per-dwelling table (`HOT WATER DATA`: 1→0.40 … 100→7.50 L/s, then the cold-water dwelling curve beyond 100) — **no loading-unit term** — at a **1.2 m/s** default limit, same copper/stainless pipe tables as cold water. Branches and callouts read `HW`.
- The feed point stays user-editable (attach level + 📌 pin), so bottom- or mid-fed hot-water mains still work.

### Save / Load
**Save** downloads `<jobno>.json` (format v4: shared building levels + **both** `services` (`cw`, `hw`), each with its own network / nodes / pipes, plus the active sheet). **Load** reopens it; older single-sheet v1/v2/v3 `*_cw.json` files migrate automatically into the cold-water sheet with an empty hot-water sheet.

## Sizing method (mirrors the spreadsheet's Cold Water logic)

- **Dwelling demand:** `Q = 0.03N + 0.4554·√N` (L/s), N = cumulative dwellings served.
- **Loading units:** converted to flow via the PSFR curve extracted from the workbook.
- **Pipe selection:** smallest standard pipe (Copper Type B or Stainless Steel) whose capacity at the max velocity (default 2.5 m/s) meets the flow — same exact-or-next-larger behaviour as the spreadsheet's XLOOKUP.
- **Mains accumulation:** BFS from the source; each main carries the demand of everything downstream (per-riser diversified flows add arithmetically).
- **Riser segments size away from the feed point** (bottom-, top- or mid-fed), and include flow exported at a level to feed other risers downstream. Demand below a riser's start level is excluded; pass-through segments still carry exports.
- **Meter branches** are sized from their level's own demand.
- Reference data (PSFR curve, pipe ID/DN tables) was extracted from the workbook, not retyped.

## Validated vs. not

**Validated against the workbook** (dwelling curve, PSFR curve, capacity bands, pipe selection): the JavaScript engine reproduces the spreadsheet's figures exactly; the same checks live in the zip's `tests/test_cold_water.py` and `tests/test_network.py`.

**Not cell-matched — engineering-judgement extensions, spot-check before relying on:**
- **Feed-point-aware riser segments and riser-to-riser export flows** — the accumulation logic is sound but has no spreadsheet counterpart to check against (the workbook only sizes bottom-fed risers).
- **Headloss (kPa/100m):** in the Python engine (Darcy-Weisbach/Colebrook-White) but not cell-matched and not surfaced in the drawing tool.
- **Mid-riser booster pumps:** only the common case (pump flow vs dwelling demand at a level) is handled.

**Known limitations:** one feed per riser is assumed (extra feeds are treated as exports); ring mains/loops are not sized; changing the building level list after drawing keeps attachments but does not re-space existing pipe waypoints.

## Open items / next steps

1. ~~**Hot water (flow)**~~ — **done (Phase 1)**: roof plant, top-fed HW risers, per-dwelling HW demand table at 1.2 m/s, `Cold`/`Hot` sheet toggle. (Stainless HW limit 2.0 m/s works as a manual velocity override; per-material auto-default not yet wired.)
2. **Hot water return (recirculation)** — next up. Start simplified (recirc flow as a fraction of flow / velocity-based min, ~0.9 m/s, drawn as the parallel Ø HWR line), then upgrade to the workbook's heat-loss method (`HWR CALCS` / `HOT WATER RETURN DATA`: insulation + water/ambient temps) + circulating-pump head.
3. **Gas** — MJ/hr demand per dwelling, diversity, gas pipe tables.
4. **Surface headloss** in the drawing tool once validated.
5. **PDF / calc-sheet export** for issuing with a job.

_Done since review (2026-07-20): pinning a feed below the riser start, two-row meter clusters for big banks, right-drag pan, and size options (±1 size with velocities) on the pipe panel._

_Done 2026-07-24: **Hot-water flow (Phase 1)** — per-service state model (`services.cw` / `services.hw`), `Cold`/`Hot` sheet toggle, roof HW Plant node, HW per-dwelling demand + 1.2 m/s sizing, `♨ HW setup` mirroring the CW risers, cross-sheet level edits, and the v4 save format. Validated statically: the embedded JS parses cleanly (balanced structure) and HW sizing reproduces the Ø40→Ø50→Ø65→Ø80 Cu progression seen on the XH_400 Tower 4 HW schematic. Browser smoke-test still recommended._

## Files

| File | What it is |
|---|---|
| `GFB_Schematic_Drawing_Tool.html` | Main drawing + sizing tool. Double-click to open. |
| `gfb_pipe_sizer.zip` | Python reference engine + validation tests (`py -m pip install -r requirements.txt`, `py -m streamlit run ui/app.py`). |
| `GFB_Pipe_Sizing_AllSheetsVisible.xlsx` | Source workbook the logic was extracted from. |
| `XH_3003_COLD WATER SCHEMATICS-Model.pdf` | Real issued drawing used as the visual reference. |
| `GFB_Pipe_Sizer_HANDOFF.md` | This document. |
