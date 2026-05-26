#!/usr/bin/env python3
from __future__ import annotations

import json
import re
from html import escape
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    yaml = None

import xml.etree.ElementTree as ET

APP_ROOT = Path(__file__).resolve().parent
DATA_ROOT = APP_ROOT / "data_snapshots"
GENERATED_ROOT = DATA_ROOT / "generated"
TASK_SPEC_ROOT = DATA_ROOT / "task_specs"
OUTPUT_PATH = APP_ROOT / "docs" / "data" / "catalog.json"
PAPER_ROOT = APP_ROOT.parent / "agentic-bt-gen-paper"
PAPER_TABLE_ROOT = PAPER_ROOT / "tables"
ROOTSTOCKS_PATH = APP_ROOT.parent / "pyrobosim" / "pyrobosim" / "pyrobosim" / "mcp" / "data" / "rootstocks.yaml"
PANTHER_ROOTSTOCKS_PATH = APP_ROOT.parent / "panther-mcp-server" / "panther_mcp" / "data" / "rootstocks.yaml"

METHOD_ORDER = {"M-Core": 0, "B1": 1, "B0": 2, "Other": 3}

# BT.CPP control-flow node tags
_BTCPP_CONTROL_TAGS = {
    "Sequence", "ReactiveSequence", "SequenceStar",
    "Fallback", "ReactiveFallback", "FallbackStar",
    "Parallel", "ParallelAll",
    "KeepRunningUntilFailure", "ForceSuccess", "ForceFailure",
    "Inverter", "RetryUntilSuccessful", "RepeatNode",
}
_BTCPP_CONDITION_TAGS = {"Condition"}
# anything else is treated as an action leaf
SUITE_LABELS = {
    "core60": "Core 60",
    "language50": "Language 50",
}
ARCHETYPE_LABELS = {
    "sequential_pick": "Sequential Pick",
    "selector_search": "Selector Search",
    "pick_and_place": "Pick and Place",
    "search_and_place": "Search and Place",
    "pick_and_return": "Pick and Return",
}

PAPER_TABLE_SPECS = [
    {
        "key": "main_comparison",
        "path": PAPER_TABLE_ROOT / "main_comparison.tex",
        "title": "Main PyRoboSim Comparison",
        "columns": ["Method", "Suite", "Valid", "Grounded", "Params", "StructComp", "Success"],
    },
    {
        "key": "pyrobosim_archetypes",
        "path": PAPER_TABLE_ROOT / "pyrobosim_archetypes.tex",
        "title": "PyRoboSim Success Rates by Archetype",
        "columns": ["Archetype", "Example prompt", "B0", "B1", "M-Core"],
    },
    {
        "key": "language_breakdown",
        "path": PAPER_TABLE_ROOT / "language_breakdown.tex",
        "title": "Language Robustness Breakdown",
        "columns": ["Variation type", "Example prompt", "B0", "B1", "M-Core"],
    },
    {
        "key": "failure_breakdown",
        "path": PAPER_TABLE_ROOT / "failure_breakdown.tex",
        "title": "Failure-Cause Breakdown",
        "columns": ["Method", "Suite", "BT construction", "Evaluator mismatch", "Runtime failure"],
    },
    {
        "key": "model_robustness",
        "path": PAPER_TABLE_ROOT / "model_robustness.tex",
        "title": "Compact Cross-Model Robustness Check",
        "columns": ["Model", "Method(s)", "Success", "StructComp", "Grounding"],
    },
    {
        "key": "run_matrix",
        "path": PAPER_TABLE_ROOT / "run_matrix.tex",
        "title": "Experimental Matrix",
        "columns": ["Track", "Suites", "Methods", "Purpose"],
    },
]


