"""Re-verify the pipe-sizing reference data embedded in GFB_Schematic_Drawing_Tool.html
against GFB's pipe-sizing workbook.

The tool hardcodes the workbook's tables (PSFR curve, pipe ID/DN tables, hot-water
per-dwelling demand) so it can run as a single self-contained HTML file. That data will
silently drift the next time the workbook is revised - this script re-runs the whole
comparison so drift shows up immediately.

Usage:
    py verify_against_workbook.py ["path\\to\\workbook.xlsx"] ["path\\to\\tool.html"]

With no arguments it looks for "XXXXX_GFB_Pipe Sizing Sheet.xlsx" (the master template)
next to this script and then in ~/Downloads, and for the tool HTML next to this script.

Standard library only - no openpyxl, no pip install. The .xlsx is read as a zip and its
sheet XML parsed directly, so this stays as dependency-free as the tool it checks.

Exit code 0 if every check passes, 1 otherwise.
"""

import json
import math
import os
import re
import sys
import xml.etree.ElementTree as ET
import zipfile

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"

# Sheet file indices are stable across both revisions of the workbook.
SHEETS = {
    "FRONT PAGE": "xl/worksheets/sheet1.xml",
    "CW CALCS": "xl/worksheets/sheet3.xml",
    "HW CALCS": "xl/worksheets/sheet4.xml",
    "COLD WATER DATA": "xl/worksheets/sheet7.xml",
    "HOT WATER DATA": "xl/worksheets/sheet8.xml",
}

TOL = 1e-9
CAP_TOL = 1e-6


# --------------------------------------------------------------------------- xlsx reading

class Workbook:
    """Minimal read-only .xlsx reader: cached values plus formula text, per sheet."""

    def __init__(self, path):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._strings = self._read_shared_strings()
        self._sheets = {}

    def _read_shared_strings(self):
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        return ["".join(t.text or "" for t in si.iter(NS + "t"))
                for si in root.findall(NS + "si")]

    def sheet(self, name):
        """{cell_ref: (value, formula_or_None)} for one sheet."""
        if name not in self._sheets:
            root = ET.fromstring(self._zip.read(SHEETS[name]))
            cells = {}
            for row in root.iter(NS + "row"):
                for c in row:
                    v = c.find(NS + "v")
                    f = c.find(NS + "f")
                    value = v.text if v is not None else None
                    if c.get("t") == "s" and value is not None:
                        value = self._strings[int(value)]
                    cells[c.get("r")] = (value, f.text if f is not None else None)
            self._sheets[name] = cells
        return self._sheets[name]

    def value(self, sheet, ref):
        return self.sheet(sheet).get(ref, (None, None))[0]

    def number(self, sheet, ref):
        try:
            return float(self.value(sheet, ref))
        except (TypeError, ValueError):
            return None

    def formula(self, sheet, ref):
        return self.sheet(sheet).get(ref, (None, None))[1]


def block_header_rows(wb, sheet, column):
    """Rows holding an 'I.D.' header in `column` - one per riser block."""
    rows = []
    for ref, (value, _) in wb.sheet(sheet).items():
        m = re.fullmatch(r"([A-Z]+)(\d+)", ref)
        if m and m.group(1) == column and value == "I.D.":
            rows.append(int(m.group(2)))
    return sorted(rows)


# ---------------------------------------------------------------- the tool's embedded data

def read_tool_data(html_path):
    """Pull the three reference constants out of the tool's <script> block.

    They are written as JSON literals, so they are parsed rather than re-implemented -
    the point is to test the values actually shipped in the HTML.
    """
    with open(html_path, encoding="utf-8") as fh:
        html = fh.read()

    def grab(name, opener):
        m = re.search(r"const %s\s*=\s*(%s.*?);" % (name, re.escape(opener)), html, re.S)
        if not m:
            raise SystemExit("could not find `const %s = ...` in %s" % (name, html_path))
        return json.loads(m.group(1))

    return {
        "PSFR": grab("PSFR", "["),
        "PIPE_TABLES": grab("PIPE_TABLES", "{"),
        "HW_PER_DWELLING": grab("HW_PER_DWELLING", "["),
        "_js": {name: extract_js_function(html, name) for name in MIRRORED_JS},
    }


