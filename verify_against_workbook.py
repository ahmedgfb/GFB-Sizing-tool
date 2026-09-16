"""Re-verify the pipe-sizing reference data embedded in GFB_Schematic_Drawing_Tool.html
against GFB's pipe-sizing workbook.

The tool hardcodes the workbook's tables (PSFR curve, pipe ID/DN tables, hot-water
per-dwelling demand, and the AS 5601 gas capacity grids + diversity curve) so it can run as
a single self-contained HTML file. That data will silently drift the next time the workbook
is revised - this script re-runs the whole comparison so drift shows up immediately.

Sheets and table blocks are located by NAME and by their own headers, never by position:
the workbook has already gained a sheet and shifted rows once, which silently pointed the
positional version of this script at the wrong data.

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
RELS_NS = "{http://schemas.openxmlformats.org/package/2006/relationships}"
DOC_REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"

# Sheets are resolved by NAME, via workbook.xml and its rels.
#
# This used to be a hardcoded {name: "xl/worksheets/sheetN.xml"} map, on the assumption that the
# file indices were stable. They are not: the master has since gained an "RCW CALCS" sheet, which
# shifted every index from 4 upwards and had this script silently reading GAS DATA as COLD WATER
# DATA. Resolving by name survives any future insertion.

TOL = 1e-9
CAP_TOL = 1e-6


# --------------------------------------------------------------------------- xlsx reading

class Workbook:
    """Minimal read-only .xlsx reader: cached values plus formula text, per sheet."""

    def __init__(self, path):
        self.path = path
        self._zip = zipfile.ZipFile(path)
        self._strings = self._read_shared_strings()
        self._parts = self._read_sheet_parts()
        self._sheets = {}

    def _read_shared_strings(self):
        if "xl/sharedStrings.xml" not in self._zip.namelist():
            return []
        root = ET.fromstring(self._zip.read("xl/sharedStrings.xml"))
        return ["".join(t.text or "" for t in si.iter(NS + "t"))
                for si in root.findall(NS + "si")]

    def _read_sheet_parts(self):
        """{sheet name: zip part} straight from workbook.xml and its relationships."""
        rels = ET.fromstring(self._zip.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target")
                   for r in rels.iter(RELS_NS + "Relationship")}
        parts = {}
        for sheet in ET.fromstring(self._zip.read("xl/workbook.xml")).iter(NS + "sheet"):
            target = targets.get(sheet.get(DOC_REL), "")
            parts[sheet.get("name")] = "xl/" + target.lstrip("/")
        return parts

    def sheet_names(self):
        return list(self._parts)

    def sheet(self, name):
        """{cell_ref: (value, formula_or_None)} for one sheet."""
        if name not in self._sheets:
            if name not in self._parts:
                raise SystemExit("workbook has no sheet named %r (it has: %s)"
                                 % (name, ", ".join(self._parts)))
            root = ET.fromstring(self._zip.read(self._parts[name]))
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
        "GAS_TABLES": grab("GAS_TABLES", "{"),
        "GAS_DIVERSITY": grab("GAS_DIVERSITY", "["),
        "GAS_SIZE_SELECTOR": grab("GAS_SIZE_SELECTOR", "["),
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
    "gasDiversity":
        "function gasDiversity(dwellings){ const n=+dwellings||0; "
        "if(n<GAS_DIVERSITY[0][0]) return null; let f=GAS_DIVERSITY[0][1]; "
        "for(const [count,factor] of GAS_DIVERSITY){ if(count<=n) f=factor; else break; } "
        "return f; }",
    "gasCapacity":
        "function gasCapacity(tableKey, dn, indexLength){ const t=gasTable(tableKey); "
        "const di=t.dn.indexOf(+dn), li=t.lengths.indexOf(+indexLength); "
        "if(di<0||li<0) return null; const v=t.cap[di][li]; return v==null? null : v; }",
    "selectGasPipe":
        "function selectGasPipe(mjhr, tableKey, indexLength){ const t=gasTable(tableKey); "
        "const q=+mjhr||0; for(const dn of t.dn){ "
        "const cap=gasCapacity(tableKey,dn,indexLength); if(cap!=null && cap>=q) return {DN:dn, cap}; } "
        "return null; }",
    "gasAdjusted":
        "function gasAdjusted(dwellings, perDwelling, diversityOn, plantLoad){ "
        "const dw=+dwellings||0, per=+perDwelling||0, plant=+plantLoad||0; "
        "if(dw<=0) return plant; const f = diversityOn ? gasDiversity(dw) : 1; "
        "return dw*per*(f==null?1:f) + plant; }",
    "gasTolerance":
        "function gasTolerance(pct){ const p=+pct; "
        "return 1 + ((isNaN(p)? GAS_DEFAULTS.tolerancePct : p)/100); }",
}


# ------------------------------------------------------------------------- gas: the mirrors
#
# GAS DATA holds four AS 5601-2022 capacity grids. Each is anchored by a "DN" label in column AS
# on the header row that carries the index lengths, so they are located rather than hardcoded.
GAS_DATA_SHEET = "GAS DATA"
GAS_LENGTH_COLS = ["I", "J", "K", "L", "M", "N", "O", "P", "Q", "R", "S", "T", "U", "V", "W",
                   "X", "Y", "Z", "AA", "AB", "AC", "AD", "AE", "AF", "AG", "AH", "AI", "AJ",
                   "AK", "AL", "AM", "AN", "AO", "AP", "AQ", "AR"]
# tool key -> the workbook's own name for the table, for the failure messages
GAS_TABLE_NAMES = {"f12": "F.12", "f13": "F.13", "f24": "F.24", "f25": "F.25"}


def gas_header_rows(wb):
    """Rows in GAS DATA that carry a capacity table's index-length header, in sheet order.

    Anchored on the table titles in column I ("TABLE F.12 - 2022", "Table F.24", ...) rather than
    on the "DN" label in column AS: F.13's block has no such label, and titles are what a reader
    would look for anyway.
    """
    titles = []
    for ref, (value, _) in wb.sheet(GAS_DATA_SHEET).items():
        m = re.fullmatch(r"I(\d+)", ref)
        if m and isinstance(value, str) and re.match(r"\s*table\s+f\.?\d", value, re.I):
            titles.append(int(m.group(1)))
    rows = []
    for title_row in sorted(titles):
        # the header is the first row below the title whose column I holds the first index length
        for row in range(title_row + 1, title_row + 12):
            if wb.number(GAS_DATA_SHEET, "I%d" % row) == 2:
                rows.append(row)
                break
    return rows


def read_gas_table(wb, header_row):
    """(lengths, [(dn, [capacity per length])]) for the table under one header row.

    The DN for each row is taken from column AS where it is labelled, and the rows run until that
    column runs out.
    """
    lengths = [wb.number(GAS_DATA_SHEET, "%s%d" % (col, header_row)) for col in GAS_LENGTH_COLS]
    rows = []
    row = header_row + 1
    while wb.number(GAS_DATA_SHEET, "AS%d" % row) is not None:
        dn = int(wb.number(GAS_DATA_SHEET, "AS%d" % row))
        rows.append((dn, [wb.number(GAS_DATA_SHEET, "%s%d" % (col, row))
                          for col in GAS_LENGTH_COLS]))
        row += 1
    return lengths, rows


def gas_table_anomalies(dns, lengths, cap):
    """Cells that break the physics: capacity must fall as the run lengthens and rise as the
    pipe grows. This is what caught F.12 DN65 @ 4 m = 137776 in GFB's own template."""
    bad = []
    for r, row in enumerate(cap):
        for i in range(len(row) - 1):
            a, b = row[i], row[i + 1]
            if a is not None and b is not None and b > a:
                bad.append("DN%s rises with length: %sm=%s -> %sm=%s"
                           % (dns[r], lengths[i], a, lengths[i + 1], b))
    for r in range(len(cap) - 1):
        for i in range(len(lengths)):
            a, b = cap[r][i], cap[r + 1][i]
            if a is not None and b is not None and b < a:
                bad.append("capacity falls with size at %sm: DN%s=%s -> DN%s=%s"
                           % (lengths[i], dns[r], a, dns[r + 1], b))
    return bad