def load_json(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def strip_tex(value: str) -> str:
    text = value.strip()
    text = re.sub(r"%.*", "", text)
    text = text.replace(r"\_", "_").replace(r"\&", "&")
    text = text.replace("``", '"').replace("''", '"')
    text = re.sub(r"\\redtext\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\textbf\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\textit\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\shortstack(?:\[[^\]]+\])?\{([^{}]*)\}", lambda m: m.group(1).replace(r"\\", " "), text)
    text = re.sub(r"\\multicolumn\{[^{}]*\}\{[^{}]*\}\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[a-zA-Z]+", "", text)
    text = text.replace("{", "").replace("}", "")
    text = text.replace(r"\\", " ")
    text = re.sub(r"\s+", " ", text).strip()
    return text


def parse_tex_table_rows(path: Path, column_count: int) -> tuple[str, str | None, list[list[str]]]:
    if not path.exists():
        return "", None, []
    text = path.read_text(encoding="utf-8")
    caption_match = re.search(r"\\caption\{([^{}]*)\}", text)
    label_match = re.search(r"\\label\{([^{}]*)\}", text)
    caption = strip_tex(caption_match.group(1)) if caption_match else path.stem
    label = label_match.group(1) if label_match else None

    tabular_match = re.search(r"\\begin\{tabular\}\{.*?\}(.*?)\\end\{tabular\}", text, re.S)
    if not tabular_match:
        return caption, label, []
    body = tabular_match.group(1)
    body = re.sub(r"\\hline|\\cline\{[^{}]*\}", "", body)

    rows: list[list[str]] = []
    for raw_row in body.split(r"\\"):
        row = raw_row.strip()
        if not row:
            continue
        cells = [strip_tex(cell) for cell in row.split("&")]
        if len(cells) < column_count:
            continue
        cells = cells[-column_count:]
        if not any(cells):
            continue
        rows.append(cells)
    return caption, label, rows


def load_paper_tables() -> list[dict[str, Any]]:
    tables: list[dict[str, Any]] = []
    for spec in PAPER_TABLE_SPECS:
        caption, label, rows = parse_tex_table_rows(spec["path"], len(spec["columns"]))
        tables.append(
            {
                "key": spec["key"],
                "title": spec["title"],
                "caption": caption or spec["title"],
                "label": label,
                "columns": list(spec["columns"]),
                "rows": rows,
                "incomplete": any(cell == "TBD" for row in rows for cell in row),
            }
        )
    return tables


def load_rootstocks() -> list[dict[str, Any]]:
    if not ROOTSTOCKS_PATH.exists():
        return []
    data = load_yaml_file(ROOTSTOCKS_PATH)
    rootstocks = data.get("rootstocks", []) if isinstance(data, dict) else []
    items: list[dict[str, Any]] = []
    for rootstock in rootstocks:
        if not isinstance(rootstock, dict) or not rootstock.get("name"):
            continue
        slots = rootstock.get("slots") if isinstance(rootstock.get("slots"), dict) else {}
        template_root = ((rootstock.get("template") or {}).get("root") or {}) if isinstance(rootstock.get("template"), dict) else {}
        template = rootstock.get("template") if isinstance(rootstock.get("template"), dict) else None
        items.append(
            {
                "name": str(rootstock.get("name")),
                "description": str(rootstock.get("description") or ""),
                "when_to_use": str(rootstock.get("when_to_use") or ""),
                "anti_pattern": str(rootstock.get("anti_pattern") or ""),
                "slots": [{"name": str(key), "description": str(value)} for key, value in slots.items()],
                "template_root_type": str(template_root.get("type") or ""),
                "template_memory": template_root.get("memory"),
                "template": template,
                "bt_svg": render_bt_svg(template),
            }
        )
    return items


_BT_OPEN_RE = re.compile(r"<([A-Z][A-Za-z]+)[\s>]")


def extract_xml_snippets_from_raw(raw_block: str) -> list[str]:
    """Extract all well-formed XML snippets from a raw YAML entry string."""
    snippets: list[str] = []
    i = 0
    while i < len(raw_block):
        m = _BT_OPEN_RE.search(raw_block, i)
        if not m:
            break
        start = m.start()
        tag = m.group(1)
        close_tag = f"</{tag}>"
        open_tag = f"<{tag}"
        depth = 0
        j = start + len(open_tag)
        found = False
        while j < len(raw_block):
            open_pos = raw_block.find(open_tag, j)
            close_pos = raw_block.find(close_tag, j)
            if close_pos == -1:
                break
            if open_pos != -1 and open_pos < close_pos:
                depth += 1
                j = open_pos + len(open_tag)
            else:
                if depth == 0:
                    end = close_pos + len(close_tag)
                    snippets.append(raw_block[start:end].strip())
                    i = end
                    found = True
                    break
                depth -= 1
                j = close_pos + len(close_tag)
        if not found:
            i = start + 1
    return snippets


def load_panther_rootstocks() -> list[dict[str, Any]]:
    """Parse Panther rootstocks directly from raw YAML text (no PyYAML needed)."""
    if not PANTHER_ROOTSTOCKS_PATH.exists():
        return []
    text = PANTHER_ROOTSTOCKS_PATH.read_text(encoding="utf-8")
    # Split on each rootstock entry boundary
    raw_entries = re.split(r"^\s{2}- name:", text, flags=re.MULTILINE)
    items: list[dict[str, Any]] = []
    for entry in raw_entries[1:]:  # skip preamble
        name_match = re.match(r"\s*(\S+)", entry)
        if not name_match:
            continue
        name = name_match.group(1)
        desc_match = re.search(r"description:\s*(.+)", entry)
        description = desc_match.group(1).strip() if desc_match else ""
        xml_snippets = extract_xml_snippets_from_raw(entry)
        # Use the longest snippet (most complete tree)
        xml_snippet = max(xml_snippets, key=len) if xml_snippets else None
        bt_json: dict[str, Any] | None = None
        if xml_snippet:
            wrapped = f"<root><BehaviorTree>{xml_snippet}</BehaviorTree></root>"
            bt_json = parse_xml_bt(wrapped)
        items.append({
            "name": name,
            "description": description,
            "bt_xml": xml_snippet,
            "bt_svg": render_bt_svg(bt_json) if bt_json else None,
        })
    return items


def parse_scalar(value: str) -> Any:
    lowered = value.lower()
    if lowered == "true":
        return True
    if lowered == "false":
        return False
    if lowered in {"null", "none"}:
        return None
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    if re.fullmatch(r"-?\d+\.\d+", value):
        return float(value)
    return value


def load_yaml_file(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    if yaml is not None:
        data = yaml.safe_load(text) or {}
        if isinstance(data, dict):
            return data
        return {}
    return parse_simple_yaml(text)


def parse_simple_yaml(text: str) -> dict[str, Any]:
    lines: list[tuple[int, str]] = []
    for raw_line in text.splitlines():
        if not raw_line.strip() or raw_line.lstrip().startswith("#") or raw_line.strip() == "---":
            continue
        indent = len(raw_line) - len(raw_line.lstrip(" "))
        lines.append((indent, raw_line.strip()))

    def parse_block(index: int, indent: int) -> tuple[Any, int]:
        if index >= len(lines):
            return {}, index
        if lines[index][1].startswith("- "):
            return parse_list(index, indent)
        return parse_dict(index, indent)

    def parse_dict(index: int, indent: int) -> tuple[dict[str, Any], int]:
        data: dict[str, Any] = {}
        while index < len(lines):
            line_indent, stripped = lines[index]
            if line_indent < indent:
                break
            if line_indent > indent:
                index += 1
                continue
            if stripped.startswith("- "):
                break

            key, _, remainder = stripped.partition(":")
            key = key.strip()
            remainder = remainder.lstrip()
            index += 1

            if remainder:
                data[key] = parse_scalar(remainder)
                continue

            if index < len(lines) and (
                lines[index][0] > line_indent
                or (lines[index][0] == line_indent and lines[index][1].startswith("- "))
            ):
                child_indent = lines[index][0]
                child, index = parse_block(index, child_indent)
                data[key] = child
            else:
                data[key] = {}
        return data, index

    def parse_list(index: int, indent: int) -> tuple[list[Any], int]:
        items: list[Any] = []
        while index < len(lines):
            line_indent, stripped = lines[index]
            if line_indent < indent:
                break
            if line_indent != indent or not stripped.startswith("- "):
                break

            rest = stripped[2:].strip()
            index += 1

            if not rest:
                if index < len(lines) and lines[index][0] > line_indent:
                    child, index = parse_block(index, lines[index][0])
                    items.append(child)
                else:
                    items.append(None)
                continue

            if ":" in rest:
                key, _, remainder = rest.partition(":")
                item: dict[str, Any] = {}
                if remainder.strip():
                    item[key.strip()] = parse_scalar(remainder.strip())
                else:
                    if index < len(lines) and lines[index][0] > line_indent:
                        child, index = parse_block(index, lines[index][0])
                        item[key.strip()] = child
                    else:
                        item[key.strip()] = {}
                if index < len(lines) and lines[index][0] > line_indent:
                    child, index = parse_block(index, lines[index][0])
                    if isinstance(child, dict):
                        item.update(child)
                items.append(item)
                continue

            items.append(parse_scalar(rest))
        return items, index

    if not lines:
        return {}
    parsed, _ = parse_block(0, lines[0][0])
    return parsed if isinstance(parsed, dict) else {}


def xml_elem_to_bt_json(elem: ET.Element) -> dict[str, Any]:
    """Recursively convert a BT.CPP XML element to the internal JSON node format."""
    tag = elem.tag
    name = elem.get("name", tag)
    children = [xml_elem_to_bt_json(child) for child in elem if isinstance(child.tag, str)]

    lowered = tag.lower()
    if tag in _BTCPP_CONTROL_TAGS:
        if "sequence" in lowered:
            node_type = "sequence"
        elif "fallback" in lowered or "selector" in lowered:
            node_type = "selector"
        elif tag in ("KeepRunningUntilFailure", "ForceSuccess", "ForceFailure", "Inverter"):
            node_type = "decorator"
        else:
            node_type = "control"
        params = {k: v for k, v in elem.attrib.items() if k != "name"}
        return {"type": node_type, "name": name, "tag": tag, "params": params or None, "children": children}

    # leaf nodes: check if it's a condition by name convention or explicit tag
    is_condition = tag in _BTCPP_CONDITION_TAGS or lowered.startswith("check") or lowered.startswith("is_")
    params = {k: v for k, v in elem.attrib.items() if k != "name"}
    if is_condition:
        return {"type": "condition", "condition": name, "name": name, "tag": tag, "params": params or None, "children": []}
    return {"type": "action", "action": name, "name": name, "tag": tag, "params": params or None, "children": []}


def parse_xml_bt(xml_text: str) -> dict[str, Any] | None:
    """Parse BT.CPP XML and return a bt_json dict compatible with render_bt_svg."""
    try:
        root_elem = ET.fromstring(xml_text)
    except ET.ParseError:
        return None
    # Find the first BehaviorTree child
    bt_elem = root_elem.find("BehaviorTree")
    if bt_elem is None:
        return None
    children = [child for child in bt_elem if isinstance(child.tag, str)]
    if not children:
        return None
    root_node = xml_elem_to_bt_json(children[0])
    return {"root": root_node}


def detect_model(name: str) -> str:
    lowered = name.lower()
    if "sonnet" in lowered:
        return "Sonnet 4.6"
    if "gemma" in lowered:
        return "Gemma4:31b"
    return "Unknown"


def detect_environment(name: str) -> str:
    lowered = name.lower()
    if "panther" in lowered:
        return "panther"
    return "pyrobosim"


PANTHER_CATEGORY_MAP = {
    1: ("navigation", "Navigation"), 2: ("navigation", "Navigation"), 3: ("navigation", "Navigation"),
    4: ("reactive_detection", "Reactive Detection"), 5: ("reactive_detection", "Reactive Detection"),
    6: ("reactive_detection", "Reactive Detection"), 7: ("reactive_detection", "Reactive Detection"),
    8: ("track_engage", "Track & Engage"), 9: ("track_engage", "Track & Engage"), 10: ("track_engage", "Track & Engage"),
    11: ("multi_phase", "Multi-phase Mission"), 12: ("multi_phase", "Multi-phase Mission"),
    13: ("multi_phase", "Multi-phase Mission"), 14: ("multi_phase", "Multi-phase Mission"),
}


def build_panther_batch(batch_dir: Path) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    submissions_path = batch_dir / "submissions.jsonl"
    xmls_dir = batch_dir / "xmls"
    if not submissions_path.exists() or not xmls_dir.exists():
        return None

    submissions = []
    for line in submissions_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            try:
                submissions.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    xml_files = sorted(f for f in xmls_dir.iterdir() if f.suffix == ".xml")

    method = detect_method(batch_dir.name)
    model = detect_model(batch_dir.name)
    task_items: list[dict[str, Any]] = []

    # Group submissions by task prompt to find first-attempt validity per task.
    # The valid XML files are numbered 01..N; invalid ones are prefixed "invalid__".
    # A task's Valid@1 = True only if attempt_number==1 was valid.
    from collections import defaultdict
    tasks_by_prompt: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for sub in submissions:
        tasks_by_prompt[sub.get("task_prompt", "")].append(sub)

    # Sort each task's attempts by attempt_number
    for attempts in tasks_by_prompt.values():
        attempts.sort(key=lambda s: s.get("attempt_number", 1))

    # Valid XML files (non-invalid) in order represent the final accepted BT per task
    valid_xml_files = [f for f in xml_files if not f.name.startswith("invalid")]

    task_num = 0
    for prompt, attempts in tasks_by_prompt.items():
        task_num += 1
        first_attempt = attempts[0]
        first_attempt_valid = first_attempt.get("valid", False)
        # The accepted XML is the last valid submission for this task
        final_sub = next((s for s in reversed(attempts) if s.get("valid")), None)
        xml_text = None
        if task_num - 1 < len(valid_xml_files):
            xml_text = valid_xml_files[task_num - 1].read_text(encoding="utf-8")
        bt_json = parse_xml_bt(xml_text) if xml_text else None
        archetype, archetype_label = PANTHER_CATEGORY_MAP.get(task_num, ("other", "Other"))

        task_items.append({
            "id": f"task{task_num:02d}_{archetype}",
            "prompt": prompt,
            "archetype": archetype,
            "archetype_label": archetype_label,
            "success": None,
            "exec_status": None,
            "failure_cause": None,
            "valid": first_attempt_valid,  # Valid@1: first attempt only
            "issues": first_attempt.get("issues", []),
            "attempt_number": len(attempts),
            "task_spec": None,
            "task_spec_view": None,
            "result": None,
            "bt_json": bt_json,
            "bt_xml": xml_text,
            "bt_svg": render_bt_svg(bt_json) if bt_json else None,
        })

    total_tasks = len(task_items)
    valid_rate = sum(1 for t in task_items if t.get("valid")) / total_tasks if total_tasks else 0.0

    batch_record = {
        "name": batch_dir.name,
        "method": method,
        "model": model,
        "suite_id": "panther14",
        "suite_label": "Panther 14",
        "suite_name": "panther_hardware",
        "environment": "panther",
        "count": total_tasks,
        "summary": {"count": total_tasks, "valid_rate": valid_rate},
        "task_ids": [t["id"] for t in task_items],
    }
    return batch_record, task_items


def normalize_suite(value: str | None) -> str | None:
    if not value:
        return None
    lowered = value.lower()
    if "language50" in lowered or "lang50" in lowered:
        return "language50"
    if "core60" in lowered:
        return "core60"
    return None


def detect_method(name: str) -> str:
    lowered = name.lower()
    if "mcore" in lowered:
        return "M-Core"
    if re.search(r"(^|[_-])b1($|[_-])", lowered):
        return "B1"
    if re.search(r"(^|[_-])b0($|[_-])", lowered):
        return "B0"
    return "Other"


def sort_key(batch_name: str) -> tuple[int, str]:
    method = detect_method(batch_name)
    return (METHOD_ORDER.get(method, 99), batch_name)


def humanize_token(value: str) -> str:
    return value.replace("_", " ").replace("-", " ").strip().title()


def compact_bt_label(node: dict[str, Any]) -> str:
    node_type = str(node.get("type") or "node")
    if node_type in {"sequence", "selector", "fallback", "parallel"}:
        return humanize_token(node_type)
    action = node.get("action")
    if action:
        return humanize_token(str(action))
    name = str(node.get("name") or node.get("condition") or node_type)
    return humanize_token(name)


def compact_bt_detail(node: dict[str, Any]) -> str:
    params = node.get("params")
    if not isinstance(params, dict) or not params:
        return ""
    parts = [str(value).replace("_", " ") for _, value in list(params.items())[:2]]
    return ", ".join(parts)


def wrap_svg_text(text: str, max_chars: int = 16) -> list[str]:
    words = text.split()
    if not words:
        return [""]
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = f"{current} {word}"
        if len(candidate) <= max_chars:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines[:3]


def bt_node_style(node: dict[str, Any]) -> dict[str, str]:
    node_type = str(node.get("type") or "node").lower()
    if node_type in {"selector", "fallback"}:
        return {"shape": "hex", "fill": "#69e0eb", "stroke": "#197c85"}
    if node_type in {"sequence", "parallel"}:
        return {"shape": "rect", "fill": "#ffd24f", "stroke": "#9a7400"}
    if node_type == "condition":
        return {"shape": "ellipse", "fill": "#d8dde5", "stroke": "#717784"}
    return {"shape": "ellipse", "fill": "#e5e8ee", "stroke": "#7c8391"}


def bt_node_lines(node: dict[str, Any]) -> list[str]:
    title = compact_bt_label(node)
    detail = compact_bt_detail(node)
    lines = wrap_svg_text(title, max_chars=15)
    if detail:
        lines.extend(wrap_svg_text(detail, max_chars=17)[:1])
    return lines[:3]


def bt_node_box(node: dict[str, Any]) -> tuple[float, float]:
    lines = bt_node_lines(node)
    max_line = max((len(line) for line in lines), default=10)
    width = max(94.0, min(156.0, 24.0 + max_line * 6.7))
    height = 28.0 + len(lines) * 13.0
    return width, height


def render_svg_shape(style: dict[str, str], cx: float, cy: float, width: float, height: float) -> str:
    fill = style["fill"]
    stroke = style["stroke"]
    shape = style["shape"]
    if shape == "rect":
        x = cx - width / 2
        y = cy - height / 2
        return (
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{width:.1f}" height="{height:.1f}" '
            f'rx="9" ry="9" fill="{fill}" stroke="{stroke}" stroke-width="1.3" />'
        )
    if shape == "hex":
        x0 = cx - width / 2
        x1 = cx - width * 0.28
        x2 = cx + width * 0.28
        x3 = cx + width / 2
        y0 = cy - height / 2
        y1 = cy
        y2 = cy + height / 2
        points = [
            (x1, y0), (x2, y0), (x3, y1), (x2, y2), (x1, y2), (x0, y1),
        ]
        point_str = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        return f'<polygon points="{point_str}" fill="{fill}" stroke="{stroke}" stroke-width="1.3" />'
    return (
        f'<ellipse cx="{cx:.1f}" cy="{cy:.1f}" rx="{width/2:.1f}" ry="{height/2:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.3" />'
    )


def render_svg_text(cx: float, cy: float, node: dict[str, Any]) -> str:
    lines = bt_node_lines(node)
    start_y = cy - (len(lines) - 1) * 6
    chunks = [
        f'<text x="{cx:.1f}" y="{start_y + idx * 14:.1f}" text-anchor="middle" '
        f'font-family="Avenir Next, Segoe UI, sans-serif" font-size="{11.5 if idx == 0 else 10}" '
        f'font-weight="{700 if idx == 0 else 500}" fill="#172033">{escape(line)}</text>'
        for idx, line in enumerate(lines)
    ]
    return "".join(chunks)


def render_bt_svg(bt_json: dict[str, Any] | None) -> str | None:
    root = bt_json.get("root") if isinstance(bt_json, dict) else None
    if not isinstance(root, dict):
        return None

    sibling_gap = 28.0
    level_gap = 88.0
    margin = 24.0
    id_counter = 0

    def clone_tree(node: dict[str, Any], depth: int = 0) -> dict[str, Any]:
        nonlocal id_counter
        children = [clone_tree(child, depth + 1) for child in node.get("children", []) if isinstance(child, dict)]
        width, height = bt_node_box(node)
        item = {
            "id": f"n{id_counter}",
            "node": node,
            "depth": depth,
            "children": children,
            "width": width,
            "height": height,
        }
        id_counter += 1
        return item

    tree = clone_tree(root)

    def count_leaves(item: dict[str, Any]) -> int:
        if not item["children"]:
            item["leaf_count"] = 1
            return 1
        total = sum(count_leaves(child) for child in item["children"])
        item["leaf_count"] = total
        return total

    def compute_subtree_width(item: dict[str, Any]) -> float:
        if not item["children"]:
            item["subtree_width"] = item["width"]
            return item["subtree_width"]
        children_width = sum(compute_subtree_width(child) for child in item["children"])
        children_width += sibling_gap * (len(item["children"]) - 1)
        item["children_width"] = children_width
        item["subtree_width"] = max(item["width"], children_width)
        return item["subtree_width"]

    def assign_positions(item: dict[str, Any], x_left: float) -> None:
        item["x"] = x_left + item["subtree_width"] / 2
        if not item["children"]:
            return
        child_x = x_left + (item["subtree_width"] - item["children_width"]) / 2
        for child in item["children"]:
            assign_positions(child, child_x)
            child_x += child["subtree_width"] + sibling_gap

    def assign_y(item: dict[str, Any]) -> None:
        item["y"] = margin + item["depth"] * level_gap
        for child in item["children"]:
            assign_y(child)

    def max_depth(item: dict[str, Any]) -> int:
        if not item["children"]:
            return item["depth"]
        return max(max_depth(child) for child in item["children"])

    count_leaves(tree)
    compute_subtree_width(tree)
    assign_positions(tree, margin)
    assign_y(tree)
    width = max(tree["subtree_width"] + margin * 2, 280.0)
    height = margin * 2 + max_depth(tree) * level_gap + tree["height"]

    edge_parts: list[str] = []
    node_parts: list[str] = []

    def walk(item: dict[str, Any]) -> None:
        for child in item["children"]:
            edge_parts.append(
                f'<line x1="{item["x"]:.1f}" y1="{item["y"] + item["height"] / 2 - 2:.1f}" '
                f'x2="{child["x"]:.1f}" y2="{child["y"] - child["height"] / 2 + 2:.1f}" '
                f'stroke="#7b7f89" stroke-width="1.2" stroke-linecap="round" />'
            )
            walk(child)

        style = bt_node_style(item["node"])
        node_parts.append(render_svg_shape(style, item["x"], item["y"], item["width"], item["height"]))
        node_parts.append(
            render_svg_text(item["x"], item["y"], item["node"])
        )

    walk(tree)

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.1f} {height:.1f}" '
        f'width="100%" height="100%" preserveAspectRatio="xMidYMin meet">'
        f'<rect x="0" y="0" width="{width:.1f}" height="{height:.1f}" fill="#fffdf8" rx="14" ry="14" />'
        f'{"".join(edge_parts)}{"".join(node_parts)}</svg>'
    )