def extract_js_function(html, name):
    """Source of `function name(...){...}`, comments stripped and whitespace collapsed."""
    start = html.find("function %s(" % name)
    if start < 0:
        return None
    depth = 0
    for i in range(html.index("{", start), len(html)):
        if html[i] == "{":
            depth += 1
        elif html[i] == "}":
            depth -= 1
            if depth == 0:
                body = html[start:i + 1]
                body = re.sub(r"//[^\n]*", "", body)
                return re.sub(r"\s+", " ", body).strip()
    return None


# The JS sizing functions this script mirrors in Python, normalised (comments stripped,
# whitespace collapsed). Check 7 fails if the HTML drifts from these, because the mirrors
# below would then be testing something the tool no longer does. There is no JS runtime on
# this machine to execute the real functions, so this guard is what keeps the mirror honest:
# if it fires, re-read the JS and update capacity()/select_pipe_tool() to match.
MIRRORED_JS = {
    "areaM2":
        "function areaM2(idmm){ const r=(idmm/1000)/2; return Math.PI*r*r; }",
    "maxFlowForVel":
        "function maxFlowForVel(idmm, vmax){ return areaM2(idmm)*vmax*1000; }",
    "selectPipe":
        "function selectPipe(flowLs, material, vmax){ "
        "const table=[...pipeTable(material)].sort((a,b)=>a.ID_mm-b.ID_mm); "
        "if(flowLs==null||flowLs<=0) return table[0]; "
        "for(const p of table){ if(maxFlowForVel(p.ID_mm,vmax)>=flowLs) return p; } "
        "return null; }",
}


def capacity(id_mm, vmax):
    """Tool's maxFlowForVel(): pipe capacity in L/s at a velocity limit."""
    return math.pi * ((id_mm / 1000) / 2) ** 2 * vmax * 1000


def select_pipe_tool(flow, table, vmax):
    """Tool's selectPipe(): smallest pipe whose capacity meets the flow."""
    for pipe in sorted(table, key=lambda p: p["ID_mm"]):
        if capacity(pipe["ID_mm"], vmax) >= flow:
            return pipe["DN"]
    return None


def dn_label(dn):
    """'DN32' / 'over capacity' - keeps int and float DNs printing the same way."""
    return "over capacity" if dn is None else "DN%g" % float(dn)


def select_pipe_workbook(flow, bands):
    """The workbook's XLOOKUP(flow, MAX FLOW, ID, , 1) - exact match or next larger.

    On an unsorted lookup array XLOOKUP returns the *smallest* qualifying value, not the
    first one encountered. Honouring that is what lets check 5 catch a MAX FLOW cell whose
    formula has been overwritten out of order.
    """
    best = None
    for max_flow, dn in bands:
        if max_flow >= flow and (best is None or max_flow < best[0]):
            best = (max_flow, dn)
    return None if best is None else best[1]


# ------------------------------------------------------------------------------- reporting

class Report:
    def __init__(self):
        self.failures = 0

    def check(self, label, problems, detail_limit=6):
        if problems:
            self.failures += 1
            print("  %s %s FAIL (%d)" % (label, "." * max(1, 52 - len(label)), len(problems)))
            for line in problems[:detail_limit]:
                print("        %s" % line)
            if len(problems) > detail_limit:
                print("        ... and %d more" % (len(problems) - detail_limit))
        else:
            print("  %s %s OK" % (label, "." * max(1, 52 - len(label))))


# ---------------------------------------------------------------------------------- checks

def check_psfr(wb, tool, report):
    """1. Loading-unit -> probable simultaneous flow curve."""
    rows = [(wb.number("COLD WATER DATA", "A%d" % r), wb.number("COLD WATER DATA", "B%d" % r))
            for r in range(3, 137)]
    psfr = tool["PSFR"]
    problems = []
    if len(psfr) != len(rows):
        problems.append("row count: tool has %d, workbook A3:B136 has %d" % (len(psfr), len(rows)))
    else:
        for i, ((lu, flow), entry) in enumerate(zip(rows, psfr)):
            if lu is None or flow is None:
                problems.append("COLD WATER DATA!A%d/B%d is empty" % (i + 3, i + 3))
            elif abs(lu - entry["LU"]) > TOL or abs(flow - entry["flow_Ls"]) > TOL:
                problems.append("row %d: workbook LU=%s -> %s L/s, tool LU=%s -> %s L/s"
                                % (i + 3, lu, flow, entry["LU"], entry["flow_Ls"]))
    report.check("PSFR curve, COLD WATER DATA!A3:B136 (%d rows)" % len(rows), problems)


