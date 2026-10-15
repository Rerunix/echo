#!/usr/bin/env python3
"""
ECHO MCP server.

This turns ECHO into a "plug" that any MCP client can use - Claude Desktop,
Claude Code, or any assistant that speaks the Model Context Protocol. The client
sees ECHO's powers as tools it can call:

    echo_capture   - run a target Python file, record the run, report pass/fail
    echo_diagnose  - find the first wrong step in the recorded run
    echo_autofix   - search for the smallest real fix and prove it by re-running
    echo_report    - write autopsy.html and return where it is
    echo_demo      - do all of the above in one call

It speaks MCP over stdio, which is what desktop MCP clients expect.

Run it directly to see it start (it will wait for a client on stdin):

    python3 echo_mcp_server.py
"""

import json
import os
import re
import subprocess
import sys

from mcp.server.mcpserver import MCPServer

BASE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_TARGET = os.path.join(BASE, "task.py")
TRACE = os.path.join(BASE, "trace.jsonl")
REPORT = os.path.join(BASE, "autopsy.html")
EXPECTED = 8
OPS = ["+", "-", "*", "/"]


# ---------------------------------------------------------------- core logic

def run_target(path):
    """Really run a Python file and return its printed output."""
    r = subprocess.run([sys.executable, path], capture_output=True, text=True)
    return r.stdout


def last_number(lines):
    if not lines:
        return None
    nums = re.findall(r"-?\d+", lines[-1])
    return int(nums[-1]) if nums else None


def capture(target, expected):
    out = run_target(target)
    lines = [l for l in out.strip().splitlines() if l.strip()]
    steps = [{"n": i + 1, "line": l} for i, l in enumerate(lines)]
    with open(TRACE, "w") as f:
        for s in steps:
            f.write(json.dumps(s) + "\n")
    val = last_number(lines)
    return steps, val


def load_trace():
    if not os.path.exists(TRACE):
        return None
    with open(TRACE) as f:
        return [json.loads(l) for l in f if l.strip()]


def diagnose(steps, expected):
    for s in steps:
        if s["n"] == 1:
            continue
        nums = re.findall(r"-?\d+", s["line"])
        if nums and int(nums[-1]) != expected:
            return s
    return None


def candidates(src):
    out = []
    for i, line in enumerate(src.splitlines()):
        if "=" not in line or "print" in line:
            continue
        for m in re.finditer(r"([A-Za-z0-9_)\]]+)\s*([+\-*/])\s*([A-Za-z0-9_(])", line):
            op = m.group(2)
            s, e = m.span(2)
            for new in OPS:
                if new != op:
                    out.append((i, line[:s] + new + line[e:]))
    return out


def find_fix(target, expected):
    src = open(target).read()
    lines = src.splitlines()
    tries = []
    for i, newline in candidates(src):
        test = lines[:]
        test[i] = newline
        tmp = os.path.join(BASE, "_try.py")
        with open(tmp, "w") as f:
            f.write("\n".join(test) + "\n")
        val = last_number([l for l in run_target(tmp).strip().splitlines() if l.strip()])
        tries.append((i + 1, lines[i].strip(), newline.strip(), val == expected))
        os.remove(tmp)
        if val == expected:
            return {"line": i + 1, "before": lines[i].strip(), "after": newline.strip(), "tries": tries}
    return {"line": None, "before": None, "after": None, "tries": tries}


def prove_fix(target, fix, expected):
    if not fix["line"]:
        return None
    lines = open(target).read().splitlines()
    lines[fix["line"] - 1] = fix["after"]
    tmp = os.path.join(BASE, "_fixed.py")
    with open(tmp, "w") as f:
        f.write("\n".join(lines) + "\n")
    val = last_number([l for l in run_target(tmp).strip().splitlines() if l.strip()])
    os.remove(tmp)
    return val


