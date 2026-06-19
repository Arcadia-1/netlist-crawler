"""Lightweight structural parser and graph queries for SPICE-like netlists."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable


PIN_ROLES: dict[str, tuple[str, ...]] = {
    "M": ("D", "G", "S", "B"),
    "R": ("1", "2"),
    "C": ("1", "2"),
    "L": ("1", "2"),
    "V": ("P", "N"),
    "I": ("P", "N"),
    "D": ("A", "K"),
    "Q": ("C", "B", "E", "S"),
}

_INSTANCE_WITH_PARENS = re.compile(r"^(\S+)\s*\((.*?)\)\s*(.*)$")


@dataclass(frozen=True)
class Device:
    """A parsed primitive or subcircuit instance."""

    name: str
    kind: str
    model: str = ""
    pins: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    raw: str = ""


@dataclass
class StructuralCircuit:
    """Device/net graph extracted from a SPICE-like netlist."""

    source: str
    devices: list[Device] = field(default_factory=list)
    directives: list[str] = field(default_factory=list)

    def nets(self) -> dict[str, list[str]]:
        nets: dict[str, list[str]] = defaultdict(list)
        for device in self.devices:
            for role, net in device.pins.items():
                nets[net].append(f"{device.name}.{role}")
        return dict(sorted(nets.items()))

    def device_by_name(self) -> dict[str, Device]:
        return {device.name: device for device in self.devices}

    def adjacency(self) -> dict[str, set[str]]:
        adj: dict[str, set[str]] = defaultdict(set)
        for device in self.devices:
            dev_node = f"@{device.name}"
            for net in device.pins.values():
                net_node = f"#{net}"
                adj[dev_node].add(net_node)
                adj[net_node].add(dev_node)
        return adj

    def summary(self) -> dict:
        nets = self.nets()
        kinds = Counter(device.kind for device in self.devices)
        high_degree = sorted(
            ((net, len(pins)) for net, pins in nets.items()),
            key=lambda item: (-item[1], item[0]),
        )
        return {
            "source": self.source,
            "devices": len(self.devices),
            "nets": len(nets),
            "directives": len(self.directives),
            "device_kinds": dict(sorted(kinds.items())),
            "top_nets": [
                {"net": net, "degree": degree}
                for net, degree in high_degree[:10]
            ],
        }

    def to_json_dict(self) -> dict:
        return {
            "source": self.source,
            "summary": self.summary(),
            "devices": [
                {
                    "name": device.name,
                    "kind": device.kind,
                    "model": device.model,
                    "pins": device.pins,
                    "params": device.params,
                }
                for device in self.devices
            ],
            "nets": self.nets(),
        }


def parse_structural_netlist(path: Path) -> StructuralCircuit:
    """Parse a pragmatic subset of SPICE/Spectre netlist structure."""
    circuit = StructuralCircuit(source=str(path))
    for line in _logical_lines(path):
        stripped = line.strip()
        if not stripped:
            continue
        if stripped.startswith(".") or stripped.lower().startswith(("simulator ", "include ")):
            circuit.directives.append(stripped)
            continue
        device = _parse_device_line(stripped)
        if device is not None:
            circuit.devices.append(device)
    return circuit


def neighborhood(circuit: StructuralCircuit, net: str, depth: int) -> dict:
    """Return a bounded bipartite neighborhood around a net."""
    start = f"#{net}"
    adj = circuit.adjacency()
    if start not in adj:
        return {"net": net, "found": False, "devices": [], "nets": []}

    seen = {start}
    q = deque([(start, 0)])
    device_names: set[str] = set()
    net_names: set[str] = {net}
    while q:
        node, dist = q.popleft()
        if dist >= depth * 2:
            continue
        for nb in sorted(adj.get(node, ())):
            if nb in seen:
                continue
            seen.add(nb)
            if nb.startswith("@"):
                device_names.add(nb[1:])
            elif nb.startswith("#"):
                net_names.add(nb[1:])
            q.append((nb, dist + 1))

    devices = circuit.device_by_name()
    return {
        "net": net,
        "found": True,
        "depth": depth,
        "devices": [
            {
                "name": name,
                "kind": devices[name].kind,
                "model": devices[name].model,
                "pins": devices[name].pins,
            }
            for name in sorted(device_names)
        ],
        "nets": sorted(net_names),
    }


def net_path(circuit: StructuralCircuit, source: str, target: str) -> dict:
    """Find the shortest structural path between two nets."""
    start = f"#{source}"
    goal = f"#{target}"
    adj = circuit.adjacency()
    if start not in adj or goal not in adj:
        return {
            "from": source,
            "to": target,
            "found": False,
            "reason": "missing endpoint",
        }

    parent: dict[str, str | None] = {start: None}
    q = deque([start])
    while q:
        node = q.popleft()
        if node == goal:
            break
        for nb in sorted(adj.get(node, ())):
            if nb in parent:
                continue
            parent[nb] = node
            q.append(nb)

    if goal not in parent:
        return {"from": source, "to": target, "found": False, "reason": "disconnected"}

    nodes = []
    cur: str | None = goal
    while cur is not None:
        nodes.append(cur)
        cur = parent[cur]
    nodes.reverse()
    return {
        "from": source,
        "to": target,
        "found": True,
        "path": [_display_node(node) for node in nodes],
    }


def detect_semantics(circuit: StructuralCircuit, pattern: str = "all") -> list[dict]:
    """Detect first-pass analog semantic patterns with explicit evidence."""
    wanted = pattern.lower().replace("_", "-")
    detectors = {
        "diff-pair": _detect_diff_pairs,
        "differential-pair": _detect_diff_pairs,
        "current-mirror": _detect_current_mirrors,
        "tail-source": _detect_tail_sources,
    }
    if wanted == "all":
        out: list[dict] = []
        for name in ("diff-pair", "current-mirror", "tail-source"):
            out.extend(detectors[name](circuit))
        return out
    if wanted not in detectors:
        raise ValueError(f"unsupported pattern: {pattern}")
    return detectors[wanted](circuit)


def explain_device(circuit: StructuralCircuit, device_name: str) -> dict:
    """Explain known semantic roles for one device."""
    devices = circuit.device_by_name()
    device = devices.get(device_name)
    if device is None:
        return {"device": device_name, "found": False, "roles": []}

    roles = []
    for hit in detect_semantics(circuit, "all"):
        if device_name in hit.get("devices", []):
            roles.append(hit)
    return {
        "device": device_name,
        "found": True,
        "kind": device.kind,
        "model": device.model,
        "pins": device.pins,
        "roles": roles,
    }


def dumps_json(data: dict) -> str:
    return json.dumps(data, indent=2, sort_keys=True)


def _mos_devices(circuit: StructuralCircuit) -> list[Device]:
    return [device for device in circuit.devices if device.kind == "M"]


def _detect_diff_pairs(circuit: StructuralCircuit) -> list[dict]:
    hits = []
    mos = _mos_devices(circuit)
    for i, left in enumerate(mos):
        for right in mos[i + 1:]:
            if left.model != right.model:
                continue
            if left.pins.get("S") != right.pins.get("S"):
                continue
            if left.pins.get("G") == right.pins.get("G"):
                continue
            if left.pins.get("D") == right.pins.get("D"):
                continue
            confidence = 0.82
            if left.pins.get("B") == right.pins.get("B"):
                confidence += 0.06
            hits.append({
                "pattern": "differential_pair",
                "devices": [left.name, right.name],
                "evidence": {
                    "shared_source": left.pins.get("S"),
                    "gate_nets": [left.pins.get("G"), right.pins.get("G")],
                    "drain_nets": [left.pins.get("D"), right.pins.get("D")],
                    "matched_model": left.model,
                    "bulk_nets": [left.pins.get("B"), right.pins.get("B")],
                },
                "confidence": round(min(confidence, 0.95), 2),
            })
    return hits


def _detect_current_mirrors(circuit: StructuralCircuit) -> list[dict]:
    hits = []
    mos = _mos_devices(circuit)
    for i, left in enumerate(mos):
        for right in mos[i + 1:]:
            if left.model != right.model:
                continue
            if left.pins.get("G") != right.pins.get("G"):
                continue
            if left.pins.get("S") != right.pins.get("S"):
                continue
            diode = []
            for device in (left, right):
                if device.pins.get("D") == device.pins.get("G"):
                    diode.append(device.name)
            if not diode:
                continue
            hits.append({
                "pattern": "current_mirror",
                "devices": [left.name, right.name],
                "evidence": {
                    "shared_gate": left.pins.get("G"),
                    "shared_source": left.pins.get("S"),
                    "matched_model": left.model,
                    "diode_connected_devices": diode,
                    "output_devices": [
                        device.name for device in (left, right) if device.name not in diode
                    ],
                },
                "confidence": 0.86 if len(diode) == 1 else 0.78,
            })
    return hits


def _detect_tail_sources(circuit: StructuralCircuit) -> list[dict]:
    hits = []
    diff_pairs = _detect_diff_pairs(circuit)
    devices = circuit.device_by_name()
    for pair in diff_pairs:
        shared_source = pair["evidence"]["shared_source"]
        for device in _mos_devices(circuit):
            if device.name in pair["devices"]:
                continue
            if device.pins.get("D") != shared_source:
                continue
            source = device.pins.get("S")
            bulk = device.pins.get("B")
            confidence = 0.74
            if source == bulk:
                confidence += 0.08
            gate = device.pins.get("G")
            if gate and "bias" in gate.lower():
                confidence += 0.08
            pair_devices = [devices[name].name for name in pair["devices"]]
            hits.append({
                "pattern": "tail_current_source",
                "devices": [device.name],
                "evidence": {
                    "drain_connected_to_diff_pair_source": shared_source,
                    "associated_diff_pair": pair_devices,
                    "gate_net": gate,
                    "source_net": source,
                    "bulk_net": bulk,
                },
                "confidence": round(min(confidence, 0.93), 2),
            })
    return hits


def _logical_lines(path: Path) -> Iterable[str]:
    current = ""
    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith(("*", "//", ";")):
            continue
        if line.startswith("+"):
            current += " " + line[1:].strip()
            continue
        if current:
            yield current
        current = line
    if current:
        yield current


def _parse_device_line(line: str) -> Device | None:
    tokens = _tokenize_instance(line)
    if len(tokens) < 2:
        return None
    name = tokens[0]
    prefix = name[0].upper()
    params = _parse_params(tokens[1:])

    if prefix == "X":
        node_tokens = _leading_node_tokens(tokens[1:])
        if len(node_tokens) < 2:
            return None
        nets = node_tokens[:-1]
        model = node_tokens[-1]
        return Device(
            name=name,
            kind="X",
            model=model,
            pins={str(i + 1): net for i, net in enumerate(nets)},
            params=params,
            raw=line,
        )

    roles = PIN_ROLES.get(prefix)
    if roles is None:
        return None
    if len(tokens) < 1 + len(roles):
        return None
    nets = tokens[1:1 + len(roles)]
    model_idx = 1 + len(roles)
    model = tokens[model_idx] if model_idx < len(tokens) and "=" not in tokens[model_idx] else ""
    return Device(
        name=name,
        kind=prefix,
        model=model,
        pins={role: net for role, net in zip(roles, nets)},
        params=params,
        raw=line,
    )


def _tokenize_instance(line: str) -> list[str]:
    match = _INSTANCE_WITH_PARENS.match(line)
    if not match:
        return line.split()
    name, pins, rest = match.groups()
    return [name, *pins.split(), *rest.split()]


def _leading_node_tokens(tokens: list[str]) -> list[str]:
    out = []
    for token in tokens:
        if "=" in token:
            break
        out.append(token)
    return out


def _parse_params(tokens: list[str]) -> dict[str, str]:
    params = {}
    for token in tokens:
        if "=" not in token:
            continue
        key, value = token.split("=", 1)
        params[key] = value
    return params


def _display_node(node: str) -> str:
    if node.startswith("#"):
        return node[1:]
    if node.startswith("@"):
        return node[1:]
    return node
