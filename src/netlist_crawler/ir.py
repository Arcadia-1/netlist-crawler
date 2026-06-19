"""Persistent IR and annotation checks for Netlist Crawler workflows."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

from .structural import (
    COMMON_NETS,
    Device,
    StructuralCircuit,
    annotate_circuit,
    list_subcircuits,
    parse_structural_netlist,
)


IR_SCHEMA = "netlist-crawler.ir.v1"
RULE_SOURCE = "netlist-crawler.rules"
ACTIVE_STATUSES = {"candidate", "confirmed", "unknown", "needs_review"}
DISPOSITION_LABELS = {
    "internal",
    "unclassified_internal",
    "parasitic_only",
    "unknown_needs_review",
    "irrelevant",
}

_NET_LABEL_CLASS = {
    "bias": "bias",
    "bias_or_mirror_control": "mirror_control",
    "differential_input": "signal_input",
    "input_candidate": "signal_input",
    "loaded_output": "signal_output",
    "output_candidate": "signal_output",
    "supply": "supply",
    "tail": "tail",
    "cascode_internal": "internal",
    **{label: label for label in DISPOSITION_LABELS},
}


def is_ir_file(path: Path) -> bool:
    """Return true when a JSON file looks like Netlist Crawler IR."""
    if path.suffix.lower() not in {".json", ".nlc"} and not path.name.endswith(".nlc.json"):
        return False
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return payload.get("schema") == IR_SCHEMA


def read_ir(path: Path) -> dict:
    """Read a persistent IR document."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != IR_SCHEMA:
        raise ValueError(f"unsupported IR schema: {payload.get('schema')!r}")
    return payload


def write_ir(ir: dict, path: Path) -> None:
    """Write a persistent IR document with stable formatting."""
    path.write_text(json.dumps(ir, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def export_ir(
    path: Path,
    *,
    topcell: str | None = None,
    expand_depth: int = 0,
    include_rule_annotations: bool = True,
) -> dict:
    """Parse a netlist into the persistent workflow IR."""
    text = path.read_text(encoding="utf-8", errors="replace")
    circuit = parse_structural_netlist(path, topcell=topcell, expand_depth=expand_depth)
    nets = circuit.nets()
    annotations = _rule_annotations(circuit) if include_rule_annotations else []
    return {
        "schema": IR_SCHEMA,
        "source": {
            "path": str(path),
            "dialect": _detect_dialect(path, text),
            "content_hash": hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest(),
            "includes": _include_directives(circuit.directives),
        },
        "view": {
            "topcell": circuit.topcell,
            "expanded": circuit.expanded,
            "expand_depth": circuit.expand_depth,
        },
        "raw": {
            "lines": text.splitlines(),
        },
        "symbols": {
            "parameters": circuit.parameters,
            "subcircuits": list_subcircuits(path),
            "directives": circuit.directives,
        },
        "instances": [
            {
                "id": device.name,
                "kind": device.kind,
                "scope": device.scope,
                "model": device.model,
                "pins": device.pins,
                "params": device.params,
                "raw": device.raw,
            }
            for device in circuit.devices
        ],
        "nets": [
            {
                "id": net,
                "degree": len(pins),
                "pins": pins,
            }
            for net, pins in nets.items()
        ],
        "edges": [
            {
                "id": f"edge:{device.name}:{role}:{net}",
                "device": device.name,
                "net": net,
                "role": role,
                "type": "pin",
            }
            for device in circuit.devices
            for role, net in device.pins.items()
        ],
        "annotations": annotations,
    }


def circuit_from_ir(ir: dict) -> StructuralCircuit:
    """Rebuild the structural circuit view from IR facts."""
    view = ir.get("view", {})
    symbols = ir.get("symbols", {})
    circuit = StructuralCircuit(
        source=ir.get("source", {}).get("path", ""),
        topcell=view.get("topcell", ""),
        subcircuits=[
            item.get("name", "")
            for item in symbols.get("subcircuits", [])
            if item.get("name")
        ],
        directives=symbols.get("directives", []),
        parameters=symbols.get("parameters", {}),
        expanded=bool(view.get("expanded", False)),
        expand_depth=int(view.get("expand_depth", 0) or 0),
    )
    circuit.devices = [
        Device(
            name=item["id"],
            kind=item.get("kind", ""),
            scope=item.get("scope", ""),
            model=item.get("model", ""),
            pins=item.get("pins", {}),
            params=item.get("params", {}),
            raw=item.get("raw", ""),
        )
        for item in ir.get("instances", [])
        if item.get("id")
    ]
    return circuit


def validate_ir(ir: dict) -> dict:
    """Check schema and fact-layer referential integrity."""
    errors: list[dict] = []
    warnings: list[dict] = []
    if ir.get("schema") != IR_SCHEMA:
        errors.append(_issue("schema", f"expected {IR_SCHEMA}", path="schema"))

    instances = ir.get("instances", [])
    nets = ir.get("nets", [])
    edges = ir.get("edges", [])
    annotations = ir.get("annotations", [])
    instance_ids = _ids(instances, "instance", errors)
    net_ids = _ids(nets, "net", errors)

    pin_refs = {
        (item.get("id"), role, net)
        for item in instances
        for role, net in (item.get("pins") or {}).items()
    }
    edge_refs = set()
    for edge in edges:
        device = edge.get("device")
        net = edge.get("net")
        role = edge.get("role")
        if device not in instance_ids:
            errors.append(_issue("edge_reference", f"unknown device {device!r}", edge=edge.get("id")))
        if net not in net_ids:
            errors.append(_issue("edge_reference", f"unknown net {net!r}", edge=edge.get("id")))
        edge_refs.add((device, role, net))

    for ref in sorted(pin_refs - edge_refs):
        warnings.append(_issue("missing_edge", f"pin has no matching edge: {ref!r}"))
    for ref in sorted(edge_refs - pin_refs):
        warnings.append(_issue("extra_edge", f"edge has no matching instance pin: {ref!r}"))

    for annotation in annotations:
        _validate_annotation(annotation, instance_ids, net_ids, errors)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "instances": len(instances),
            "nets": len(nets),
            "edges": len(edges),
            "annotations": len(annotations),
        },
    }


