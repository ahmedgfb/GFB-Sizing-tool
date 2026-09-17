# Tests

```
py tests/run_all.py                       # everything (needs Chrome or Edge)
py tests/run_suite.py tests/suite_gas.js  # one suite
py verify_against_workbook.py             # the reference data, against the workbook
```

The tool is one HTML file with no module system, so there is nothing to import. Every suite loads
the **real** `GFB_Schematic_Drawing_Tool.html` in a headless browser, injects itself as an extra
`<script>`, and reads assertions back out of a `<pre id="results">`.

| File | What it covers |
|---|---|
| `suite_gas.js` | 61 assertions. The gas engine against the workbook: diversity curve, capacity lookups, `GAS CALCS` columns G/H, the `MAIN PIPE` sheet, per-riser overrides, save/load v5→v6, and the guard that diversified loads are never summed. |
| `suite_ui.js` | 48 assertions. Sheet switching, the gas auto-build, the drawing, every panel, the toolbar, undo/redo, PDF naming — and that the cold sheet is untouched by all of it. |
| `suite_perriser.js` | 23 assertions. Per-riser demand/dwelling: the override survives typing (no focus loss), and a main serving risers at different MJ/hr blends them instead of applying one sheet-wide rate. |
| `suite_water_regression.js` | Prints every number the cold and hot sheets produce. Not pass/fail on its own: `run_all.py` runs it against `HEAD`'s tool and the working copy and requires the output to be identical. |
| `extract_gas_data.py` | Regenerates the embedded gas tables from the workbook. They were never retyped. |

## Writing a suite

`ok(name, got, want)` asserts, `note(text)` annotates. Use `defer(fn)` for anything that depends
on `pushUndo`, which commits its snapshot on a `setTimeout(...,0)` — a synchronous undo assertion
will read stale state and look like a bug in the tool.

## Two known accidents worth not rediscovering

- **`--headless=old`, not `=new`.** The new mode prints nothing with `--dump-dom`.
- **Edge may emit nothing at all.** On the machine this was written, Edge 153 produced empty
  stdout for every command including `--version`, so the runner prefers Chrome. Override with
  `GFB_TEST_BROWSER`.

**Verify numerically, not visually.** Every real bug found in this codebase looked fine in a
screenshot: overlapping HW mains carrying conflicting Ø callouts, a connect-mode feed pipe
collapsed to a point, and — in the gas work — the temptation to add two risers' diversified
loads, which looks right on the drawing and undersizes the main.
