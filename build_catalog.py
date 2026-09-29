#!/usr/bin/env python3
"""Build the website's data from the released results.

Reads, from sibling checkouts in the workspace:
  bt-eval-harness/generated_ral_resubmit_final/   released trees and results
  bt-eval-harness/task_suites/task_spec/          task prompts and success conditions
  pyrobosim/.../mcp/data/, panther-mcp-server/    the contracts the agents were served
  agentic-bt-gen-paper/tables/                    the paper's tables (shown verbatim)
  docs/data/live/                                 replays recorded by
                                                  bt-eval-harness/executors/pyrobosim_live.py

Writes docs/data/catalog.json (everything the page needs up front) and one
docs/data/batches/<cell>.json per cell, loaded when the explorer opens it.
Only run01 of each simulation cell is published as trees; per-task success
over all ten runs is included as a count.

Run with the Python environment that has pyrobosim installed (the world
vocabulary is built by the simulator's own code):
  python build_catalog.py
"""
from __future__ import annotations

import json
import os
import re
import statistics
import sys
import xml.etree.ElementTree as ET
from html import escape
from pathlib import Path
from typing import Any

import yaml

APP_ROOT = Path(__file__).resolve().parent
WORKSPACE = APP_ROOT.parent
HARNESS = WORKSPACE / "bt-eval-harness"
RELEASE = HARNESS / "generated_ral_resubmit_final"
SUITE_DIR = HARNESS / "task_suites" / "task_spec"
SIM_MCP_DATA = WORKSPACE / "pyrobosim" / "pyrobosim" / "pyrobosim" / "mcp" / "data"
PANTHER_DATA = WORKSPACE / "panther-mcp-server" / "panther_mcp" / "data"
PAPER_TABLES = WORKSPACE / "agentic-bt-gen-paper" / "tables"
OUT = APP_ROOT / "docs" / "data"
LIVE = OUT / "live"
HIGHLIGHTS = APP_ROOT / "tools" / "highlights.json"

MAX_SVG_NODES = 300  # larger trees (LLM-OBTEA under an incomplete prior) are shown as JSON only

MODELS = {"sonnet": "Sonnet 5", "gemma": "Gemma4:31b"}
METHODS = {
    "obtea": {"label": "LLM-OBTEA", "symbol": "LLM-OBTEA", "long": "LLM-OBTEA baseline"},
    "b1": {"label": "Contract without rootstocks", "symbol": "𝒞∖ℛ", "long": "Contract without rootstocks (𝒞∖ℛ)"},
    "mcore": {"label": "Full contract", "symbol": "𝒞", "long": "Full contract (𝒞)"},
}
SUITES = {
    "core60": {"label": "Core60", "file": "tasks_pyrobosim_core60.yaml", "tasks": 60,
               "blurb": "60 tasks, 12 of each of five archetypes."},
    "lang50": {"label": "Lang50", "file": "tasks_pyrobosim_language50.yaml", "tasks": 50,
               "blurb": "50 language variations of Core60 tasks."},
    "hard15": {"label": "Hard15", "file": "tasks_pyrobosim_hard15.yaml", "tasks": 15,
               "blurb": "15 structurally deeper tasks that no rootstock was written for."},
    "prior30": {"label": "Prior30", "file": "tasks_pyrobosim_prior30.yaml", "tasks": 30,
                "blurb": "30 tasks under a correct, stale or incomplete symbolic prior."},
    "panther": {"label": "Panther 14", "file": None, "tasks": 14,
                "blurb": "14 tasks on the physical Husarion Panther."},
}
SUITE_ORDER = ["core60", "lang50", "hard15", "prior30", "panther"]
METHOD_ORDER = ["obtea", "b1", "mcore"]
ARCHETYPES = {
    "sequential_pick": "Sequential pick", "selector_search": "Selector search",
    "pick_and_place": "Pick-and-place", "search_and_place": "Search-and-place",
    "pick_and_return": "Pick-and-return",
    "multi_object_sequential": "Multi-object sequential", "nested_search": "Nested search",
    "conditional_place": "Conditional place", "container_handling": "Container handling",
    "ordered_constraint": "Ordered constraint", "multi_phase": "Multi-phase",
    "retry_recovery": "Retry recovery", "negation_constraint": "Negation constraint",
    "stale_prior": "Stale prior", "incomplete_prior": "Incomplete prior", "control": "Correct prior",
}
VARIATIONS = {
    "paraphrase": "Paraphrase", "lexical_substitution": "Lexical substitution",
    "constraint_wording": "Constraint wording", "clause_reordering": "Clause reordering",
}
# Table II of the paper: every failed task-run in exactly one category.
CATEGORY = {
    "never_valid": "Never valid",
    "control_flow_ordering": "Runtime failure",
    "runtime_failure": "Runtime failure",
    "unmet_precondition": "Runtime failure",
    "bt_construction": "Goal mismatch",
    "evaluator_mismatch": "Goal mismatch",
}
CAUSE_NOTE = {
    "never_valid": "No submission passed validation, so no tree was executed.",
    "control_flow_ordering": "Failed first at an open or close action.",
    "runtime_failure": "A node failed during execution, or the tree ran out of time.",
    "unmet_precondition": "Failed first at a condition node.",
    "bt_construction": "The tree finished, but the end state does not meet the task's goal.",
    "evaluator_mismatch": "The tree finished, but the end state does not meet the task's goal.",
}
PANTHER_CATEGORY = {1: "Nav", 2: "Nav", 3: "Nav", 4: "React", 5: "React", 6: "React", 7: "React",
                    8: "Track", 9: "Track", 10: "Track", 11: "Multi", 12: "Multi", 13: "Multi", 14: "Multi"}