def annotation_coverage(ir: dict) -> dict:
    """Report direct or group annotation coverage for nets and devices."""
    device_ids = sorted(item["id"] for item in ir.get("instances", []) if item.get("id"))
    net_ids = sorted(item["id"] for item in ir.get("nets", []) if item.get("id"))
    covered = _covered_targets(ir.get("annotations", []))
    covered_devices = sorted(set(device_ids) & covered["device"])
    covered_nets = sorted(set(net_ids) & covered["net"])
    missing_devices = sorted(set(device_ids) - set(covered_devices))
    missing_nets = sorted(set(net_ids) - set(covered_nets))
    return {
        "complete": not missing_devices and not missing_nets,
        "devices": {
            "total": len(device_ids),
            "covered": len(covered_devices),
            "missing": missing_devices,
        },
        "nets": {
            "total": len(net_ids),
            "covered": len(covered_nets),
            "missing": missing_nets,
        },
    }


def check_annotations(ir: dict) -> dict:
    """Validate annotations and flag coverage, conflicts, and weak consistency."""
    validation = validate_ir(ir)
    coverage = annotation_coverage(ir)
    conflicts = _annotation_conflicts(ir)
    consistency = _structural_consistency_warnings(ir)
    errors = list(validation["errors"]) + conflicts
    warnings = list(validation["warnings"]) + consistency
    if not coverage["complete"]:
        warnings.append(_issue("coverage", "some nets or devices lack annotations"))
    return {
        "ok": not errors and coverage["complete"],
        "valid_ir": validation["valid"],
        "coverage": coverage,
        "errors": errors,
        "warnings": warnings,
        "summary": validation["summary"],
    }


def _rule_annotations(circuit: StructuralCircuit) -> list[dict]:
    annotation = annotate_circuit(circuit)
    out: list[dict] = []
    counter = 0
    for net in annotation["nets"]:
        for label in net["labels"]:
            out.append(_annotation(
                counter,
                target={"type": "net", "id": net["name"]},
                label=label["label"],
                confidence=label.get("confidence", 0.0),
                evidence=label.get("evidence", {}),
            ))
            counter += 1
    for index, match in enumerate(annotation["patterns"]):
        out.append(_annotation(
            counter,
            target={
                "type": "group",
                "id": f"group:{match['pattern']}:{index}",
                "members": [
                    {"type": "device", "id": device}
                    for device in match.get("devices", [])
                ],
            },
            label=match["pattern"],
            confidence=match.get("confidence", 0.0),
            evidence=match.get("evidence", {}),
        ))
        counter += 1
    return out


def _annotation(
    counter: int,
    *,
    target: dict,
    label: str,
    confidence: float,
    evidence: dict,
) -> dict:
    return {
        "id": f"ann:rules:{counter}",
        "target": target,
        "label": label,
        "status": "candidate",
        "source": RULE_SOURCE,
        "confidence": confidence,
        "evidence": evidence,
    }