def summarize_task_spec(task: dict[str, Any], suite_meta: dict[str, Any]) -> dict[str, Any]:
    static = ((task.get("required") or {}).get("static") or {}) if isinstance(task, dict) else {}
    success = (task.get("success") or {}) if isinstance(task, dict) else {}

    control_flow = []
    if static.get("must_use_memory_sequence"):
        control_flow.append("Use a memory sequence for the main execution path")
    if static.get("must_use_selector"):
        control_flow.append("Use selector fallback for the search branches")

    success_conditions = []
    if success.get("must_hold_category"):
        success_conditions.append(f"Robot must be holding `{success['must_hold_category']}`")
    if success.get("robot_at"):
        success_conditions.append(f"Robot must finish at `{success['robot_at']}`")
    if isinstance(success.get("must_place_category_at"), dict):
        place_rule = success.get("must_place_category_at") or {}
        category = place_rule.get("category")
        location = place_rule.get("location")
        if category and location:
            success_conditions.append(f"`{category}` must be placed at `{location}`")
    if success.get("category_at_location"):
        for category, location in (success.get("category_at_location") or {}).items():
            success_conditions.append(f"`{category}` must end at `{location}`")

    return {
        "suite_name": suite_meta.get("suite_name"),
        "environment": suite_meta.get("environment"),
        "world_file": suite_meta.get("world_file"),
        "robot_name": suite_meta.get("robot_name"),
        "archetype": task.get("archetype"),
        "archetype_label": ARCHETYPE_LABELS.get(str(task.get("archetype")), humanize_token(str(task.get("archetype", "task")))),
        "required_actions": list(static.get("actions") or []),
        "required_locations": list(static.get("locations") or []),
        "control_flow": control_flow,
        "success_conditions": success_conditions,
        "runtime": suite_meta.get("runtime") or {},
    }