# Double-blind review: identifying terms (the hardware lab's name appears in Panther
# prompts, location names and file names) are replaced, visibly, everywhere they are
# published. The terms themselves are kept out of this file, in tools/redact.local
# (one per line, git-ignored).
REDACT_FILE = APP_ROOT / "tools" / "redact.local"
REDACTED = "[lab]"
HARDWARE_TASKS = WORKSPACE / "agentic-bt-gen-paper" / "hardware_demos.txt"


def _redact_pattern() -> re.Pattern[str] | None:
    if not REDACT_FILE.exists():
        print(f"warning: {REDACT_FILE} not found; nothing is redacted", file=sys.stderr)
        return None
    terms = [t.strip() for t in REDACT_FILE.read_text(encoding="utf-8").splitlines() if t.strip()]
    return re.compile("|".join(re.escape(t) for t in terms), re.IGNORECASE) if terms else None


REDACT = _redact_pattern()


def redact(text: str) -> str:
    return REDACT.sub(REDACTED, text) if REDACT else text


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


# ─── Tree JSON helpers ───────────────────────────────────────────────────────

def field(node: dict[str, Any], key: str) -> Any:
    """A node key; some Gemma trees nest keys under `fields`."""
    if key in node:
        return node[key]
    inner = node.get("fields")
    return inner.get(key) if isinstance(inner, dict) else None


def json_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    """Children in the order PyTrees builds them (a decorator's `child` is its only child)."""
    kind = node.get("type")
    if kind == "decorator":
        child = node.get("child")
        return [child] if isinstance(child, dict) else []
    if kind in ("sequence", "selector", "parallel"):
        return [c for c in node.get("children", []) if isinstance(c, dict)]
    return []


def count_nodes(node: dict[str, Any], kids=json_children) -> int:
    return 1 + sum(count_nodes(c, kids) for c in kids(node))


def preorder_names(node: dict[str, Any], kids=json_children) -> list[str]:
    out = [str(field(node, "name") or field(node, "action") or node.get("type") or "")]
    for c in kids(node):
        out.extend(preorder_names(c, kids))
    return out


def preorder_depths(node: dict[str, Any], depth: int = 0, kids=json_children) -> list[int]:
    out = [depth]
    for c in kids(node):
        out.extend(preorder_depths(c, depth + 1, kids))
    return out


# ─── SVG rendering ───────────────────────────────────────────────────────────
# Each node is a <g class="bt-node" data-i="N"> where N is its pre-order index
# in the tree JSON, which is also its index in a replay trace. The page colours
# nodes by adding classes to these groups.

PALETTE = {
    "selector": ("hex", "#69e0eb", "#197c85"),
    "sequence": ("rect", "#ffd24f", "#9a7400"),
    "parallel": ("rect", "#ffc38a", "#a85a12"),
    "decorator": ("diamond", "#e6d4f7", "#7b4bb0"),
    "condition": ("ellipse", "#eef0f4", "#717784"),
    "action": ("ellipse", "#dfe5ef", "#56627a"),
}


def short(value: Any, n: int = 22) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= n else text[: n - 1] + "…"


def sim_node_view(node: dict[str, Any]) -> tuple[str, str, str]:
    """(kind, title, detail) for a PyRoboSim tree-JSON node."""
    kind = str(node.get("type") or "action")
    name = field(node, "name")
    if kind in ("sequence", "selector", "parallel"):
        return kind, kind.capitalize(), short(name) if name else ""
    if kind == "decorator":
        return kind, str(field(node, "decorator") or "decorator").capitalize(), short(name) if name else ""
    if kind == "condition":
        key, op, val = field(node, "key"), field(node, "operator"), field(node, "value")
        detail = f"{key} {op}" + (f" {short(val, 14)}" if val is not None and op != "truthy" else "")
        return kind, short(name or "condition", 24), short(detail, 30)
    action = str(field(node, "action") or name or "action")
    params = field(node, "params") or {}
    detail = ""
    if isinstance(params, dict) and params:
        value = next(iter(params.values()))
        if isinstance(value, dict):
            value = value.get("key") or value.get("literal") or "…"
        detail = short(value, 22)
    return "action", action, detail


BTCPP_CONTROL = {"Sequence", "SequenceWithMemory", "ReactiveSequence", "SequenceStar"}
BTCPP_FALLBACK = {"Fallback", "ReactiveFallback", "FallbackStar"}
BTCPP_DECORATOR = {"KeepRunningUntilFailure", "Repeat", "RetryUntilSuccessful", "Inverter",
                   "ForceSuccess", "ForceFailure", "RunOnce"}
BTCPP_CONDITION = {"CheckDetection"}


def xml_node_view(node: dict[str, Any]) -> tuple[str, str, str]:
    tag = node["tag"]
    attrs = node.get("attrs") or {}
    kind = ("sequence" if tag in BTCPP_CONTROL else "selector" if tag in BTCPP_FALLBACK
            else "parallel" if tag.startswith("Parallel") else "decorator" if tag in BTCPP_DECORATOR
            else "condition" if tag in BTCPP_CONDITION else "action")
    detail = ", ".join(f"{v}" for k, v in attrs.items() if k != "name")
    return kind, tag, short(detail, 26)