def _detect_dialect(path: Path, text: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".scs" or "simulator lang=spectre" in text.lower():
        return "spectre"
    if suffix == ".dspf":
        return "dspf"
    if suffix == ".mrpp":
        return "mrpp"
    if suffix in {".sp", ".spi", ".cir", ".ckt"}:
        return "spice"
    return "unknown"


def _include_directives(directives: list[str]) -> list[str]:
    return [
        directive
        for directive in directives
        if directive.split(maxsplit=1)[0].lower() in {".include", "include", ".inc", "inc"}
    ]


def _ids(items: list[dict], kind: str, errors: list[dict]) -> set[str]:
    seen = set()
    for item in items:
        item_id = item.get("id")
        if not item_id:
            errors.append(_issue("missing_id", f"{kind} is missing id"))
            continue
        if item_id in seen:
            errors.append(_issue("duplicate_id", f"duplicate {kind} id {item_id!r}"))
        seen.add(item_id)
    return seen


def _validate_annotation(
    annotation: dict,
    instance_ids: set[str],
    net_ids: set[str],
    errors: list[dict],
) -> None:
    target = annotation.get("target") or {}
    target_type = target.get("type")
    target_id = target.get("id")
    if target_type == "device":
        if target_id not in instance_ids:
            errors.append(_issue("annotation_reference", f"unknown device {target_id!r}", annotation=annotation.get("id")))
    elif target_type == "net":
        if target_id not in net_ids:
            errors.append(_issue("annotation_reference", f"unknown net {target_id!r}", annotation=annotation.get("id")))
    elif target_type == "group":
        for member in target.get("members", []):
            member_type = member.get("type")
            member_id = member.get("id")
            if member_type == "device" and member_id not in instance_ids:
                errors.append(_issue("annotation_reference", f"unknown group device {member_id!r}", annotation=annotation.get("id")))
            elif member_type == "net" and member_id not in net_ids:
                errors.append(_issue("annotation_reference", f"unknown group net {member_id!r}", annotation=annotation.get("id")))
            elif member_type not in {"device", "net"}:
                errors.append(_issue("annotation_reference", f"unknown group member type {member_type!r}", annotation=annotation.get("id")))
    else:
        errors.append(_issue("annotation_reference", f"unknown target type {target_type!r}", annotation=annotation.get("id")))


def _covered_targets(annotations: list[dict]) -> dict[str, set[str]]:
    covered = {"device": set(), "net": set()}
    for annotation in annotations:
        if annotation.get("status", "candidate") not in ACTIVE_STATUSES:
            continue
        target = annotation.get("target") or {}
        target_type = target.get("type")
        if target_type in covered and target.get("id"):
            covered[target_type].add(target["id"])
        if target_type == "group":
            for member in target.get("members", []):
                member_type = member.get("type")
                member_id = member.get("id")
                if member_type in covered and member_id:
                    covered[member_type].add(member_id)
    return covered


def _annotation_conflicts(ir: dict) -> list[dict]:
    labels_by_target = _labels_by_target(ir.get("annotations", []))
    conflicts = []
    for target, labels in labels_by_target.items():
        classes = {_normalize_label(label) for label in labels}
        classes.discard("")
        if "supply" in classes and classes & {"signal_input", "signal_output", "bias", "tail"}:
            conflicts.append(_issue("annotation_conflict", f"{target} mixes supply with {sorted(classes)}"))
        if "parasitic_only" in classes and classes - {"parasitic_only"}:
            conflicts.append(_issue("annotation_conflict", f"{target} mixes parasitic_only with {sorted(classes)}"))
    return conflicts


def _structural_consistency_warnings(ir: dict) -> list[dict]:
    labels_by_target = _labels_by_target(ir.get("annotations", []))
    nets = {item["id"]: item for item in ir.get("nets", []) if item.get("id")}
    warnings = []
    for net, item in nets.items():
        classes = {_normalize_label(label) for label in labels_by_target.get(("net", net), set())}
        roles = _pin_roles(item.get("pins", []))
        if "supply" in classes and net not in COMMON_NETS:
            warnings.append(_issue("annotation_consistency", f"net {net!r} is marked supply but is not a common rail name"))
        if "bias" in classes and not roles.get("G") and not _looks_like_bias(net):
            warnings.append(_issue("annotation_consistency", f"net {net!r} is marked bias but has no gate pins"))
        if "signal_input" in classes and not roles.get("G"):
            warnings.append(_issue("annotation_consistency", f"net {net!r} is marked signal_input but has no gate pins"))
        if "signal_output" in classes and not roles.get("D"):
            warnings.append(_issue("annotation_consistency", f"net {net!r} is marked signal_output but has no drain pins"))
    return warnings


def _labels_by_target(annotations: list[dict]) -> dict[tuple[str, str], set[str]]:
    labels: dict[tuple[str, str], set[str]] = defaultdict(set)
    for annotation in annotations:
        if annotation.get("status", "candidate") not in ACTIVE_STATUSES:
            continue
        label = annotation.get("label")
        if not label:
            continue
        target = annotation.get("target") or {}
        target_type = target.get("type")
        target_id = target.get("id")
        if target_type in {"device", "net"} and target_id:
            labels[(target_type, target_id)].add(label)
        elif target_type == "group":
            for member in target.get("members", []):
                member_type = member.get("type")
                member_id = member.get("id")
                if member_type in {"device", "net"} and member_id:
                    labels[(member_type, member_id)].add(label)
    return labels


def _normalize_label(label: str) -> str:
    return _NET_LABEL_CLASS.get(label, label)


def _pin_roles(pins: list[str]) -> dict[str, int]:
    roles: dict[str, int] = defaultdict(int)
    for pin in pins:
        if "." not in pin:
            continue
        _, role = pin.rsplit(".", 1)
        roles[role] += 1
    return dict(roles)


def _looks_like_bias(net: str) -> bool:
    lower = net.lower()
    return "bias" in lower or lower.startswith(("vb", "vcas", "vbn", "vbp"))


def _issue(kind: str, message: str, **extra: Any) -> dict:
    return {"kind": kind, "message": message, **extra}