# The one workbook cell this script knowingly refuses to trust. Present in every copy checked:
# the master, all six Ellen Street "V5" sheets and the Resizing copy - so it is a defect in GFB's
# template, not a corrupted file. The tool carries it as null so a lookup landing there reports
# "not tabulated" instead of a wrong size.
GAS_KNOWN_BAD = [("f12", 65, 4)]


def gas_diversity_py(dwellings, curve):
    """Mirror of gasDiversity(): VLOOKUP(...,TRUE) - the largest tabulated count <= n."""
    n = dwellings or 0
    if n < curve[0][0]:
        return None
    factor = curve[0][1]
    for count, value in curve:
        if count <= n:
            factor = value
        else:
            break
    return factor


def select_gas_pipe_py(mjhr, table, index_length):
    """Mirror of selectGasPipe(): smallest DN whose tabulated capacity covers the demand."""
    try:
        li = table["lengths"].index(index_length)
    except ValueError:
        return None
    for di, dn in enumerate(table["dn"]):
        cap = table["cap"][di][li]
        if cap is not None and cap >= mjhr:
            return dn
    return None


def gas_adjusted_py(dwellings, per_dwelling, diversity_on, plant_load, curve):
    """Mirror of gasAdjusted() / GAS CALCS column G."""
    if dwellings <= 0:
        return plant_load
    factor = gas_diversity_py(dwellings, curve) if diversity_on else 1
    return dwellings * per_dwelling * (1 if factor is None else factor) + plant_load


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
        # Anchor on the block's own "I.D." header rather than assuming it starts at row 5 -
        # COLD WATER DATA's first block sits one row higher than HOT WATER DATA's, and a hardcoded
        # row 5 read the whole table off by one. check_capacity_bands already works this way.
        headers = block_header_rows(wb, sheet, id_col)
        if not headers:
            report.check("%s!%s ID/DN" % (sheet, id_col),
                         ["no 'I.D.' header found in column %s" % id_col])
            continue
        first_row = headers[0] + 1
        for i, pipe in enumerate(table):
            row = first_row + i
            book_id = wb.number(sheet, "%s%d" % (id_col, row))
            book_dn = wb.number(sheet, "%s%d" % (dn_col, row))
            if book_id is None or book_dn is None:
                problems.append("%s!%s%d is empty" % (sheet, id_col, row))
            else:
                if abs(book_id - pipe["ID_mm"]) > CAP_TOL:
                    problems.append("row %d: workbook I.D. %s, tool %s" % (row, book_id, pipe["ID_mm"]))
                if abs(book_dn - pipe["DN"]) > TOL:
                    problems.append("row %d: workbook DN %s, tool %s" % (row, book_dn, pipe["DN"]))
        label = "%s ID/DN, %s!%s%d:%s%d" % (
            "Stainless" if material == "stainless_steel" else "Copper Type B",
            sheet, id_col, first_row, dn_col, first_row + len(table) - 1)
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


