"""Extract the gas reference data from the GFB master workbook into a JS block.

This is how the GAS_TABLES / GAS_DIVERSITY / GAS_SIZE_SELECTOR constants in the tool were
produced - the tables were never retyped. Re-run it when the workbook's GAS DATA sheet changes,
then paste gas_data.js over the corresponding block in GFB_Schematic_Drawing_Tool.html and
re-run verify_against_workbook.py.

    py tests/extract_gas_data.py ["path\\to\\XXXXX_GFB_Pipe Sizing Sheet.xlsx"]

Cells that fail the monotonicity check (capacity must fall as the run lengthens and rise as the
pipe grows) are emitted as null rather than as a number the tool would size on. Stdlib only, same
approach as verify_against_workbook.py.
"""
import json
import os
import sys
import zipfile
from xml.etree import ElementTree as ET

NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
RNS = '{http://schemas.openxmlformats.org/package/2006/relationships}'
RID = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id'

WORKBOOK_NAME = 'XXXXX_GFB_Pipe Sizing Sheet.xlsx'

# GAS DATA layout: header row carrying the index lengths, then one row per DN.
TABLES = [
    ('f12', 13, 'F.12', 'copper', 0.75, '2.75-5 kPa'),
    ('f13', 37, 'F.13', 'copper', 1.5, '5-10 kPa'),
    ('f24', 59, 'F.24', 'steel', 0.75, '2.75-5 kPa'),
    ('f25', 76, 'F.25', 'steel', 1.5, '5-10 kPa'),
]


def colname(i):
    s = ''
    i += 1
    while i:
        i, r = divmod(i - 1, 26)
        s = chr(65 + r) + s
    return s


COLS = [colname(i) for i in range(8, 44)]  # I..AR = the 36 length columns


def load(path):
    z = zipfile.ZipFile(path)
    shared = [''.join(t.text or '' for t in si.iter(NS + 't'))
              for si in ET.fromstring(z.read('xl/sharedStrings.xml')).iter(NS + 'si')]
    rels = {r.get('Id'): r.get('Target')
            for r in ET.fromstring(z.read('xl/_rels/workbook.xml.rels')).iter(RNS + 'Relationship')}
    sheets = {s.get('name'): 'xl/' + rels[s.get(RID)].lstrip('/')
              for s in ET.fromstring(z.read('xl/workbook.xml')).iter(NS + 'sheet')}
    return z, shared, sheets


def cells(z, shared, part):
    out = {}
    for c in ET.fromstring(z.read(part)).iter(NS + 'c'):
        v = c.find(NS + 'v')
        if v is None:
            continue
        out[c.get('r')] = shared[int(v.text)] if c.get('t') == 's' else v.text
    return out


def num(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def clean(v):
    """Trim float noise so the emitted JS matches the printed table."""
    if v is None:
        return None
    return int(v) if v == int(v) else round(v, 4)


def anomalies(dns, lengths, cap):
    """Capacity must fall as the run lengthens and rise as the pipe grows."""
    bad = []
    for r, row in enumerate(cap):
        for i in range(len(row) - 1):
            a, b = row[i], row[i + 1]
            if a is not None and b is not None and b > a:
                bad.append(('row', dns[r], lengths[i], lengths[i + 1], a, b))
    for r in range(len(cap) - 1):
        for i in range(len(lengths)):
            a, b = cap[r][i], cap[r + 1][i]
            if a is not None and b is not None and b < a:
                bad.append(('col', lengths[i], dns[r], dns[r + 1], a, b))
    return bad


def resolve_workbook(argv):
    if len(argv) > 1:
        return argv[1]
    here = os.path.dirname(os.path.abspath(__file__))
    for candidate in (os.path.join(os.path.dirname(here), WORKBOOK_NAME),
                      os.path.join(here, WORKBOOK_NAME),
                      os.path.join(os.path.expanduser('~'), 'Downloads', WORKBOOK_NAME)):
        if os.path.isfile(candidate):
            return candidate
    raise SystemExit('could not find %s - pass its path as the first argument' % WORKBOOK_NAME)


def main(argv):
    z, shared, sheets = load(resolve_workbook(argv))
    gd = cells(z, shared, sheets['GAS DATA'])

    tables = {}
    for key, hdr, label, material, drop, prange in TABLES:
        lengths = [clean(num(gd.get(c + str(hdr)))) for c in COLS]
        dns, cap = [], []
        r = hdr + 1
        while num(gd.get('AS' + str(r))) is not None:
            dns.append(int(num(gd['AS' + str(r)])))
            cap.append([clean(num(gd.get(c + str(r)))) for c in COLS])
            r += 1
        bad = anomalies(dns, lengths, cap)
        for kind, *rest in bad:
            if kind == 'row':
                dn, l1, l2, a, b = rest
                i = lengths.index(l2)
                cap[dns.index(dn)][i] = None  # impossible cell -> refuse to size on it
                print('  !! %s DN%s @ %sm = %s is impossible (DN%s @ %sm = %s) -> nulled'
                      % (label, dn, l2, b, dn, l1, a))
        tables[key] = {'label': label, 'material': material, 'drop': drop,
                       'range': prange, 'dn': dns, 'lengths': lengths, 'cap': cap}
        print('%s: DN %s, %d lengths, %d anomalies'
              % (label, dns, len([x for x in lengths if x is not None]), len(bad)))

    diversity = []
    for r in range(9, 89):
        n, f = num(gd.get('F' + str(r))), num(gd.get('G' + str(r)))
        if n is None or f is None:
            break
        diversity.append([int(n), round(f, 4)])
    print('diversity: %d rows, %s .. %s' % (len(diversity), diversity[0], diversity[-1]))

    selector = []
    for r in range(9, 20):
        idc, dn = num(gd.get('A' + str(r))), num(gd.get('B' + str(r)))
        ids, dss = num(gd.get('C' + str(r))), num(gd.get('D' + str(r)))
        if dn is None:
            break
        selector.append({'ID_mm': clean(idc), 'DN': int(dn),
                         'ID_ss': clean(ids), 'DN_ss': clean(dss)})
    print('selector: %d rows' % len(selector))

    def dump(name, obj, comment):
        j = json.dumps(obj, separators=(',', ':'))
        return '%s\nconst %s = %s;\n' % (comment, name, j)

    out = []
    out.append(dump('GAS_TABLES', tables,
                    '// AS 5601-2022 capacity tables (MJ/h) from the workbook\'s hidden GAS DATA sheet:\n'
                    '// F.12/F.13 natural gas through copper, F.24/F.25 through steel. cap[dnIndex][lengthIndex];\n'
                    '// null = not tabulated for that length, or a workbook cell the validator rejected.'))
    out.append(dump('GAS_DIVERSITY', diversity,
                    '// GAS DATA!F9:G88 — diversity factor by number of dwellings. Looked up like the\n'
                    '// workbook\'s VLOOKUP(...,TRUE): the largest row <= n, clamped at 80 dwellings.'))
    out.append(dump('GAS_SIZE_SELECTOR', selector,
                    '// GAS DATA!A9:D19 — the pipe size selector (copper I.D./DN and the stainless columns).'))
    js = '\n'.join(out)

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'gas_data.js')
    with open(out, 'w', encoding='utf-8') as fh:
        fh.write(js)
    print('\nwrote %s (%d bytes)' % (out, len(js)))


if __name__ == '__main__':
    main(sys.argv)