def xml_children(node: dict[str, Any]) -> list[dict[str, Any]]:
    return node.get("children", [])


def text_width(text: str, size: float) -> float:
    return len(text) * size * 0.58


def render_svg(root: dict[str, Any], view=sim_node_view, kids=json_children) -> str:
    level_gap, sibling_gap, margin = 72.0, 10.0, 12.0
    counter = 0

    def build(node: dict[str, Any], depth: int) -> dict[str, Any]:
        nonlocal counter
        kind, title, detail = view(node)
        item = {"i": counter, "kind": kind, "title": title, "detail": detail, "depth": depth}
        counter += 1
        item["children"] = [build(c, depth + 1) for c in kids(node)]
        w = max(text_width(title, 11.5), text_width(detail, 10)) + 18
        item["w"] = max(64.0, min(190.0, w)) + (18 if kind in ("hex", "selector", "decorator") else 0)
        item["h"] = 40.0 if detail else 30.0
        return item

    tree = build(root, 0)

    def span(item: dict[str, Any]) -> float:
        if not item["children"]:
            item["span"] = item["w"]
        else:
            inner = sum(span(c) for c in item["children"]) + sibling_gap * (len(item["children"]) - 1)
            item["inner"] = inner
            item["span"] = max(item["w"], inner)
        return item["span"]

    def place(item: dict[str, Any], left: float) -> None:
        item["x"] = left + item["span"] / 2
        item["y"] = margin + 20 + item["depth"] * level_gap
        if item["children"]:
            x = left + (item["span"] - item["inner"]) / 2
            for c in item["children"]:
                place(c, x)
                x += c["span"] + sibling_gap

    def depth(item: dict[str, Any]) -> int:
        return max([item["depth"]] + [depth(c) for c in item["children"]])

    span(tree)
    place(tree, margin)
    width = tree["span"] + 2 * margin
    height = 2 * margin + 40 + depth(tree) * level_gap

    edges: list[str] = []
    nodes: list[str] = []

    def shape(kind: str, x: float, y: float, w: float, h: float) -> str:
        form, fill, stroke = PALETTE.get(kind, PALETTE["action"])
        dash = ' stroke-dasharray="4 3"' if kind == "condition" else ""
        common = f'fill="{fill}" stroke="{stroke}" stroke-width="1.3"{dash}'
        if form == "rect":
            return f'<rect class="bt-shape" x="{x - w/2:.1f}" y="{y - h/2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="7" {common}/>'
        if form == "hex":
            k = 12.0
            pts = [(x - w/2 + k, y - h/2), (x + w/2 - k, y - h/2), (x + w/2, y), (x + w/2 - k, y + h/2),
                   (x - w/2 + k, y + h/2), (x - w/2, y)]
            return f'<polygon class="bt-shape" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" {common}/>'
        if form == "diamond":
            k = 10.0
            pts = [(x - w/2 + k, y - h/2), (x + w/2 - k, y - h/2), (x + w/2, y), (x + w/2 - k, y + h/2),
                   (x - w/2 + k, y + h/2), (x - w/2, y)]
            return f'<polygon class="bt-shape" points="{" ".join(f"{a:.1f},{b:.1f}" for a, b in pts)}" {common} stroke-linejoin="round"/>'
        return f'<ellipse class="bt-shape" cx="{x:.1f}" cy="{y:.1f}" rx="{w/2:.1f}" ry="{h/2:.1f}" {common}/>'

    def walk(item: dict[str, Any]) -> None:
        for c in item["children"]:
            edges.append(f'<line x1="{item["x"]:.1f}" y1="{item["y"] + item["h"]/2:.1f}" '
                         f'x2="{c["x"]:.1f}" y2="{c["y"] - c["h"]/2:.1f}" data-to="{c["i"]}"/>')
        x, y = item["x"], item["y"]
        mono = item["kind"] == "action"
        family = "ui-monospace, SFMono-Regular, Menlo, monospace" if mono else "inherit"
        title_y = y - 5 if item["detail"] else y + 4
        parts = [shape(item["kind"], x, y, item["w"], item["h"]),
                 f'<text x="{x:.1f}" y="{title_y:.1f}" class="bt-t" font-family="{family}">{escape(item["title"])}</text>']
        if item["detail"]:
            parts.append(f'<text x="{x:.1f}" y="{y + 11:.1f}" class="bt-d">{escape(item["detail"])}</text>')
        nodes.append(f'<g class="bt-node bt-{item["kind"]}" data-i="{item["i"]}">{"".join(parts)}</g>')
        for c in item["children"]:
            walk(c)

    walk(tree)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" class="bt-svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'width="{width:.0f}" height="{height:.0f}" role="img" aria-label="Behavior tree, {counter} nodes">'
        f'<g class="bt-edges" stroke="#8a8f99" stroke-width="1.2">{"".join(edges)}</g>{"".join(nodes)}</svg>'
    )


# ─── BT.CPP XML (Panther) ────────────────────────────────────────────────────