def load_suites() -> dict[str, dict[str, Any]]:
    suites: dict[str, dict[str, Any]] = {}
    for path in sorted(TASK_SPEC_ROOT.glob("*.yaml")):
        data = load_yaml_file(path)
        suite_name = data.get("suite_name")
        suite_id = normalize_suite(suite_name)
        if not isinstance(suite_name, str) or not suite_id:
            continue
        tasks = {}
        for task in data.get("tasks") or []:
            if isinstance(task, dict) and task.get("id"):
                tasks[str(task["id"])] = task
        suites[suite_id] = {
            "suite_id": suite_id,
            "label": SUITE_LABELS.get(suite_id, suite_id),
            "suite_name": suite_name,
            "environment": data.get("environment"),
            "world_file": data.get("world_file"),
            "robot_name": data.get("robot_name"),
            "runtime": data.get("runtime") or {},
            "tasks": tasks,
        }
    return suites


def build_batch(batch_dir: Path, suites: dict[str, dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]] | None:
    summary = load_json(batch_dir / "results_summary.json", {})
    results = load_json(batch_dir / "results.json", [])
    if not isinstance(results, list):
        return None

    suite_name = None
    suite_names = summary.get("suite_names")
    if isinstance(suite_names, list) and suite_names:
        suite_name = str(suite_names[0])
    else:
        for row in results:
            if isinstance(row, dict) and row.get("suite_name"):
                suite_name = str(row.get("suite_name"))
                break

    suite_id = normalize_suite(suite_name) or normalize_suite(batch_dir.name)
    if not suite_id or suite_id not in suites:
        return None

    suite_meta = suites[suite_id]
    method = detect_method(batch_dir.name)
    task_items: list[dict[str, Any]] = []
    archetype_counts: dict[str, int] = {}

    for row in results:
        if not isinstance(row, dict):
            continue
        task_id = str(row.get("id", ""))
        task_spec = suite_meta["tasks"].get(task_id)
        if not task_id or not task_spec:
            continue
        # bt_path in results.json points to the eval harness (stale); use local jsons/ dir instead
        bt_json = None
        jsons_dir = batch_dir / "jsons"
        if jsons_dir.exists():
            json_files = sorted(jsons_dir.glob("*.json"))
            task_index = len(task_items)  # current position (0-based)
            if task_index < len(json_files):
                bt_json = load_json(json_files[task_index], None)
        archetype = str(task_spec.get("archetype") or row.get("archetype") or "unknown")
        archetype_counts[archetype] = archetype_counts.get(archetype, 0) + 1
        task_items.append(
            {
                "id": task_id,
                "prompt": task_spec.get("task_prompt") or row.get("task_prompt"),
                "archetype": archetype,
                "archetype_label": ARCHETYPE_LABELS.get(archetype, humanize_token(archetype)),
                "success": row.get("success"),
                "exec_status": row.get("exec_status"),
                "failure_cause": row.get("failure_cause"),
                "task_spec": task_spec,
                "task_spec_view": summarize_task_spec(task_spec, suite_meta),
                "result": row,
                "bt_json": bt_json,
                "bt_svg": render_bt_svg(bt_json),
            }
        )

    task_items.sort(key=lambda item: item["id"])
    batch_record = {
        "name": batch_dir.name,
        "method": method,
        "suite_id": suite_id,
        "suite_label": suite_meta["label"],
        "suite_name": suite_meta["suite_name"],
        "environment": suite_meta["environment"],
        "count": summary.get("count", len(task_items)),
        "summary": summary,
        "archetype_counts": archetype_counts,
        "task_ids": [item["id"] for item in task_items],
    }
    return batch_record, task_items