def check_hw_per_dwelling(wb, tool, report):
    """2. Hot-water demand per number of dwellings served."""
    table = tool["HW_PER_DWELLING"]
    problems = []
    if len(table) != 101:
        problems.append("tool table has %d entries, expected 101 (index 0 unused + 1..100)"
                        % len(table))
    for n in range(1, 101):
        book = wb.number("HOT WATER DATA", "B%d" % (n + 1))
        if book is None:
            problems.append("HOT WATER DATA!B%d is empty" % (n + 1))
        elif n < len(table) and abs(book - table[n]) > TOL:
            problems.append("%d dwellings: workbook %s L/s, tool %s L/s" % (n, book, table[n]))
    report.check("HW per-dwelling demand, HOT WATER DATA!A2:B101", problems)


def check_pipe_tables(wb, tool, report):
    """3. Pipe internal diameters and nominal sizes, on both data sheets."""
    layouts = [
        ("COLD WATER DATA", "stainless_steel", "D", "E"),
        ("COLD WATER DATA", "copper_type_b", "L", "M"),
        ("HOT WATER DATA", "stainless_steel", "D", "E"),
        ("HOT WATER DATA", "copper_type_b", "L", "M"),
    ]
    for sheet, material, id_col, dn_col in layouts:
        table = tool["PIPE_TABLES"][material]
        problems = []
        for i, pipe in enumerate(table):
            row = 5 + i
            book_id = wb.number(sheet, "%s%d" % (id_col, row))
            book_dn = wb.number(sheet, "%s%d" % (dn_col, row))
            if book_id is None or book_dn is None:
                problems.append("%s!%s%d is empty" % (sheet, id_col, row))
            else:
                if abs(book_id - pipe["ID_mm"]) > CAP_TOL:
                    problems.append("row %d: workbook I.D. %s, tool %s" % (row, book_id, pipe["ID_mm"]))
                if abs(book_dn - pipe["DN"]) > TOL:
                    problems.append("row %d: workbook DN %s, tool %s" % (row, book_dn, pipe["DN"]))
        label = "%s ID/DN, %s!%s5:%s14" % (
            "Stainless" if material == "stainless_steel" else "Copper Type B",
            sheet, id_col, dn_col)
        report.check(label, problems)


def check_capacity_bands(wb, report):
    """4. Every MAX FLOW cell equals VEL * area * 1000, across all riser blocks.

    This is the check that catches a MAX FLOW formula that has been typed over with a
    literal - the defect present in GFB_Pipe_Sizing_AllSheetsVisible.xlsx at
    COLD WATER DATA!O8 (copper DN32, RISER 1).
    """
    for sheet in ("COLD WATER DATA", "HOT WATER DATA"):
        problems = []
        blocks = 0
        for material, id_col, dn_col, min_col, max_col, vel_col in (
                ("stainless", "D", "E", "F", "G", "H"),
                ("copper", "L", "M", "N", "O", "P")):
            for header in block_header_rows(wb, sheet, id_col):
                blocks += 1
                previous_max = None
                for i in range(1, 11):
                    row = header + i
                    id_mm = wb.number(sheet, "%s%d" % (id_col, row))
                    if id_mm is None:
                        continue
                    dn = wb.value(sheet, "%s%d" % (dn_col, row))
                    vel = wb.number(sheet, "%s%d" % (vel_col, row))
                    stored_max = wb.number(sheet, "%s%d" % (max_col, row))
                    stored_min = wb.number(sheet, "%s%d" % (min_col, row))
                    if vel is None:
                        problems.append("%s%d (%s DN%s): VEL cell is empty" % (vel_col, row, material, dn))
                        continue
                    expected_max = vel * ((id_mm / 1000) ** 2) * (math.pi / 4) * 1000
                    if stored_max is None or abs(stored_max - expected_max) > CAP_TOL:
                        problems.append(
                            "%s%d (%s DN%s): MAX FLOW is %s, formula gives %.6f"
                            % (max_col, row, material, dn, stored_max, expected_max))
                    expected_min = 0.001 if previous_max is None else previous_max + 0.001
                    if stored_min is None or abs(stored_min - expected_min) > CAP_TOL:
                        problems.append(
                            "%s%d (%s DN%s): MIN FLOW is %s, expected %.6f"
                            % (min_col, row, material, dn, stored_min, expected_min))
                    previous_max = stored_max
        report.check("Capacity bands, %s (%d material blocks)" % (sheet, blocks), problems)