def parse_xml_tree(xml_text: str) -> dict[str, Any] | None:
    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    bt = root.find("BehaviorTree") if root.tag != "BehaviorTree" else root
    if bt is None:
        return None
    first = next((c for c in bt if isinstance(c.tag, str)), None)

    def conv(el: ET.Element) -> dict[str, Any]:
        return {"tag": el.tag, "attrs": dict(el.attrib), "children": [conv(c) for c in el if isinstance(c.tag, str)]}

    return conv(first) if first is not None else None


def xml_snippets(prose: str) -> list[str]:
    """Top-level XML elements quoted inside a rootstock's prose."""
    out, depth, start = [], 0, None
    for m in re.finditer(r"<(/?)([A-Za-z][A-Za-z0-9_]*)([^>]*?)(/?)>", prose):
        closing, selfclose = m.group(1) == "/", m.group(4) == "/"
        if not closing and depth == 0:
            start = m.start()
        if closing:
            depth -= 1
        elif not selfclose:
            depth += 1
        if depth == 0 and start is not None:
            out.append(prose[start:m.end()])
            start = None
    return out


# ─── Paper tables ────────────────────────────────────────────────────────────

def tone_of(cell: str) -> str | None:
    for tone in ("green", "orange", "red"):
        if f"\\score{tone}" in cell:
            return tone
    return None