def build_catalog() -> dict[str, Any]:
    suites = load_suites()
    paper_tables = load_paper_tables()
    rootstocks = load_rootstocks()
    panther_rootstocks = load_panther_rootstocks()
    batches: list[dict[str, Any]] = []
    tasks_by_batch: dict[str, list[dict[str, Any]]] = {}

    for batch_dir in sorted((path for path in GENERATED_ROOT.iterdir() if path.is_dir()), key=lambda path: sort_key(path.name)):
        env = detect_environment(batch_dir.name)
        if env == "panther":
            built = build_panther_batch(batch_dir)
        else:
            built = build_batch(batch_dir, suites)
            if built:
                # Inject model field into pyrobosim batch records
                built[0]["model"] = detect_model(batch_dir.name)
        if not built:
            continue
        batch_record, task_items = built
        batches.append(batch_record)
        tasks_by_batch[batch_record["name"]] = task_items

    suite_index = {}
    for suite_id, suite_meta in suites.items():
        suite_index[suite_id] = {
            "suite_id": suite_id,
            "label": suite_meta["label"],
            "suite_name": suite_meta["suite_name"],
            "environment": suite_meta["environment"],
            "world_file": suite_meta["world_file"],
            "robot_name": suite_meta["robot_name"],
            "runtime": suite_meta["runtime"],
            "task_count": len(suite_meta["tasks"]),
        }
    suite_index["panther14"] = {
        "suite_id": "panther14",
        "label": "Panther 14",
        "suite_name": "panther_hardware",
        "environment": "panther",
        "world_file": None,
        "robot_name": "panther",
        "runtime": {},
        "task_count": 14,
    }

    methods_present = sorted(
        {batch["method"] for batch in batches},
        key=lambda method: METHOD_ORDER.get(method, 99),
    )
    models_present = sorted({batch.get("model", "Unknown") for batch in batches})

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "project": {
            "title": "Behavior Tree Synthesis via Coding Agents",
            "subtitle": "Grounding, Grafting, and Physical Deployment",
        },
        "methods": methods_present,
        "models": models_present,
        "suites": suite_index,
        "paper_tables": paper_tables,
        "rootstocks": rootstocks,
        "panther_rootstocks": panther_rootstocks,
        "batches": batches,
        "tasks_by_batch": tasks_by_batch,
    }


def main() -> None:
    catalog = build_catalog()
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(catalog, indent=2), encoding="utf-8")
    print(f"Wrote catalog with {len(catalog['batches'])} batches to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