def check_gas_tables(wb, tool, report):
    """8. The four AS 5601-2022 capacity grids, cell for cell against GAS DATA."""
    headers = gas_header_rows(wb)
    tool_tables = tool["GAS_TABLES"]
    order = ["f12", "f13", "f24", "f25"]
    problems = []
    if len(headers) != len(order):
        problems.append("expected %d 'DN' header rows in GAS DATA!AS, found %d (%s)"
                        % (len(order), len(headers), headers))
        report.check("Gas capacity tables, GAS DATA", problems)
        return

    for key, header in zip(order, headers):
        name = GAS_TABLE_NAMES[key]
        book_lengths, book_rows = read_gas_table(wb, header)
        table = tool_tables.get(key)
        if table is None:
            problems.append("%s: tool has no GAS_TABLES.%s" % (name, key))
            continue
        if [x for x in book_lengths if x is not None] != [x for x in table["lengths"] if x is not None]:
            problems.append("%s: index lengths differ (workbook %s, tool %s)"
                            % (name, book_lengths, table["lengths"]))
            continue
        if [dn for dn, _ in book_rows] != table["dn"]:
            problems.append("%s: DN list differs (workbook %s, tool %s)"
                            % (name, [dn for dn, _ in book_rows], table["dn"]))
            continue
        for di, (dn, book_caps) in enumerate(book_rows):
            for li, book_cap in enumerate(book_caps):
                tool_cap = table["cap"][di][li]
                length = book_lengths[li]
                if (key, dn, length) in GAS_KNOWN_BAD:
                    if tool_cap is not None:
                        problems.append("%s DN%s @ %sm: known-bad workbook cell (%s) must be "
                                        "carried as null, tool has %s" % (name, dn, length, book_cap, tool_cap))
                    continue
                if book_cap is None and tool_cap is None:
                    continue
                if book_cap is None or tool_cap is None or abs(book_cap - tool_cap) > TOL:
                    problems.append("%s DN%s @ %sm: workbook %s, tool %s"
                                    % (name, dn, length, book_cap, tool_cap))
    cells = sum(len(t["dn"]) * len(t["lengths"]) for t in tool_tables.values())
    report.check("Gas capacity tables, GAS DATA (4 tables, %d cells)" % cells, problems)


