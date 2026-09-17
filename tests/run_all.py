"""Run every browser suite, plus the water regression diff against the committed build.

    py tests/run_all.py

The regression check re-runs suite_water_regression.js against both HEAD's copy of the tool and
the working copy and diffs the output: the cold and hot sheets must be bit-identical after any
change that is only supposed to touch gas. It is skipped (not failed) outside a git checkout.

Exit code 0 if everything passed.
"""

import os
import subprocess
import sys

import run_suite

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
TOOL = "GFB_Schematic_Drawing_Tool.html"

SUITES = ["suite_gas.js", "suite_ui.js", "suite_perriser.js"]


def read(name):
    with open(os.path.join(HERE, name), encoding="utf-8") as fh:
        return fh.read()


def capture(suite, tool):
    """Run a suite and return its printed body, for diffing rather than pass/fail."""
    import contextlib
    import io
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        run_suite.run(suite, tool)
    return buf.getvalue()


def water_regression():
    print("=== water regression (cold + hot must be unchanged vs HEAD) ===")
    head_copy = os.path.join(HERE, "_tool_HEAD.html")
    try:
        blob = subprocess.run(["git", "show", "HEAD:" + TOOL], cwd=REPO,
                              capture_output=True, timeout=60)
        if blob.returncode != 0 or not blob.stdout:
            print("  SKIPPED - not a git checkout, or the tool is not committed yet")
            return 0
        with open(head_copy, "wb") as fh:
            fh.write(blob.stdout)
        suite = read("suite_water_regression.js")
        before = capture(suite, head_copy)
        after = capture(suite, os.path.join(REPO, TOOL))
        if before == after:
            print("  OK - identical across %d lines" % len(after.splitlines()))
            return 0
        print("  FAIL - the water sheets changed:")
        import difflib
        for line in list(difflib.unified_diff(before.splitlines(), after.splitlines(),
                                              "HEAD", "working", lineterm=""))[:40]:
            print("    %s" % line)
        return 1
    finally:
        if os.path.exists(head_copy):
            os.remove(head_copy)


def main():
    failures = 0
    for name in SUITES:
        print("=== %s ===" % name)
        failures += run_suite.run(read(name))
        print()
    failures += water_regression()
    print()
    if failures:
        print("%d suite(s) FAILED" % failures)
        return 1
    print("All suites passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
