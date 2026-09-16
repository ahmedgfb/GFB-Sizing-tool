"""Run an assertion suite against the real GFB_Schematic_Drawing_Tool.html in a headless browser.

The tool has no module system and no build step, so there is nothing to import: the only honest
way to test it is to load the actual file and drive its real functions. This injects a suite as
an extra <script> at the end of <body>, loads the page headless with --dump-dom, and reads the
assertions back out of a <pre id="results">.

Usage:
    py tests/run_suite.py tests/suite_gas.js                 # against the tool in this folder
    py tests/run_suite.py tests/suite_gas.js other_tool.html # against some other build

    py tests/run_all.py                                      # every suite

Suites call ok(name, got, want) / note(text), and defer(fn) for anything that has to run a turn
later (undo commits its snapshot on a setTimeout, so undo assertions must be deferred).

Exit code 0 if every assertion passed, 1 otherwise.

Browser notes, the hard way:
  - Use --headless=old. The new mode prints nothing with --dump-dom.
  - Chrome is the default here because Edge 153 on the original dev machine emitted nothing on
    stdout at all, --version included. Set GFB_TEST_BROWSER to override.
  - Spawn the browser directly. From PowerShell, `& $exe` drops stdout; use ProcessStartInfo with
    RedirectStandardOutput, or run this script from Python/Bash as intended.
  - Decode stdout as UTF-8: the DOM is full of Ø and ·.
"""

import html
import os
import re
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TOOL = os.path.join(os.path.dirname(HERE), "GFB_Schematic_Drawing_Tool.html")

BROWSER_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser():
    override = os.environ.get("GFB_TEST_BROWSER")
    if override:
        if not os.path.isfile(override):
            raise SystemExit("GFB_TEST_BROWSER is not a file: %s" % override)
        return override
    for path in BROWSER_CANDIDATES:
        if os.path.isfile(path):
            return path
    raise SystemExit("no Chrome or Edge found - set GFB_TEST_BROWSER to a browser executable")


HARNESS = r'''
<pre id="results"></pre>
<script>
(function(){
  var out=[], pass=0, fail=0;
  function log(s){ out.push(s); }
  window.ok=function(name, got, want){
    var good = (got===want) || (typeof got==='number' && typeof want==='number' && Math.abs(got-want)<1e-6);
    if(good){ pass++; log('PASS  '+name+'  = '+got); }
    else { fail++; log('FAIL  '+name+'  got '+JSON.stringify(got)+'  want '+JSON.stringify(want)); }
  };
  window.note=function(s){ log('.     '+s); };
  window.finish=function(){
    log('');
    log('TOTAL '+(pass+fail)+'  PASS '+pass+'  FAIL '+fail);
    document.getElementById('results').textContent=out.join('\n');
  };
  // pushUndo commits its snapshot on a setTimeout(...,0), so anything asserting on undo has to
  // run after the event loop turns. Suites queue those with defer(); finish waits for them.
  var pending=0;
  window.defer=function(fn){ pending++; setTimeout(function(){
    try{ fn(); }catch(e){ fail++; log('THREW in defer '+(e&&e.stack||e)); }
    if(--pending===0) setTimeout(window.finish,0);
  }, 30); };
  try{ SUITE_BODY }
  catch(e){ fail++; log('THREW '+(e&&e.stack||e)); }
  if(pending===0) window.finish();
})();
</script>
'''


def run(suite_js, tool=None, quiet=False):
    tool = tool or DEFAULT_TOOL
    with open(tool, encoding="utf-8") as fh:
        page = fh.read()
    if "</body>" not in page:
        raise SystemExit("no </body> in %s" % tool)
    page = page.replace("</body>", HARNESS.replace("SUITE_BODY", suite_js) + "</body>")

    tmp = os.path.join(tempfile.gettempdir(), "gfb_suite_page.html")
    with open(tmp, "w", encoding="utf-8") as fh:
        fh.write(page)

    proc = subprocess.run(
        [find_browser(), "--headless=old", "--disable-gpu", "--no-sandbox",
         "--user-data-dir=" + os.path.join(tempfile.gettempdir(), "gfb_test_profile"),
         "--virtual-time-budget=30000", "--dump-dom",
         "file:///" + tmp.replace("\\", "/")],
        capture_output=True, text=True, timeout=180,
        encoding="utf-8", errors="replace")

    m = re.search(r'<pre id="results">(.*?)</pre>', proc.stdout or "", re.S)
    if not m:
        print("NO RESULTS BLOCK - the page did not run.")
        print("browser stderr tail:\n%s" % (proc.stderr or "")[-2000:])
        return 1
    text = html.unescape(m.group(1))
    if not quiet:
        print(text)
    return 0 if re.search(r"FAIL 0$", text.strip()) else 1


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    with open(sys.argv[1], encoding="utf-8") as fh:
        sys.exit(run(fh.read(), sys.argv[2] if len(sys.argv) > 2 else None))
