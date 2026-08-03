"""Deterministic translation between pragmatic Spectre and SPICE subsets.

The translators are intentionally local and side-effect free: text goes in,
translated text plus structured diagnostics comes out.  They do not run a
simulator, edit the source file, or guess PDK semantics unless an explicit
profile is selected.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from .profiles import TranslationProfile, find_sky130_model_library, get_profile


Dialect = Literal["spectre", "spice", "ngspice"]


@dataclass(frozen=True)
class TranslationIssue:
    """One lossy, unsupported, or profile-specific translation event."""

    line: int
    code: str
    message: str
    statement: str = ""


@dataclass(frozen=True)
class TranslationResult:
    """Translated text and all non-fatal diagnostics."""

    text: str
    source: str
    target: str
    issues: tuple[TranslationIssue, ...] = ()


class TranslationError(ValueError):
    """Raised when strict translation encounters unsupported input."""

    def __init__(self, issue: TranslationIssue):
        self.issue = issue
        location = f"line {issue.line}: " if issue.line else ""
        super().__init__(f"{location}{issue.message}")


_SPECTRE_INSTANCE_RE = re.compile(
    r"^(\S+)\s*\(\s*([^)]*?)\s*\)\s*(\S+)(?:\s+(.*))?$"
)
_SPECTRE_INCLUDE_RE = re.compile(
    r'^include\s+"([^"]+)"(?:\s+section\s*=\s*(\S+))?.*$', re.IGNORECASE
)
_NUMBER_RE = re.compile(
    r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?([TGMKkmunpfa])?$"
)
_SPICE_NUMBER_RE = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?)(meg|[tgkmunpfa])?$",
    re.IGNORECASE,
)
_SPECTRE_SUFFIX = {
    "T": 1e12,
    "G": 1e9,
    "M": 1e6,
    "K": 1e3,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
    "a": 1e-18,
}
_SPICE_SUFFIX = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
    "a": 1e-18,
}
_ANALYSES = {"tran", "ac", "dc", "noise", "op"}
_SPICE_CONTROL_NOOPS = {
    "destroy",
    "display",
    "echo",
    "plot",
    "print",
    "quit",
    "reset",
    "resume",
    "run",
    "set",
    "setplot",
    "setseed",
    "show",
    "unset",
    "wrdata",
    "write",
}


def convert_text(
    text: str,
    *,
    source: Dialect,
    target: Dialect,
    profile: str | None = None,
    fragment: bool = False,
    model_lib: str | Path | None = None,
    pdk_root: str | Path | None = None,
    corner: str = "tt",
    strict: bool = True,
    title: str = "netlist",
) -> TranslationResult:
    """Translate netlist text between supported dialects.

    ``spice`` and ``ngspice`` share the same translator today; the distinct
    names keep the public API honest and leave room for future dialect rules.
    No PDK behavior is enabled unless ``profile`` is explicitly provided.
    """

    source_name = source.lower()
    target_name = target.lower()
    if source_name == target_name or {source_name, target_name} <= {"spice", "ngspice"}:
        return TranslationResult(text=text, source=source_name, target=target_name)

    selected_profile = get_profile(profile)
    if source_name == "spectre" and target_name in {"spice", "ngspice"}:
        return _spectre_to_spice(
            text,
            target=target_name,
            profile=selected_profile,
            fragment=fragment,
            model_lib=model_lib,
            pdk_root=pdk_root,
            corner=corner,
            strict=strict,
            title=title,
        )
    if source_name in {"spice", "ngspice"} and target_name == "spectre":
        return _spice_to_spectre(text, source=source_name, strict=strict, title=title)
    raise ValueError(f"unsupported translation: {source} -> {target}")


def convert_file(
    input_path: str | Path,
    output_path: str | Path,
    **kwargs,
) -> TranslationResult:
    """Translate one file, writing output only after translation succeeds."""

    source_path = Path(input_path)
    destination = Path(output_path)
    result = convert_text(
        source_path.read_text(encoding="utf-8", errors="replace"),
        title=source_path.name,
        **kwargs,
    )
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(result.text, encoding="utf-8")
    return result


def _spectre_to_spice(
    text: str,
    *,
    target: str,
    profile: TranslationProfile | None,
    fragment: bool,
    model_lib: str | Path | None,
    pdk_root: str | Path | None,
    corner: str,
    strict: bool,
    title: str,
) -> TranslationResult:
    issues: list[TranslationIssue] = []
    out = [f"* {title} - translated from Spectre by netlist-crawler"]
    resolved_sky130_model = None
    if profile is not None and profile.name == "sky130":
        resolved_sky130_model = find_sky130_model_library(
            model_lib=model_lib,
            pdk_root=pdk_root,
        )

    for line, statement in _spectre_statements(text):
        stripped = statement.strip()
        if not stripped:
            continue
        if stripped.startswith("//"):
            out.append("*" + stripped[2:])
            continue

        code, comment = _split_inline_comment(stripped, "//")
        if not code:
            if comment:
                out.append(f"* {comment}")
            continue
        translated = _spectre_statement_to_spice(
            code,
            line=line,
            profile=profile,
            fragment=fragment,
            model_lib=resolved_sky130_model,
            corner=corner,
            strict=strict,
            issues=issues,
        )
        if comment and translated:
            translated[-1] += f" ; {comment}"
        out.extend(translated)

    if not fragment and not any(item.lower() == ".end" for item in out):
        out.append(".end")
    return TranslationResult(
        text="\n".join(out).rstrip() + "\n",
        source="spectre",
        target=target,
        issues=tuple(issues),
    )


def _spectre_statement_to_spice(
    statement: str,
    *,
    line: int,
    profile: TranslationProfile | None,
    fragment: bool,
    model_lib: Path | None,
    corner: str,
    strict: bool,
    issues: list[TranslationIssue],
) -> list[str]:
    fields = _split_fields(statement)
    if not fields:
        return []
    head = fields[0].lower()

    if head == "simulator":
        return []
    if head == "global":
        return [".global " + " ".join(fields[1:])]
    if head == "parameters":
        return [".param " + " ".join(_spectre_param(token) for token in fields[1:])]
    if head == "include":
        match = _SPECTRE_INCLUDE_RE.match(statement)
        if not match:
            return _unsupported(line, "include", "cannot parse Spectre include", statement, strict, issues)
        include_path, section = match.groups()
        if profile is not None and profile.matches_model_include(include_path):
            if fragment:
                return [f"* omitted {profile.name} model include: {include_path}"]
            if model_lib is None:
                return _unsupported(
                    line,
                    "profile-model",
                    f"{profile.name} model include needs --model-lib/--pdk-root, or --fragment",
                    statement,
                    strict,
                    issues,
                )
            return [f'.lib "{model_lib}" {section or corner}']
        if section:
            return [f'.lib "{include_path}" {section}']
        return [f'.include "{include_path}"']
    if head == "subckt":
        return [".subckt " + " ".join(fields[1:])]
    if head == "ends":
        return [".ends" + (" " + " ".join(fields[1:]) if len(fields) > 1 else "")]
    if head == "save":
        return [".save " + " ".join(fields[1:])]
    if head == "options" or (len(fields) >= 2 and fields[1].lower() == "options"):
        body = fields[1:] if head == "options" else fields[2:]
        return [".options " + " ".join(body)]
    if head == "temp":
        body = " ".join(fields[1:]).lstrip("=").strip()
        return [".temp " + _spectre_value(body)]
    if head == "ic":
        body = statement[len(fields[0]):].strip().strip("()")
        assignments = []
        for token in _split_fields(body):
            if "=" in token:
                node, value = token.split("=", 1)
                assignments.append(f"v({node})={_spectre_value(value)}")
        return [".ic " + " ".join(assignments)] if assignments else []

    analysis = fields[1].lower() if len(fields) >= 2 else ""
    if analysis in _ANALYSES:
        params = _param_dict(fields[2:])
        return _spectre_analysis_to_spice(fields[0], analysis, params, line, statement, strict, issues)

    match = _SPECTRE_INSTANCE_RE.match(statement)
    if not match:
        return _unsupported(line, "statement", "unsupported Spectre statement", statement, strict, issues)
    name, node_text, master, rest = match.groups()
    nodes = _split_fields(node_text)
    params = _param_dict(_split_fields(rest or ""))
    return [_spectre_instance_to_spice(name, nodes, master, params, profile)]


def _spectre_analysis_to_spice(
    name: str,
    analysis: str,
    params: dict[str, str],
    line: int,
    statement: str,
    strict: bool,
    issues: list[TranslationIssue],
) -> list[str]:
    if analysis == "op":
        return [".op"]
    if analysis == "tran":
        step = _spectre_value(params.get("step", params.get("maxstep", "1p")))
        stop = _spectre_value(params.get("stop", "1n"))
        start = _spectre_value(params.get("start", "0"))
        maxstep = params.get("maxstep") or params.get("max_step")
        output = f".tran {step} {stop} {start}"
        if maxstep:
            output += f" {_spectre_value(maxstep)}"
        if params.get("uic", "").lower() in {"1", "yes", "true"}:
            output += " uic"
        return [output]
    if analysis == "ac":
        sweep = "dec"
        points = params.get("dec") or params.get("lin") or params.get("oct") or "40"
        if "lin" in params:
            sweep = "lin"
        elif "oct" in params:
            sweep = "oct"
        start = _spectre_value(params.get("start", "1"))
        stop = _spectre_value(params.get("stop", "1G"))
        return [f".ac {sweep} {points} {start} {stop}"]
    if analysis == "dc":
        source = params.get("source") or params.get("dev") or params.get("param")
        if not source:
            return _unsupported(line, "dc-source", "dc analysis needs source=", statement, strict, issues)
        start = _spectre_value(params.get("start", "0"))
        stop = _spectre_value(params.get("stop", "1"))
        step = _spectre_value(params.get("step", "0.01"))
        return [f".dc {source} {start} {stop} {step}"]
    if analysis == "noise":
        output = params.get("output", "vout")
        source = params.get("source", "VIN")
        points = params.get("dec", "20")
        start = _spectre_value(params.get("start", "1"))
        stop = _spectre_value(params.get("stop", "1M"))
        return [f".noise v({output}) {source} dec {points} {start} {stop}"]
    return _unsupported(line, "analysis", f"unsupported analysis {name} {analysis}", statement, strict, issues)


def _spectre_instance_to_spice(
    name: str,
    nodes: list[str],
    master: str,
    params: dict[str, str],
    profile: TranslationProfile | None,
) -> str:
    lowered = master.lower()
    if lowered in {"vsource", "isource"}:
        return _spectre_source_to_spice(name, nodes, lowered, params)
    if lowered in {"resistor", "capacitor", "inductor"}:
        prefix, key = {
            "resistor": ("R", "r"),
            "capacitor": ("C", "c"),
            "inductor": ("L", "l"),
        }[lowered]
        value = _spectre_value(params.pop(key, "0"))
        return f"{_prefixed_name(prefix, name)} {' '.join(nodes)} {value}"
    if lowered == "vcvs":
        gain = _spectre_value(params.pop("gain", "1"))
        return f"{_prefixed_name('E', name)} {' '.join(nodes)} {gain}"
    if lowered == "bsource":
        if "v" in params:
            return f"{_prefixed_name('B', name)} {' '.join(nodes)} V={_spectre_value(params['v'])}"
        if "i" in params:
            return f"{_prefixed_name('B', name)} {' '.join(nodes)} I={_spectre_value(params['i'])}"

    is_profile_subckt = profile is not None and lowered in profile.subcircuit_masters
    if name[:1].upper() in {"M", "D", "Q"} and not is_profile_subckt:
        prefix = name[:1].upper()
    else:
        prefix = "X"
    param_text = " ".join(f"{key}={_spectre_value(value)}" for key, value in params.items())
    return f"{_prefixed_name(prefix, name)} {' '.join(nodes)} {master} {param_text}".rstrip()


def _spectre_source_to_spice(
    name: str,
    nodes: list[str],
    master: str,
    params: dict[str, str],
) -> str:
    prefix = "V" if master == "vsource" else "I"
    parts = [_prefixed_name(prefix, name), *nodes]
    source_type = params.pop("type", "dc").lower()
    dc = params.pop("dc", None)
    if dc is not None:
        parts.extend(["DC", _spectre_value(dc)])
    mag = params.pop("mag", None)
    if mag is not None:
        parts.extend(["AC", _spectre_value(mag)])
    if source_type == "pulse":
        keys = ("val0", "val1", "delay", "rise", "fall", "width", "period")
        defaults = ("0", "0", "0", "1p", "1p", "1n", "2n")
        values = [_spectre_value(params.pop(key, default)) for key, default in zip(keys, defaults)]
        parts.append("PULSE(" + " ".join(values) + ")")
    elif source_type == "sine":
        keys = ("sinedc", "ampl", "freq", "delay")
        defaults = ("0", "0", "1k", "0")
        values = [_spectre_value(params.pop(key, default)) for key, default in zip(keys, defaults)]
        parts.append("SIN(" + " ".join(values) + ")")
    elif source_type == "pwl":
        wave = params.pop("wave", "").strip("[]")
        parts.append("PWL(" + " ".join(_spectre_value(value) for value in _split_fields(wave)) + ")")
    if dc is None and mag is None and source_type == "dc":
        parts.extend(["DC", "0"])
    return " ".join(parts)


def _spice_to_spectre(text: str, *, source: str, strict: bool, title: str) -> TranslationResult:
    issues: list[TranslationIssue] = []
    out = ["simulator lang=spectre", f"// {title} - translated from {source} by netlist-crawler"]
    in_control = False
    for line, statement in _spice_statements(text):
        stripped = statement.strip()
        if not stripped:
            continue
        if stripped.startswith("*"):
            out.append("//" + stripped[1:])
            continue
        code, comment = _split_inline_comment(stripped, ";")
        if not code:
            continue
        head = code.split(maxsplit=1)[0].lower()
        if head == ".control":
            in_control = True
            continue
        if head in {".endc", ".endcontrol"}:
            in_control = False
            continue
        if in_control and head in _SPICE_CONTROL_NOOPS:
            issues.append(
                TranslationIssue(line, "control-command", f"omitted ngspice control command {head}", code)
            )
            continue
        if in_control and head in _ANALYSES:
            code = "." + code
        translated = _spice_statement_to_spectre(code, line, strict, issues)
        if comment and translated:
            translated[-1] += f" // {comment}"
        out.extend(translated)
    return TranslationResult(
        text="\n".join(out).rstrip() + "\n",
        source=source,
        target="spectre",
        issues=tuple(issues),
    )


def _spice_statement_to_spectre(
    statement: str,
    line: int,
    strict: bool,
    issues: list[TranslationIssue],
) -> list[str]:
    fields = _split_fields(statement)
    if not fields:
        return []
    head = fields[0].lower()
    if head == ".end":
        return []
    if head in {".include", ".inc"}:
        return ["include " + " ".join(fields[1:])]
    if head == ".lib" and len(fields) >= 3:
        return [f"include {fields[1]} section={fields[2]}"]
    if head == ".global":
        return ["global " + " ".join(fields[1:])]
    if head == ".param":
        return ["parameters " + " ".join(_spice_param(token) for token in fields[1:])]
    if head == ".subckt":
        return ["subckt " + " ".join(fields[1:])]
    if head == ".ends":
        return ["ends" + (" " + " ".join(fields[1:]) if len(fields) > 1 else "")]
    if head == ".save":
        return ["save " + " ".join(fields[1:])]
    if head == ".options":
        return ["simulatorOptions options " + " ".join(fields[1:])]
    if head == ".temp":
        return ["temp " + " ".join(fields[1:])]
    if head == ".ic":
        assignments = re.findall(r"v\(([^)]+)\)\s*=\s*(\S+)", statement, re.IGNORECASE)
        return ["ic " + " ".join(f"{node}={_spice_value(value)}" for node, value in assignments)]
    if head in {".meas", ".measure"}:
        return ["measure " + " ".join(fields[1:])]
    if head == ".op":
        return ["op1 op"]
    if head == ".tran" and len(fields) >= 3:
        result = f"tran1 tran step={_spice_value(fields[1])} stop={_spice_value(fields[2])}"
        if len(fields) >= 4 and fields[3] != "0":
            result += f" start={_spice_value(fields[3])}"
        if len(fields) >= 5 and fields[4].lower() != "uic":
            result += f" maxstep={_spice_value(fields[4])}"
        if any(field.lower() == "uic" for field in fields):
            result += " uic=yes"
        return [result]
    if head == ".ac" and len(fields) >= 5:
        return [
            f"ac1 ac {fields[1].lower()}={fields[2]} "
            f"start={_spice_value(fields[3])} stop={_spice_value(fields[4])}"
        ]
    if head == ".dc" and len(fields) >= 5:
        return [
            f"dc1 dc source={fields[1]} start={_spice_value(fields[2])} "
            f"stop={_spice_value(fields[3])} step={_spice_value(fields[4])}"
        ]
    if head == ".noise" and len(fields) >= 7:
        output = fields[1]
        if output.lower().startswith("v(") and output.endswith(")"):
            output = output[2:-1]
        return [
            f"noise1 noise output={output} source={fields[2]} {fields[3].lower()}={fields[4]} "
            f"start={_spice_value(fields[5])} stop={_spice_value(fields[6])}"
        ]
    if head.startswith("."):
        return _unsupported(line, "directive", "unsupported SPICE directive", statement, strict, issues, prefix="//")
    return [_spice_instance_to_spectre(fields, statement, line, strict, issues)]


def _spice_instance_to_spectre(
    fields: list[str],
    statement: str,
    line: int,
    strict: bool,
    issues: list[TranslationIssue],
) -> str:
    name = fields[0]
    prefix = name[:1].upper()
    if prefix in {"R", "C", "L"} and len(fields) >= 4:
        master, key = {
            "R": ("resistor", "r"),
            "C": ("capacitor", "c"),
            "L": ("inductor", "l"),
        }[prefix]
        return f"{name} ({fields[1]} {fields[2]}) {master} {key}={_spice_value(fields[3])}"
    if prefix in {"V", "I"} and len(fields) >= 3:
        return _spice_source_to_spectre(name, fields[1:3], " ".join(fields[3:]))
    if prefix == "E" and len(fields) >= 6:
        return f"{name} ({' '.join(fields[1:5])}) vcvs gain={_spice_value(fields[5])}"
    if prefix == "B" and len(fields) >= 4:
        return f"{name} ({fields[1]} {fields[2]}) bsource {' '.join(fields[3:]).lower()}"
    if prefix == "M" and len(fields) >= 6:
        params = " ".join(_spice_param(token) for token in fields[6:])
        return f"{name} ({' '.join(fields[1:5])}) {fields[5]} {params}".rstrip()
    if prefix in {"D", "Q"}:
        node_count = 2 if prefix == "D" else 3
        if len(fields) >= node_count + 2:
            nodes = fields[1:1 + node_count]
            master = fields[1 + node_count]
            params = " ".join(_spice_param(token) for token in fields[2 + node_count:])
            return f"{name} ({' '.join(nodes)}) {master} {params}".rstrip()
    if prefix == "X" and len(fields) >= 3:
        first_param = next((index for index, token in enumerate(fields[1:], start=1) if "=" in token), len(fields))
        master_index = first_param - 1
        if master_index <= 1:
            _unsupported(line, "instance", "cannot locate X-instance master", statement, strict, issues)
            return f"// unsupported SPICE instance: {statement}"
        nodes = fields[1:master_index]
        master = fields[master_index]
        params = " ".join(_spice_param(token) for token in fields[master_index + 1:])
        return f"{name} ({' '.join(nodes)}) {master} {params}".rstrip()
    _unsupported(line, "instance", "unsupported SPICE instance", statement, strict, issues)
    return f"// unsupported SPICE instance: {statement}"


def _spice_source_to_spectre(name: str, nodes: list[str], rest: str) -> str:
    master = "vsource" if name[:1].upper() == "V" else "isource"
    params: list[str] = []
    pulse = re.search(r"\bPULSE\s*\((.*)\)\s*$", rest, re.IGNORECASE)
    sine = re.search(r"\bSIN\s*\((.*)\)\s*$", rest, re.IGNORECASE)
    pwl = re.search(r"\bPWL\s*\((.*)\)\s*$", rest, re.IGNORECASE)
    waveform_start = len(rest)
    for match in (pulse, sine, pwl):
        if match:
            waveform_start = min(waveform_start, match.start())
    leading = _split_fields(rest[:waveform_start])
    index = 0
    while index < len(leading):
        token = leading[index].lower()
        if token in {"dc", "ac"} and index + 1 < len(leading):
            key = "dc" if token == "dc" else "mag"
            params.append(f"{key}={_spice_value(leading[index + 1])}")
            index += 2
        else:
            params.append(f"dc={_spice_value(leading[index])}")
            index += 1
    if pulse:
        values = _split_fields(pulse.group(1))
        keys = ("val0", "val1", "delay", "rise", "fall", "width", "period")
        params.append("type=pulse")
        params.extend(f"{key}={_spice_value(value)}" for key, value in zip(keys, values))
    elif sine:
        values = _split_fields(sine.group(1))
        keys = ("sinedc", "ampl", "freq", "delay")
        params.append("type=sine")
        params.extend(f"{key}={_spice_value(value)}" for key, value in zip(keys, values))
    elif pwl:
        values = _split_fields(pwl.group(1))
        params.extend(("type=pwl", "wave=[" + " ".join(_spice_value(value) for value in values) + "]"))
    return f"{name} ({' '.join(nodes)}) {master} {' '.join(params)}".rstrip()


def _spectre_statements(text: str) -> list[tuple[int, str]]:
    statements: list[tuple[int, str]] = []
    pending = ""
    pending_line = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.rstrip()
        if not pending:
            pending_line = line_number
        if stripped.endswith("\\"):
            pending += stripped[:-1] + " "
            continue
        pending += stripped
        if pending.strip():
            statements.append((pending_line, pending.strip()))
        pending = ""
    if pending.strip():
        statements.append((pending_line, pending.strip()))
    return statements


def _spice_statements(text: str) -> list[tuple[int, str]]:
    statements: list[tuple[int, str]] = []
    pending = ""
    pending_line = 0
    for line_number, raw in enumerate(text.splitlines(), 1):
        stripped = raw.rstrip()
        if stripped.lstrip().startswith("+") and pending:
            pending += " " + stripped.lstrip()[1:].strip()
            continue
        if pending:
            statements.append((pending_line, pending))
        pending = stripped.strip()
        pending_line = line_number
    if pending:
        statements.append((pending_line, pending))
    return statements


def _split_fields(text: str) -> list[str]:
    fields: list[str] = []
    buffer: list[str] = []
    stack: list[str] = []
    quote = ""
    pairs = {"(": ")", "[": "]", "{": "}"}
    for char in text:
        if quote:
            buffer.append(char)
            if char == quote:
                quote = ""
            continue
        if char in {'"', "'"}:
            quote = char
            buffer.append(char)
            continue
        if char in pairs:
            stack.append(pairs[char])
            buffer.append(char)
            continue
        if stack and char == stack[-1]:
            stack.pop()
            buffer.append(char)
            continue
        if char.isspace() and not stack:
            if buffer:
                fields.append("".join(buffer))
                buffer = []
            continue
        buffer.append(char)
    if buffer:
        fields.append("".join(buffer))
    return fields


def _split_inline_comment(text: str, marker: str) -> tuple[str, str]:
    quote = ""
    index = 0
    while index < len(text):
        char = text[index]
        if quote:
            if char == quote:
                quote = ""
            index += 1
            continue
        if char in {'"', "'"}:
            quote = char
            index += 1
            continue
        if text.startswith(marker, index):
            return text[:index].rstrip(), text[index + len(marker):].strip()
        index += 1
    return text, ""


def _param_dict(tokens: list[str]) -> dict[str, str]:
    params: dict[str, str] = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        params[key.lower()] = value
    return params


def _spectre_param(token: str) -> str:
    if "=" not in token:
        return token
    key, value = token.split("=", 1)
    return f"{key}={_spectre_value(value)}"


def _spice_param(token: str) -> str:
    if "=" not in token:
        return token
    key, value = token.split("=", 1)
    return f"{key}={_spice_value(value)}"


def _spectre_value(value: str) -> str:
    value = value.strip()
    if value.startswith("{") and value.endswith("}"):
        return value
    match = _NUMBER_RE.match(value)
    if match:
        suffix = match.group(1)
        base = float(value[:-1] if suffix else value)
        return f"{base * (_SPECTRE_SUFFIX[suffix] if suffix else 1):.12g}"
    return "{" + value + "}"


def _spice_value(value: str) -> str:
    value = value.strip().strip("{}")
    match = _SPICE_NUMBER_RE.match(value)
    if not match:
        return value
    base, suffix = match.groups()
    factor = _SPICE_SUFFIX[suffix.lower()] if suffix else 1.0
    return f"{float(base) * factor:.12g}"


def _prefixed_name(prefix: str, name: str) -> str:
    return name if name[:1].upper() == prefix.upper() else prefix + name


def _unsupported(
    line: int,
    code: str,
    message: str,
    statement: str,
    strict: bool,
    issues: list[TranslationIssue],
    *,
    prefix: str = "*",
) -> list[str]:
    issue = TranslationIssue(line, code, message, statement)
    if strict:
        raise TranslationError(issue)
    issues.append(issue)
    return [f"{prefix} unsupported [{code}]: {statement}"]