def check_gas_diversity(wb, tool, report):
    """9. Diversity factor by dwelling count, GAS DATA!F9:G88."""
    curve = tool["GAS_DIVERSITY"]
    problems = []
    book = []
    for row in range(9, 89):
        count = wb.number(GAS_DATA_SHEET, "F%d" % row)
        factor = wb.number(GAS_DATA_SHEET, "G%d" % row)
        if count is None or factor is None:
            break
        book.append((int(count), factor))
    if len(book) != len(curve):
        problems.append("row count: workbook %d, tool %d" % (len(book), len(curve)))
    else:
        for (count, factor), entry in zip(book, curve):
            if count != entry[0] or abs(factor - entry[1]) > TOL:
                problems.append("%d dwellings: workbook %s, tool %s -> %s"
                                % (count, factor, entry[0], entry[1]))
    report.check("Gas diversity curve, GAS DATA!F9:G88 (%d rows)" % len(book), problems)


def check_gas_table_sanity(wb, tool, report):
    """10. The capacity grids must be physically monotonic.

    This is the gas analogue of the MAX FLOW check: it catches a mistyped table cell, which is a
    defect the cell-for-cell comparison above cannot see (it would agree with the workbook).
    """
    problems = []
    for key, table in tool["GAS_TABLES"].items():
        bad = gas_table_anomalies(table["dn"], table["lengths"], table["cap"])
        problems.extend("%s: %s" % (GAS_TABLE_NAMES.get(key, key), b) for b in bad)
    report.check("Gas tables are monotonic (mistyped-cell guard)", problems)


def check_gas_selection_sweep(wb, tool, report):
    """11. selectGasPipe over every table x every tabulated index length."""
    problems = []
    checked = 0
    for key, table in tool["GAS_TABLES"].items():
        name = GAS_TABLE_NAMES.get(key, key)
        for li, length in enumerate(table["lengths"]):
            caps = [table["cap"][di][li] for di in range(len(table["dn"]))]
            live = [(table["dn"][di], c) for di, c in enumerate(caps) if c is not None]
            if not live:
                continue
            for dn, cap in live:
                # just inside this size, and a hair over it
                for demand, expect in ((cap, dn), (cap * (1 - 1e-9), dn)):
                    got = select_gas_pipe_py(demand, table, length)
                    checked += 1
                    if got != expect:
                        problems.append("%s @ %sm, %.4f MJ/h: expected DN%s, got DN%s"
                                        % (name, length, demand, expect, got))
                over = cap * (1 + 1e-6)
                bigger = [d for d, c in live if c >= over]
                got = select_gas_pipe_py(over, table, length)
                checked += 1
                expect = bigger[0] if bigger else None
                if got != expect:
                    problems.append("%s @ %sm, just over DN%s: expected %s, got %s"
                                    % (name, length, dn, expect, got))
            checked += 1
            if select_gas_pipe_py(live[-1][1] * 10, table, length) is not None:
                problems.append("%s @ %sm: demand past the table top should be unsized" % (name, length))
    report.check("Gas selection sweep (%d lookups)" % checked, problems)