def clean_tex(cell: str) -> str:
    s = cell
    for macro, text in (("\\OBTEA{}", "LLM-OBTEA"), ("\\Bone{}", "𝒞∖ℛ"), ("\\MCore{}", "𝒞"),
                        ("\\OBTEA", "LLM-OBTEA"), ("\\Bone", "𝒞∖ℛ"), ("\\MCore", "𝒞"),
                        ("\\na", "n/a"), ("\\%", "%"), ("\\pm", "±"), ("\\times", "×"), ("\\quad", ""), ("\\,", "")):
        s = s.replace(macro, text)
    s = re.sub(r"\\multirow\{\d+\}\{\*\}", "", s)
    s = re.sub(r"\\shortstack\[l\]", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    s = s.replace("{", "").replace("}", "").replace("$", "").replace("~", " ")
    return re.sub(r"\s+", " ", s).strip()


def table_rows(path: Path) -> list[str]:
    """Body rows of a tabular: lines with '&', comments removed."""
    lines = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = re.sub(r"(?<!\\)%.*$", "", raw)
        if line.strip():
            lines.append(line)
    body = "\n".join(lines)
    body = body[body.index("\\begin{tabular}"): body.index("\\end{tabular}")]
    rows = [r.strip() for r in body.split("\\\\")]
    return [r.replace("\\hline", "").replace("\\cline{2-4}", "").strip() for r in rows]


def parse_table1(path: Path) -> list[dict[str, Any]]:
    sections: list[dict[str, Any]] = []
    for row in table_rows(path):
        m = re.search(r"\\multicolumn\{7\}\{@\{\}l\}\{\\textbf\{(\w+)\}", row)
        if m:
            sub = re.search(r"\\scriptsize (.*)\}\}\s*$", row)
            sections.append({"suite": m.group(1), "note": clean_tex(sub.group(1)) if sub else "", "rows": []})
            continue
        if not sections or "&" not in row:
            continue
        cells = [c.strip() for c in row.split("&")]
        label = cells[0]
        sections[-1]["rows"].append({
            "label": clean_tex(label),
            "level": 1 if "\\quad" in label else 0,
            "cells": [{"text": clean_tex(c), "tone": tone_of(c)} for c in cells[1:]],
        })
    return sections


def parse_table2(path: Path) -> list[dict[str, Any]]:
    out = []
    for row in table_rows(path):
        cells = [c.strip() for c in row.split("&")]
        if len(cells) < 9 or "textbf" in cells[0] or not cells[0]:
            continue
        vals = [clean_tex(c) for c in cells]
        vals = [v for v in vals if v != ""]
        out.append({"model": vals[0], "method": vals[1], "never_valid": vals[2], "runtime": vals[3],
                    "goal_mismatch": vals[4], "failure_rate": vals[5]})
    return out


def parse_table3(path: Path) -> list[dict[str, Any]]:
    out, prior = [], None
    for row in table_rows(path):
        m = re.search(r"\\textbf\{(\w+)\}", row)
        if m and "multirow" in row:
            prior = m.group(1)
        cells = [c.strip() for c in row.split("&")]
        if len(cells) < 6 or "Method" in row or prior is None:
            continue
        out.append({"prior": prior, "method": clean_tex(cells[1]),
                    "sonnet": {"text": clean_tex(cells[2]), "tone": tone_of(cells[2])}, "sonnet_nodes": clean_tex(cells[3]),
                    "gemma": {"text": clean_tex(cells[4]), "tone": tone_of(cells[4])}, "gemma_nodes": clean_tex(cells[5])})
    return out


def parse_hardware(path: Path) -> list[dict[str, Any]]:
    out, method = [], None
    for row in table_rows(path):
        if "multirow" in row:
            method = clean_tex(re.search(r"\\multirow\{2\}\{\*\}\{(.*?\})\}", row).group(1))
        cells = [clean_tex(c) for c in row.split("&")]
        if len(cells) == 10 and cells[1] in ("Sonnet", "Gemma"):
            out.append({"method": method, "model": cells[1], "cells": cells[2:]})
    return out


# ─── PyRoboSim cells ─────────────────────────────────────────────────────────

def norm_prompt(text: str | None) -> str:
    return re.sub(r"\s+", " ", (text or "")).strip().lower()


def first_submissions(cell_dir: Path, tasks: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    """task id -> its submissions in log order."""
    by_prompt = {norm_prompt(t["task_prompt"]): t["id"] for t in tasks}
    out: dict[str, list[dict[str, Any]]] = {}
    path = cell_dir / "submissions.jsonl"
    if not path.exists():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        sub = json.loads(line)
        tid = sub.get("task_id") or by_prompt.get(norm_prompt(sub.get("task_prompt")))
        if tid:
            out.setdefault(tid, []).append(sub)
    return out


def pop_sd(values: list[float]) -> float:
    return statistics.pstdev(values) if len(values) > 1 else 0.0


def build_sim_cell(cell: str, suite_key: str, model: str, method: str, suite: dict[str, Any],
                   live_keys: dict[tuple[str, str], str]) -> tuple[dict[str, Any], dict[str, Any]]:
    tasks = suite["tasks"]
    runs = sorted(p.name for p in (RELEASE / cell).glob("run[0-9][0-9]"))
    per_run_rows = {run: {r["id"]: r for r in load_json(RELEASE / cell / run / "results.json")} for run in runs}
    succeeded = {t["id"]: sum(bool(per_run_rows[run].get(t["id"], {}).get("success")) for run in runs) for t in tasks}
    success_by_run = [100.0 * sum(bool(per_run_rows[run].get(t["id"], {}).get("success")) for t in tasks) / len(tasks)
                      for run in runs]
    valid_by_run = []
    for run in runs:
        v = load_json(RELEASE / cell / run / "results_summary.json").get("valid_at_1")
        if v is not None:
            valid_by_run.append(100.0 * v)

    run = "run01"
    subs = first_submissions(RELEASE / cell / run, tasks)
    records = []
    for t in tasks:
        tid = t["id"]
        row = per_run_rows[run].get(tid, {})
        cause = row.get("failure_cause") or ("never_valid" if row.get("missing_bt") else None)
        task_subs = subs.get(tid, [])
        first = task_subs[0] if task_subs else None
        bt = None
        if row.get("bt_path"):
            bt = load_json(RELEASE / row["bt_path"])
        nodes = count_nodes(bt["root"]) if bt else None
        rec = {
            "id": tid,
            "prompt": t.get("task_prompt"),
            "archetype": ARCHETYPES.get(t.get("archetype"), t.get("archetype")),
            "variation": VARIATIONS.get(t.get("lang_variation")) if t.get("lang_variation") else None,
            "prior": t.get("baseline_prior"),
            "mechanism": t.get("mechanism"),
            "success_spec": t.get("success"),
            "valid_at_1": (bool(first["valid"]) if first else None) if method != "obtea" else None,
            "submissions": len(task_subs) if method != "obtea" else None,
            "first_issues": [i.get("message") for i in (first or {}).get("issues", [])] if first and not first.get("valid") else [],
            "bt_file": row.get("bt_path"),
            "bt": bt,
            "nodes": nodes,
            "svg": render_svg(bt["root"]) if bt and nodes <= MAX_SVG_NODES else None,
            "exec_status": row.get("exec_status") if cause != "never_valid" else None,
            "goal_satisfied": row.get("goal_satisfied") if cause != "never_valid" else None,
            "success": bool(row.get("success")),
            "failure_cause": cause,
            "category": CATEGORY.get(cause) if cause else None,
            "cause_note": CAUSE_NOTE.get(cause) if cause else None,
            "failed_node": row.get("failed_node"),
            "tick_count": row.get("tick_count"),
            "runtime_ms": row.get("runtime_ms"),
            "runs_succeeded": succeeded[tid],
            "runs": len(runs),
            "live": live_keys.get((cell, tid)),
        }
        records.append(rec)
    run01_valid = [r["valid_at_1"] for r in records if r["valid_at_1"] is not None]
    batch = {
        "name": cell,
        "environment": "pyrobosim",
        "model": model,
        "method": method,
        "suite": suite_key,
        "file": f"batches/{cell}.json",
        "count": len(tasks),
        "run01": {"success": sum(r["success"] for r in records),
                  "valid_at_1": sum(run01_valid) if run01_valid else None},
        "ten_runs": {
            "runs": len(runs),
            "success_mean": round(statistics.mean(success_by_run), 1),
            "success_sd": round(pop_sd(success_by_run), 1),
            "valid_mean": round(statistics.mean(valid_by_run), 1) if valid_by_run else None,
            "valid_sd": round(pop_sd(valid_by_run), 1) if valid_by_run else None,
        },
    }
    return batch, {"name": cell, "tasks": records}


# ─── Panther cells ───────────────────────────────────────────────────────────

def build_panther_cell(cell: str, model: str, method: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """One session per task. Gemma's tasks 10 and 11 were run in two sessions on
    the same day; the later one is used, which is the one the paper's
    first-submission counts correspond to."""
    subs = [json.loads(l) for l in (RELEASE / cell / "submissions.jsonl").read_text().splitlines() if l.strip()]
    by_task: dict[int, list[dict[str, Any]]] = {}
    for s in sorted(subs, key=lambda s: s["timestamp"]):
        num = int(Path(s["generated"]).name.replace("invalid__", "")[:2])
        by_task.setdefault(num, []).append(s)
    records = []
    for num in range(1, 15):
        attempts = by_task.get(num, [])
        # split into sessions at gaps over one hour; keep the last
        sessions: list[list[dict[str, Any]]] = []
        for s in attempts:
            if sessions and _gap_hours(sessions[-1][-1]["timestamp"], s["timestamp"]) < 1.0:
                sessions[-1].append(s)
            else:
                sessions.append([s])
        session = sessions[-1] if sessions else []
        first = session[0] if session else None
        scored = next((s for s in session if s.get("valid")), None)
        xml_text = (RELEASE / scored["generated"]).read_text(encoding="utf-8") if scored else ""
        tree = parse_xml_tree(xml_text) if xml_text else None
        prompt = re.sub(r"^Task \d+:\s*", "", (first or {}).get("task_prompt", ""))
        records.append({
            "id": f"panther{num:02d}",
            "num": num,
            "prompt": redact(prompt),
            "archetype": PANTHER_CATEGORY[num],
            "valid_at_1": bool(first["valid"]) if first else None,
            "submissions": len(session),
            "earlier_sessions": len(sessions) - 1,
            "first_issues": [i.get("message") for i in first.get("issues", [])] if first and not first.get("valid") else [],
            "bt_file": redact(scored["generated"]) if scored else None,
            "xml": redact(xml_text),
            "nodes": count_nodes(tree, xml_children) if tree else None,
            "svg": redact(render_svg(tree, xml_node_view, xml_children)) if tree else None,
        })
    batch = {
        "name": cell, "environment": "panther", "model": model, "method": method, "suite": "panther",
        "file": f"batches/{cell}.json", "count": 14,
        "run01": {"valid_at_1": sum(bool(r["valid_at_1"]) for r in records), "success": None},
        "ten_runs": None,
    }
    return batch, {"name": cell, "tasks": records}


def _gap_hours(a: str, b: str) -> float:
    from datetime import datetime
    fa = datetime.fromisoformat(a.replace("Z", "+00:00"))
    fb = datetime.fromisoformat(b.replace("Z", "+00:00"))
    return abs((fb - fa).total_seconds()) / 3600.0


# ─── Contracts ───────────────────────────────────────────────────────────────

MCP_TOOLS = [
    {"served": "list_skills", "paper": "get_skill_library", "returns": "skill schemas",
     "desc": "Every robot skill with its typed parameters and the blackboard outputs it writes.", "full_only": False},
    {"served": "get_bt_format", "paper": "get_bt_operators", "returns": "BT format",
     "desc": "The tree specification: permitted node types, composites, decorators and condition operators.", "full_only": False},
    {"served": "list_rootstocks_tool", "paper": "get_rootstocks", "returns": "rootstocks",
     "desc": "Rootstock templates with their slots, when to use them, and anti-patterns. Absent under 𝒞∖ℛ.", "full_only": True},
    {"served": "list_world_entities", "paper": "get_world_vocabulary", "returns": "world vocabulary",
     "desc": "Names of rooms, locations, object spawns, object categories, objects and hallways, with no relations between them.", "full_only": False},
    {"served": "validate_bt", "paper": "validate_bt", "returns": "validation report",
     "desc": "Runs the validation gate on a draft tree without executing it. The agent may call it before submitting.", "full_only": False},
    {"served": "send_to_robot", "paper": "send_to_robot", "returns": "validation result, then execution",
     "desc": "Submits a tree. The gate checks it against the contract; a rejected tree comes back with specific errors, an accepted one is executed.", "full_only": False},
]


def sim_contract() -> dict[str, Any]:
    skills = yaml.safe_load((SIM_MCP_DATA / "skills.yaml").read_text())["skills"]
    schema = yaml.safe_load((SIM_MCP_DATA / "bt_schema.yaml").read_text())
    rootstocks = yaml.safe_load((SIM_MCP_DATA / "rootstocks.yaml").read_text())["rootstocks"]
    return {
        "skills": [{"name": s["name"], "description": s.get("description", ""),
                    "params": [{"name": k, "type": v.get("type"), "required": bool(v.get("required"))}
                               for k, v in (s.get("params") or {}).items()],
                    "outputs": s.get("outputs", [])} for s in skills],
        "format": {
            "node_types": schema["node_types"],
            "composites": {k: v for k, v in schema["composite_nodes"].items()},
            "decorators": schema["decorator_node"]["fields"]["decorator"],
            "condition_operators": schema["condition_node"]["fields"]["operator"],
            "notes": schema.get("notes", []),
        },
        "rootstocks": [{"name": r["name"], "description": r.get("description", ""),
                        "when_to_use": r.get("when_to_use", ""), "slots": r.get("slots", {}),
                        "anti_pattern": r.get("anti_pattern", ""),
                        "svg": render_svg(r["template"]["root"])} for r in rootstocks],
        "vocabulary": world_vocabulary(),
    }


def world_vocabulary() -> dict[str, list[str]]:
    """The vocabulary sim_app serves in 'vocab' mode, built by the simulator's own code."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import logging
    logging.disable(logging.CRITICAL)
    from pyrobosim.sim_app.server import load_world
    from pyrobosim.sim_app.world_entities import build_world_entities
    world, _ = load_world("roscon_2024_workshop_world.yaml")
    vocab = build_world_entities(world, mode="vocab")
    vocab.pop("mode", None)
    return vocab


def panther_header(label: str) -> list[str]:
    """A comma-separated list from the header comment of the hardware task list.
    The Panther server reads its locations from a file outside this workspace; this
    header is the list the tasks were written against."""
    text, capture = [], False
    for line in HARDWARE_TASKS.read_text(encoding="utf-8").splitlines():
        if not line.startswith("#"):
            break
        body = line.lstrip("#").strip()
        if body.startswith(label + ":"):
            capture = True
            body = body.split(":", 1)[1]
        elif capture and ":" in body:
            break
        if capture:
            text.append(body)
    return [x.strip() for x in ",".join(text).split(",") if x.strip()]


def panther_contract() -> dict[str, Any]:
    skills = yaml.safe_load((PANTHER_DATA / "skills.yaml").read_text())["skills"]
    schema = yaml.safe_load((PANTHER_DATA / "bt_schema.yaml").read_text())
    rootstocks = yaml.safe_load((PANTHER_DATA / "rootstocks.yaml").read_text())["rootstocks"]
    rs = []
    for r in rootstocks:
        snippets = xml_snippets(r.get("bt", ""))
        tree = None
        for snip in reversed(snippets):
            tree = parse_xml_tree(f"<root><BehaviorTree>{snip}</BehaviorTree></root>")
            if tree:
                break
        rs.append({"name": r["name"], "description": r.get("description", ""), "prose": redact(r.get("bt", "")),
                   "svg": render_svg(tree, xml_node_view, xml_children) if tree else None})
    return {
        "skills": [{"name": s["name"], "description": " ".join(str(s.get("description", "")).split()),
                    "params": [{"name": k, "type": (v or {}).get("type"), "required": bool((v or {}).get("required"))}
                               for k, v in (s.get("params") or {}).items()]} for s in skills],
        "operators": [{"name": k, "description": " ".join(str((v or {}).get("description", "")).split()).split(" NOTE")[0].split(" CRITICAL")[0]}
                      for k, v in schema["control_flow_nodes"].items()],
        "rootstocks": rs,
        "vocabulary": {
            "locations": [redact(x) for x in panther_header("Location vocab")],
            "detection_classes": panther_header("Detection classes"),
        },
    }


# ─── OOC10 ───────────────────────────────────────────────────────────────────
# Scored by bt-eval-harness score_ooc10.py (branch ral/ooc10) into
# <root>/_report/ooc10_scores.json. A cell that has not been run yet is shown
# as pending rather than left out, so the table keeps its four columns.

OOC10_ROOT = HARNESS / "generated_ral_resubmit" / "ooc10"
OOC10_SCORES = OOC10_ROOT / "_report" / "ooc10_scores.json"
OOC10_CELLS = [  # table column order: (scorer cell, method, model)
    ("cr_sonnet", "mcore", "sonnet"), ("cr_gemma", "mcore", "gemma"),
    ("obtea_sonnet", "obtea", "sonnet"), ("obtea_gemma", "obtea", "gemma"),
]


def ooc10_catalog() -> dict[str, Any]:
    suite = yaml.safe_load((SUITE_DIR / "tasks_pyrobosim_ooc10.yaml").read_text())["tasks"]
    tasks = [{"id": t["id"], "prompt": t["task_prompt"], "reason": t.get("ooc_reason", "")} for t in suite]
    if not OOC10_SCORES.exists():
        return {"tasks": tasks, "cells": [], "examples": {}}
    scores = load_json(OOC10_SCORES)
    summaries = scores["summaries"]

    def rate(block: dict[str, Any]) -> dict[str, Any]:
        return {"mean": block["mean"], "sd": block["sd_population"], "ci95": block["bootstrap95"]}

    cells = []
    for cell, method, model in OOC10_CELLS:
        s = summaries.get(cell)
        entry = {"cell": cell, "method": method, "model": model, "pending": s is None}
        if s:
            pos = "rejected" if method == "obtea" else "refused"
            entry.update({
                "runs": len(s["runs"]),
                "positive": pos,
                "per_task": {tid: v["counts"] for tid, v in s["per_task"].items()},
                "rate": rate(s[f"{pos}_rate_all10"]),
                "rate_wo08": rate(s[f"{pos}_rate_without_ooc08"]),
                "totals": s["label_totals"],
                "extra": s.get("obtea") or s.get("sensitivity") or {},
            })
        cells.append(entry)

    # Run 1 of each contract cell: the reply as the agent wrote it. LLM-OBTEA:
    # the goals stage 1 produced for the prompt, counted over all runs.
    examples: dict[str, dict[str, Any]] = {t["id"]: {} for t in tasks}
    goals: dict[tuple[str, str], dict[str, int]] = {}
    for u in scores["units"]:
        cell, tid = u["cell"], u["task_id"]
        if u["method"] == "cr" and u["run"] == "run01":
            examples[tid][cell] = {"label": u["label"], "sub": u.get("sub"),
                                   "text": redact(u["evidence"].get("final_text") or ""),
                                   "tools": u["evidence"].get("tool_summary", "")}
        elif u["method"] == "obtea":
            goal = " & ".join(u["attrs"].get("goal") or []) or "no goal"
            bucket = goals.setdefault((cell, tid), {})
            bucket[goal] = bucket.get(goal, 0) + 1
    for (cell, tid), counts in goals.items():
        examples[tid][cell] = {"goals": sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))}

    sources: dict[str, int] = {}
    for u in scores["units"]:
        if u["method"] == "cr" and u.get("needs_text_judgement"):
            sources[u["label_source"]] = sources.get(u["label_source"], 0) + 1
    return {"tasks": tasks, "cells": cells, "examples": examples,
            "judge": {"model": scores.get("judge_model"), "votes": scores.get("votes"),
                      "label_sources": sources}}


# ─── Main ────────────────────────────────────────────────────────────────────

def main() -> None:
    manifest = load_json(HIGHLIGHTS)
    live_keys = {}
    highlights = {}
    for h in manifest:
        trace_path = LIVE / f"{h['key']}.json"
        if not trace_path.exists():
            print(f"warning: no replay for {h['key']}", file=sys.stderr)
            continue
        trace = load_json(trace_path)
        live_keys[(h["cell"], h["task_id"])] = h["key"]
        bt = load_json(RELEASE / trace["bt_path"])
        n = count_nodes(bt["root"])
        highlights[h["key"]] = {
            "cell": h["cell"], "task_id": h["task_id"], "prompt": trace["task_prompt"],
            "nodes": n, "names": preorder_names(bt["root"]), "depths": preorder_depths(bt["root"]),
            "svg": render_svg(bt["root"]) if n <= MAX_SVG_NODES else None,
            "replay": trace["replay"], "recorded": trace["recorded"],
            "video": f"data/live/{trace['video']}", "trace": f"data/live/{h['key']}.json",
        }

    batches, suites = [], {}
    for suite_key in ["core60", "lang50", "hard15", "prior30"]:
        suite = yaml.safe_load((SUITE_DIR / SUITES[suite_key]["file"]).read_text())
        suites[suite_key] = suite
        for model in MODELS:
            for method in METHOD_ORDER:
                cells = [c for c in (f"{suite_key}_{model}_{method}", f"{suite_key}_{model}_{method}_full")
                         if (RELEASE / c).is_dir()]
                if not cells:
                    continue
                batch, detail = build_sim_cell(cells[0], suite_key, model, method, suite, live_keys)
                write_json(OUT / batch["file"], detail)
                batches.append(batch)
                print(f"{cells[0]:28s} success run01 {batch['run01']['success']}/{batch['count']}  "
                      f"10-run {batch['ten_runs']['success_mean']} ± {batch['ten_runs']['success_sd']}")
    for model in MODELS:
        for method in ["b1", "mcore"]:
            batch, detail = build_panther_cell(f"panther_{model}_{method}", model, method)
            write_json(OUT / batch["file"], detail)
            batches.append(batch)
            print(f"panther_{model}_{method:6s} valid@1 {batch['run01']['valid_at_1']}/14")

    tables = {
        "table1": parse_table1(PAPER_TABLES / "suite_results_with_archetype_breakdown.tex"),
        "table2": parse_table2(PAPER_TABLES / "failure_breakdown.tex"),
        "table3": parse_table3(PAPER_TABLES / "prior30_results.tex"),
        "hardware": parse_hardware(PAPER_TABLES / "hardware_failures.tex"),
    }
    check_table1(tables["table1"], batches)

    catalog = {
        "models": [{"id": k, "label": v} for k, v in MODELS.items()],
        "methods": [{"id": k, **METHODS[k]} for k in METHOD_ORDER],
        "suites": {k: {kk: vv for kk, vv in SUITES[k].items() if kk != "file"} for k in SUITE_ORDER},
        "batches": batches,
        "mcp_tools": MCP_TOOLS,
        "contract": {"sim": sim_contract(), "hw": panther_contract()},
        "tables": tables,
        "highlights": highlights,
        "ooc10": ooc10_catalog(),
    }
    write_json(OUT / "catalog.json", catalog)
    print(f"wrote {OUT / 'catalog.json'} ({(OUT / 'catalog.json').stat().st_size / 1e3:.0f} kB), "
          f"{len(batches)} batches, {len(highlights)} replays")


def check_table1(sections: list[dict[str, Any]], batches: list[dict[str, Any]]) -> None:
    """Every Valid@1 and Success cell of Table I against the released data."""
    col = [(m, meth) for m in MODELS for meth in METHOD_ORDER]
    by = {(b["suite"], b["model"], b["method"]): b for b in batches}
    bad = 0
    for sec in sections:
        suite = sec["suite"].lower()
        for row in sec["rows"]:
            kind = "valid" if row["label"].startswith("Valid@1") else "success" if row["label"].startswith("Success") else None
            if not kind:
                continue
            for (model, method), cell in zip(col, row["cells"]):
                b = by.get((suite, model, method))
                if b is None or cell["text"] == "n/a":
                    continue
                mean, sd = b["ten_runs"][f"{kind}_mean"], b["ten_runs"][f"{kind}_sd"]
                if cell["text"] != f"{mean:.1f} ± {sd:.1f}":
                    bad += 1
                    print(f"TABLE I MISMATCH {suite} {model} {method} {kind}: paper {cell['text']} data {mean:.1f} ± {sd:.1f}")
    print("Table I Valid@1/Success cells match the released data" if not bad else f"{bad} Table I cells differ")


if __name__ == "__main__":
    main()
    sys.stdout.flush()
    os._exit(0)  # the simulator's world starts non-daemon threads