def check_selection_sweep(wb, tool, report):
    """5. Pipe selection agrees with the workbook at every flow, not just in principle."""
    layouts = [
        ("COLD WATER DATA", "stainless_steel", "D", "E", "G", "H"),
        ("COLD WATER DATA", "copper_type_b", "L", "M", "O", "P"),
        ("HOT WATER DATA", "stainless_steel", "D", "E", "G", "H"),
        ("HOT WATER DATA", "copper_type_b", "L", "M", "O", "P"),
    ]
    for sheet, material, id_col, dn_col, max_col, vel_col in layouts:
        bands = []
        for row in range(5, 15):
            max_flow = wb.number(sheet, "%s%d" % (max_col, row))
            dn = wb.number(sheet, "%s%d" % (dn_col, row))
            if max_flow is not None and dn is not None:
                bands.append((max_flow, dn))
        # Use the velocity the workbook actually cached, so both sides are compared like
        # for like; the velocity *defaults* are reported separately under Notes.
        vmax = wb.number(sheet, "%s5" % vel_col)
        table = tool["PIPE_TABLES"][material]
        problems = []
        if not bands or vmax is None:
            problems.append("could not read the %s band table from %s" % (material, sheet))
        else:
            flow_milli = 1
            while flow_milli <= 45000:
                flow = flow_milli / 1000
                mine = select_pipe_tool(flow, table, vmax)
                theirs = select_pipe_workbook(flow, bands)
                if (float(mine) if mine is not None else None) != theirs:
                    problems.append("%.3f L/s: workbook %s, tool %s"
                                    % (flow, dn_label(theirs), dn_label(mine)))
                flow_milli += 1
        label = "Selection sweep 0.001-45 L/s, %s %s @ %s m/s" % (
            sheet.split()[0].title(),
            "SS" if material == "stainless_steel" else "Cu",
            vmax)
        report.check(label, problems)


def check_demand_formulas(wb, report):
    """6. The calc sheets still use the constants and lookup ranges the tool assumes."""
    problems = []

    cw = wb.formula("CW CALCS", "C6")
    if not cw:
        problems.append("CW CALCS!C6 has no formula - the sheet layout has changed")
    else:
        for token, why in (
                ("0.03", "dwelling curve linear term"),
                ("0.4554", "dwelling curve sqrt coefficient"),
                ("'COLD WATER DATA'!$A$3:$A$136", "PSFR lookup range (tool's PSFR is 134 rows)"),
                ("'COLD WATER DATA'!$B$3:$B$136", "PSFR result range")):
            if token not in cw:
                problems.append("CW CALCS!C6 no longer contains %s (%s)" % (token, why))

    hw = wb.formula("HW CALCS", "C6")
    if not hw:
        problems.append("HW CALCS!C6 has no formula - the sheet layout has changed")
    else:
        for token, why in (
                ("'HOT WATER DATA'!$A$2:$B$101", "HW per-dwelling lookup range (tool caps at 100)"),
                ("<101", "dwelling count at which the workbook falls back to the CW curve"),
                ("0.4554", "CW curve fallback above the table")):
            if token not in hw:
                problems.append("HW CALCS!C6 no longer contains %s (%s)" % (token, why))

    report.check("Demand formulas, CW CALCS!C6 + HW CALCS!C6", problems)