def write_report(steps, infection, fix, fixed_val, expected):
    bad = last_number([s["line"] for s in steps])
    rows = "\n".join(
        '      <tr class="%s"><td>%d</td><td class="mono">%s</td></tr>'
        % ("bad" if infection and s["n"] == infection["n"] else "", s["n"], s["line"])
        for s in steps)
    tries = "\n".join(
        '      <tr class="%s"><td>%d</td><td class="mono">%s</td><td class="mono">%s</td><td>%s</td></tr>'
        % ("good" if ok else "", ln, b, a, "PASS" if ok else "fail")
        for (ln, b, a, ok) in fix["tries"])
    inf_n = infection["n"] if infection else "-"
    html = """<!DOCTYPE html><html lang="en"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ECHO - Autopsy Report</title><style>
:root{--bg:#f6f8fb;--card:#fff;--line:#e2e8f0;--ink:#0f172a;--dim:#64748b;--red:#b91c1c;--redbg:#fef2f2;--green:#047857;--greenbg:#ecfdf5;--blue:#1d4ed8}
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:'Segoe UI',system-ui,sans-serif;background:var(--bg);color:var(--ink);padding:40px 20px;line-height:1.6}
.wrap{max-width:820px;margin:0 auto}
.eyebrow{font-family:ui-monospace,Consolas,monospace;font-size:12px;letter-spacing:2px;text-transform:uppercase;color:var(--blue);font-weight:600}
h1{font-size:32px;letter-spacing:-0.5px;margin:8px 0 6px}.sub{color:var(--dim);margin-bottom:8px}
.verdict{display:inline-block;font-family:ui-monospace,Consolas,monospace;font-size:13px;font-weight:700;padding:5px 12px;border-radius:6px;background:var(--redbg);color:var(--red);border:1px solid #fecaca;margin-bottom:28px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:22px 24px;margin-bottom:20px}
.card h2{font-size:15px;text-transform:uppercase;letter-spacing:1px;color:var(--dim);margin-bottom:14px;font-weight:600}
table{width:100%%;border-collapse:collapse;font-size:14px}
th{text-align:left;font-size:11px;text-transform:uppercase;letter-spacing:1px;color:var(--dim);padding:8px 10px;border-bottom:2px solid var(--line)}
td{padding:9px 10px;border-bottom:1px solid var(--line);vertical-align:top}
tr:last-child td{border-bottom:none}.mono{font-family:ui-monospace,Consolas,monospace}
tr.bad{background:var(--redbg)}tr.bad td{color:var(--red);font-weight:600}
tr.good{background:var(--greenbg)}tr.good td{color:var(--green);font-weight:600}
.point b{color:var(--red)}.fix b{color:var(--green)}.note{font-size:13px;color:var(--dim)}
footer{text-align:center;color:var(--dim);font-size:12px;margin-top:30px;font-family:ui-monospace,Consolas,monospace}
</style></head><body><div class="wrap">
<div class="eyebrow">ECHO - Autopsy Report</div>
<h1>Program: add two numbers</h1>
<div class="sub">Real run. Correct answer should be __EXP__.</div>
<div class="verdict">RESULT: FAILED &mdash; answered __BAD__, should be __EXP__</div>
<div class="card"><h2>What actually ran</h2><table><tr><th>Step</th><th>Line</th></tr>
__STEPS__
</table></div>
<div class="card"><h2>Infection point</h2>
<p class="point">First wrong step: <b>step __INFN__</b>.</p></div>
<div class="card"><h2>The fix, found and proven</h2>
<p class="fix">ECHO tried small real edits and kept the smallest that worked:</p>
<table style="margin-top:12px"><tr><th>Line</th><th>Before</th><th>After</th><th>Result</th></tr>
__TRIES__
</table>
<p class="note" style="margin-top:12px">Applying it for real gives __FIXEDVAL__ (expected __EXP__).</p></div>
<p class="note">Generated by the ECHO MCP server. Real execution, real fix search.</p>
<footer>ECHO &middot; MCP &middot; open this file in any browser</footer></div></body></html>"""
    html = (html.replace("__BAD__", str(bad)).replace("__EXP__", str(expected))
                .replace("__STEPS__", rows).replace("__INFN__", str(inf_n))
                .replace("__TRIES__", tries).replace("__FIXEDVAL__", str(fixed_val)))
    with open(REPORT, "w") as f:
        f.write(html)