def check_gas_calcs(wb, tool, report):
    """12. Reproduce the published sizes on GAS CALCS, column by column.

    The riser blocks carry their own inputs, so the sheet's own numbers drive the mirror: this
    reads the workbook's dwellings, demand/dwelling, plant loads, index length and table choice,
    recomputes columns F/G/H in Python, and compares against the cached cell values.
    """
    problems = []
    rows_checked = 0
    front = "FRONT PAGE"
    per_dwelling = wb.number("GAS CALCS", "D4")
    index_length = wb.number("GAS CALCS", "L3")
    table_choice = wb.value(front, "F14")
    diversity_on = str(wb.value(front, "F15")).upper() == "ON"
    tolerance_pct = wb.number(front, "B15")
    tolerance = 1.1 if tolerance_pct is None else 1 + tolerance_pct / 100.0

    key = {"F12-2.75kPa": "f12", "F13-5kPa": "f13",
           "F24 - 2.75kPa (STEEL)": "f24", "F25 - 5kPa (STEEL)": "f25"}.get(str(table_choice))
    table = tool["GAS_TABLES"].get(key) if key else None
    if table is None or per_dwelling is None or index_length is None:
        report.check("GAS CALCS riser 1 (column F/G/H)",
                     ["cannot read the sheet's gas inputs: table=%r, MJ/hr=%r, index length=%r"
                      % (table_choice, per_dwelling, index_length)])
        return

    curve = tool["GAS_DIVERSITY"]
    plant_below = {}
    running = 0.0
    for row in range(65, 4, -1):  # column J, summed from the row downwards (J_row:J$65)
        running += wb.number("GAS CALCS", "J%d" % row) or 0.0
        plant_below[row] = running

    for row in range(5, 66):
        dwellings = wb.number("GAS CALCS", "C%d" % row)
        book_g = wb.number("GAS CALCS", "G%d" % row)
        book_h = wb.value("GAS CALCS", "H%d" % row)
        if dwellings is None or book_g is None:
            continue
        mine_g = gas_adjusted_py(dwellings, per_dwelling, diversity_on, plant_below[row], curve)
        if abs(mine_g - book_g) > 1e-6:
            problems.append("G%d: workbook %s, mirror %s (%s dwellings)"
                            % (row, book_g, mine_g, dwellings))
        if book_h not in (None, "-", ""):
            mine_h = select_gas_pipe_py(book_g * tolerance, table, index_length)
            if mine_h is None or abs(float(book_h) - mine_h) > TOL:
                problems.append("H%d: workbook DN%s, mirror DN%s (%s MJ/hr x %.2f)"
                                % (row, book_h, mine_h, book_g, tolerance))
        rows_checked += 1
    report.check("GAS CALCS riser 1, columns G + H (%d rows, %s @ %sm)"
                 % (rows_checked, GAS_TABLE_NAMES.get(key, key), index_length), problems)


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

    print("  3. Gas table F.12, DN65 at an index length of 4 m.")
    for key, dn, length in GAS_KNOWN_BAD:
        header = gas_header_rows(wb)[["f12", "f13", "f24", "f25"].index(key)]
        lengths, rows = read_gas_table(wb, header)
        caps = dict(rows)[dn]
        around = [(lengths[i], caps[i]) for i in range(3)]
        print("     Workbook %s reads %s" % (GAS_TABLE_NAMES[key],
              "  ".join("%sm=%s" % (L, c) for L, c in around)))
    print("     The 4 m cell is impossible - 12x its neighbours, and above DN80 at the same")
    print("     length. It is present in every copy checked (the master, all six Ellen Street")
    print("     'V5' sheets and the Resizing copy), so it is a defect in GFB's template rather")
    print("     than a corrupted file. The tool carries that one cell as null, so a lookup")
    print("     landing on it reports 'not tabulated' instead of a wrong size. Only an index")
    print("     length of 4 m is affected. Worth correcting in the template from the standard.")


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
    check_gas_tables(wb, tool, report)
    check_gas_diversity(wb, tool, report)
    check_gas_table_sanity(wb, tool, report)
    check_gas_selection_sweep(wb, tool, report)
    check_gas_calcs(wb, tool, report)
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