def check_js_mirror(tool, report):
    """7. The JS sizing functions still match what this script mirrors in Python.

    Checks 4 and 5 compare the workbook against a Python reimplementation of the tool's
    selectPipe(), because there is no JS runtime here to run the real one. That is only
    sound while the two stay in step - so fail loudly if the JS changes.
    """
    problems = []
    for name, expected in sorted(MIRRORED_JS.items()):
        actual = tool["_js"].get(name)
        if actual is None:
            problems.append("%s() not found in the tool HTML" % name)
        elif actual != expected:
            problems.append("%s() has changed - update capacity()/select_pipe_tool() to match:"
                            % name)
            problems.append("    tool now: %s" % actual)
            problems.append("    mirrored: %s" % expected)
    report.check("JS sizing functions mirrored by this script", problems, detail_limit=9)


# ----------------------------------------------------------------------------------- notes

def print_notes(wb):
    """Known, deliberate differences between the tool and the workbook.

    These are decisions, not drift, so they never affect the exit code - but they are
    echoed from the live workbook so a future reader sees them and knows they were
    considered rather than missed.
    """
    print()
    print("Notes - known intentional deviations (not failures):")

    cw_vel = wb.formula("FRONT PAGE", "G15")
    hw_vel = wb.formula("FRONT PAGE", "I15")
    print("  1. Velocity limits. Workbook FRONT PAGE!G15 = %s" % cw_vel)
    print("                               FRONT PAGE!I15 = %s" % hw_vel)
    print("     The workbook raises the HOT WATER limit to 2.0 m/s for stainless steel.")
    print("     The tool keeps 1.2 m/s for hot water in both materials (decided 2026-07-31);")
    print("     stainless can still be raised by hand via the per-network or per-riser override.")

    pairs = []
    for row in range(3, 13):
        ss = wb.number("COLD WATER DATA", "U%d" % row)
        dn = wb.number("COLD WATER DATA", "V%d" % row)
        if ss is not None and dn is not None:
            pairs.append("%g->%g" % (ss, dn))
    print("  2. Stainless size labelling. COLD WATER DATA!U3:V12 maps SS size to DN:")
    print("       %s" % "  ".join(pairs))
    print("     The workbook's FRONT PAGE displays the DN column; the tool's diameter callouts")
    print("     keep the raw stainless size (decided 2026-07-31).")


# ------------------------------------------------------------------------------------ main

def resolve_paths(argv):
    here = os.path.dirname(os.path.abspath(__file__))
    workbook = argv[1] if len(argv) > 1 else None
    html = argv[2] if len(argv) > 2 else os.path.join(here, "GFB_Schematic_Drawing_Tool.html")

    if workbook is None:
        name = "XXXXX_GFB_Pipe Sizing Sheet.xlsx"
        for candidate in (os.path.join(here, name),
                          os.path.join(os.path.expanduser("~"), "Downloads", name)):
            if os.path.isfile(candidate):
                workbook = candidate
                break
        else:
            raise SystemExit(
                "could not find the master workbook (%s) next to this script or in "
                "~/Downloads - pass its path as the first argument" % name)

    for path, what in ((workbook, "workbook"), (html, "tool HTML")):
        if not os.path.isfile(path):
            raise SystemExit("%s not found: %s" % (what, path))
    return workbook, html


def main(argv):
    workbook_path, html_path = resolve_paths(argv)
    wb = Workbook(workbook_path)
    tool = read_tool_data(html_path)

    print("Workbook: %s" % workbook_path)
    print("Tool:     %s" % html_path)
    print()

    report = Report()
    check_psfr(wb, tool, report)
    check_hw_per_dwelling(wb, tool, report)
    check_pipe_tables(wb, tool, report)
    check_capacity_bands(wb, report)
    check_selection_sweep(wb, tool, report)
    check_demand_formulas(wb, report)
    check_js_mirror(tool, report)

    print_notes(wb)

    print()
    if report.failures:
        print("%d check(s) FAILED - the tool's embedded data no longer matches the workbook."
              % report.failures)
        return 1
    print("All checks passed - the tool's pipe sizes match the workbook.")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