# ---------------------------------------------------------------- MCP server

server = MCPServer(
    name="echo",
    title="ECHO - agent debugger",
    instructions=("ECHO records a program run, finds the first step that went wrong, "
                  "searches for the smallest real fix, and proves it by re-running. "
                  "Use echo_demo to do everything at once."),
    version="0.1.0",
)


@server.tool(description="Run a target Python file, record every step, and report whether it passed.")
def echo_capture(target_path: str = "", expected: int = EXPECTED) -> str:
    target = target_path or DEFAULT_TARGET
    steps, val = capture(target, expected)
    lines = ["Ran %s and recorded %d steps:" % (os.path.basename(target), len(steps))]
    lines += ["  step %d: %s" % (s["n"], s["line"]) for s in steps]
    lines += ["", "Final answer: %s   Expected: %s" % (val, expected),
              "PASSED" if val == expected else "FAILED"]
    return "\n".join(lines)


@server.tool(description="Find the first wrong step in the last recorded run.")
def echo_diagnose(expected: int = EXPECTED) -> str:
    steps = load_trace()
    if steps is None:
        return "No run recorded yet. Call echo_capture first."
    infection = diagnose(steps, expected)
    lines = []
    for s in steps:
        if s["n"] == 1:
            lines.append("  step %d: %s   [input]" % (s["n"], s["line"]))
        else:
            nums = re.findall(r"-?\d+", s["line"])
            ok = nums and int(nums[-1]) == expected
            lines.append("  step %d: %s   [%s]" % (s["n"], s["line"], "ok" if ok else "WRONG"))
    if infection:
        lines += ["", "Infection point: step %d" % infection["n"]]
    return "\n".join(lines)


@server.tool(description="Search for the smallest real fix and prove it by re-running the target.")
def echo_autofix(target_path: str = "", expected: int = EXPECTED) -> str:
    target = target_path or DEFAULT_TARGET
    fix = find_fix(target, expected)
    lines = ["Searching for the smallest real fix..."]
    lines += ["  try: line %d  '%s' -> '%s'  [%s]" % (ln, b, a, "PASS" if ok else "fail")
              for (ln, b, a, ok) in fix["tries"]]
    if fix["line"]:
        val = prove_fix(target, fix, expected)
        lines += ["", "Smallest fix: line %d" % fix["line"],
                  "  before: %s" % fix["before"], "  after : %s" % fix["after"],
                  "Proved by re-running: answer %s (expected %s) -> %s"
                  % (val, expected, "PASS" if val == expected else "FAIL")]
    else:
        lines.append("No single-line fix found.")
    return "\n".join(lines)


@server.tool(description="Write the autopsy.html report and return its path.")
def echo_report(expected: int = EXPECTED) -> str:
    steps = load_trace()
    if steps is None:
        return "No run recorded yet. Call echo_capture first."
    infection = diagnose(steps, expected)
    fix = find_fix(DEFAULT_TARGET, expected)
    val = prove_fix(DEFAULT_TARGET, fix, expected)
    write_report(steps, infection, fix, val, expected)
    return "Report written to: %s\nOpen it in any browser." % REPORT


@server.tool(description="Do everything at once: capture, diagnose, autofix, and write the report.")
def echo_demo(target_path: str = "", expected: int = EXPECTED) -> str:
    parts = [echo_capture(target_path, expected), "",
             echo_diagnose(expected), "",
             echo_autofix(target_path, expected), "",
             echo_report(expected)]
    return "\n".join(parts)


if __name__ == "__main__":
    server.run("stdio")
