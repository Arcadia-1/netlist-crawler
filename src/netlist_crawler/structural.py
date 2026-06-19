"""Lightweight structural parser and graph queries for SPICE-like netlists."""

from __future__ import annotations

import json
import re
import shlex
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
GLOBAL_NETS = {"0", "gnd", "GND", "vss", "VSS", "vdd", "VDD", "vss!", "vdd!"}
COMMON_NETS = GLOBAL_NETS | {
    "agnd", "AGND", "dgnd", "DGND",
    "avdd", "AVDD", "dvdd", "DVDD",
    "avss", "AVSS", "dvss", "DVSS",
    "sub", "SUB", "bulk", "BULK",
}


@dataclass(frozen=True)
class Device:
    """A parsed primitive or subcircuit instance."""

    name: str
    kind: str
    scope: str = ""
    model: str = ""
    pins: dict[str, str] = field(default_factory=dict)
    params: dict[str, str] = field(default_factory=dict)
    raw: str = ""


@dataclass
class SubcktDef:
    """A parsed subcircuit definition."""

    name: str
    ports: list[str] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)


@dataclass
class StructuralCircuit:
    """Device/net graph extracted from a SPICE-like netlist."""

    source: str
    topcell: str = ""
    subcircuits: list[str] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    directives: list[str] = field(default_factory=list)
    expanded: bool = False
    expand_depth: int = 0

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
            "topcell": self.topcell,
            "subcircuits": self.subcircuits,
            "expanded": self.expanded,
            "expand_depth": self.expand_depth,
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
                    "scope": device.scope,
                    "model": device.model,
                    "pins": device.pins,
                    "params": device.params,
                }
                for device in self.devices
            ],
            "nets": self.nets(),
        }


def parse_structural_netlist(
    path: Path,
    *,
    topcell: str | None = None,
    expand_depth: int = 0,
) -> StructuralCircuit:
    """Parse a pragmatic subset of SPICE/Spectre netlist structure."""
    subckts, top_devices, directives = _parse_netlist_model(path)
    circuit = StructuralCircuit(
        source=str(path),
        topcell=topcell or "",
        subcircuits=list(subckts),
        directives=directives,
        expanded=bool(topcell and expand_depth > 0),
        expand_depth=expand_depth,
    )

    if topcell:
        definition = subckts.get(topcell)
        if definition is None:
            return circuit
        if expand_depth > 0:
            circuit.devices = _expand_subckt(
                subckts,
                definition,
                prefix="",
                net_map={},
                depth=expand_depth,
            )
            return circuit
        circuit.devices = [
            _copy_device(device, scope=definition.name)
            for device in definition.devices
        ]
        return circuit

    devices = list(top_devices)
    for definition in subckts.values():
        devices.extend(_copy_device(device, scope=definition.name) for device in definition.devices)
    circuit.devices = devices
    return circuit


def list_subcircuits(path: Path) -> list[dict]:
    """Return subcircuit names, ports, and direct device counts."""
    subckts, _, _ = _parse_netlist_model(path)
    return [
        {
            "name": definition.name,
            "ports": definition.ports,
            "devices": len(definition.devices),
        }
        for definition in subckts.values()
    ]


def _parse_netlist_model(path: Path) -> tuple[dict[str, SubcktDef], list[Device], list[str]]:
    subckts: dict[str, SubcktDef] = {}
    top_devices: list[Device] = []
    directives: list[str] = []
    current_subckt = ""
    current_def: SubcktDef | None = None
    for line in _logical_lines(path):
        stripped = line.strip()
        if not stripped:
            continue
        header = _subckt_header(stripped)
        if header is not None:
            subckt_name, ports = header
            current_subckt = subckt_name
            current_def = SubcktDef(name=subckt_name, ports=ports)
            subckts[subckt_name] = current_def
            directives.append(stripped)
            continue
        if _is_ends(stripped):
            directives.append(stripped)
            current_subckt = ""
            current_def = None
            continue
        if stripped.startswith(".") or stripped.lower().startswith(("simulator ", "include ")):
            directives.append(stripped)
            continue
        device = _parse_device_line(stripped)
        if device is None:
            continue
        if current_def is None:
            top_devices.append(device)
            continue
        current_def.devices.append(_copy_device(device, scope=current_subckt))
    return subckts, top_devices, directives


def _expand_subckt(
    subckts: dict[str, SubcktDef],
    definition: SubcktDef,
    *,
    prefix: str,
    net_map: dict[str, str],
    depth: int,
) -> list[Device]:
    expanded: list[Device] = []
    for device in definition.devices:
        mapped_pins = {
            role: _map_net(net, prefix=prefix, net_map=net_map)
            for role, net in device.pins.items()
        }
        hier_name = f"{prefix}.{device.name}" if prefix else device.name
        child_def = subckts.get(device.model)
        if device.kind == "X" and child_def is not None and depth > 0:
            child_map = _instance_port_map(child_def, device, net_map=net_map, prefix=prefix)
            expanded.extend(
                _expand_subckt(
                    subckts,
                    child_def,
                    prefix=hier_name,
                    net_map=child_map,
                    depth=depth - 1,
                )
            )
            continue
        expanded.append(
            Device(
                name=hier_name,
                kind=device.kind,
                scope=definition.name,
                model=device.model,
                pins=mapped_pins,
                params=device.params,
                raw=device.raw,
            )
        )
    return expanded


def neighborhood(
    circuit: StructuralCircuit,
    net: str,
    depth: int,
    *,
    exclude_nets: set[str] | None = None,
    max_degree: int | None = None,
) -> dict:
    """Return a bounded bipartite neighborhood around a net."""
    exclude_nets = exclude_nets or set()
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
        if node != start and _is_excluded_net_node(node, exclude_nets):
            continue
        if node != start and _is_high_degree_net_node(adj, node, max_degree):
            continue
        for nb in sorted(adj.get(node, ())):
            if nb in seen:
                continue
            seen.add(nb)
            if nb.startswith("@"):
                device_names.add(nb[1:])
            elif nb.startswith("#"):
                net_names.add(nb[1:])
            if (
                not _is_excluded_net_node(nb, exclude_nets)
                and not _is_high_degree_net_node(adj, nb, max_degree)
            ):
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


def net_path(
    circuit: StructuralCircuit,
    source: str,
    target: str,
    *,
    exclude_nets: set[str] | None = None,
    max_degree: int | None = None,
) -> dict:
    """Find the shortest structural path between two nets."""
    exclude_nets = exclude_nets or set()
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
            if nb not in {start, goal} and _is_excluded_net_node(nb, exclude_nets):
                continue
            if nb not in {start, goal} and _is_high_degree_net_node(adj, nb, max_degree):
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
        "active-load": _detect_active_loads,
        "cascode": _detect_cascodes,
    }
    if wanted == "all":
        out: list[dict] = []
        for name in ("diff-pair", "current-mirror", "tail-source", "active-load", "cascode"):
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


def _detect_active_loads(circuit: StructuralCircuit) -> list[dict]:
    hits = []
    devices = circuit.device_by_name()
    for diff_pair in _detect_diff_pairs(circuit):
        drain_nets = set(diff_pair["evidence"]["drain_nets"])
        for mirror in _detect_current_mirrors(circuit):
            mirror_devices = [devices[name] for name in mirror["devices"]]
            loaded = [
                device.name
                for device in mirror_devices
                if device.pins.get("D") in drain_nets
            ]
            if len(loaded) < 2:
                continue
            hits.append({
                "pattern": "active_load",
                "devices": mirror["devices"],
                "evidence": {
                    "loaded_diff_pair": diff_pair["devices"],
                    "loaded_drain_nets": sorted(drain_nets),
                    "mirror_shared_gate": mirror["evidence"]["shared_gate"],
                    "mirror_shared_source": mirror["evidence"]["shared_source"],
                    "devices_loading_diff_pair_outputs": loaded,
                },
                "confidence": 0.84,
            })
    return hits


def _detect_cascodes(circuit: StructuralCircuit) -> list[dict]:
    hits = []
    mos = _mos_devices(circuit)
    for lower in mos:
        for upper in mos:
            if lower.name == upper.name:
                continue
            if lower.model != upper.model:
                continue
            intermediate = lower.pins.get("D")
            if not intermediate or intermediate != upper.pins.get("S"):
                continue
            if lower.pins.get("G") == upper.pins.get("G"):
                continue
            if intermediate in GLOBAL_NETS:
                continue
            upper_gate = upper.pins.get("G", "")
            if not _looks_like_bias_gate(upper_gate):
                continue
            confidence = 0.78
            confidence += 0.08
            hits.append({
                "pattern": "cascode",
                "devices": [lower.name, upper.name],
                "evidence": {
                    "lower_device": lower.name,
                    "upper_device": upper.name,
                    "intermediate_net": intermediate,
                    "lower_gate": lower.pins.get("G"),
                    "upper_gate": upper.pins.get("G"),
                    "output_net": upper.pins.get("D"),
                    "shared_model": lower.model,
                },
                "confidence": round(min(confidence, 0.9), 2),
            })
    return hits


def _looks_like_bias_gate(net: str) -> bool:
    n = net.lower()
    return "bias" in n or n.startswith(("vb", "vcas", "vbn", "vbp"))


def _logical_lines(path: Path, *, seen: set[Path] | None = None) -> Iterable[str]:
    seen = seen or set()
    resolved = path.resolve()
    if resolved in seen:
        return
    seen.add(resolved)

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
            include = _include_path(current, base_dir=path.parent)
            if include and include.exists():
                yield from _logical_lines(include, seen=seen)
        current = line
    if current:
        yield current
        include = _include_path(current, base_dir=path.parent)
        if include and include.exists():
            yield from _logical_lines(include, seen=seen)


def _parse_device_line(line: str) -> Device | None:
    tokens = _tokenize_instance(line)
    if len(tokens) < 2:
        return None
    name = tokens[0]
    prefix = name[0].upper()
    params = _parse_params(tokens[1:])

    if prefix == "X":
        named = _parse_named_x_instance(tokens)
        if named is not None:
            return named
        node_tokens = _leading_node_tokens(tokens[1:])
        if len(node_tokens) < 2:
            return None
        nets = node_tokens[:-1]
        model = node_tokens[-1]
        return Device(
            name=name,
            kind="X",
            scope="",
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
        scope="",
        model=model,
        pins={role: net for role, net in zip(roles, nets)},
        params=params,
        raw=line,
    )


def _parse_named_x_instance(tokens: list[str]) -> Device | None:
    body = tokens[1:]
    model_idx = None
    for idx in range(len(body) - 1, -1, -1):
        if "=" not in body[idx]:
            model_idx = idx
            break
    if model_idx is None or model_idx == 0:
        return None

    named_pins: dict[str, str] = {}
    for token in body[:model_idx]:
        if "=" not in token:
            return None
        key, value = token.split("=", 1)
        if not key or not value:
            return None
        named_pins[key] = value
    if not named_pins:
        return None
    return Device(
        name=tokens[0],
        kind="X",
        scope="",
        model=body[model_idx],
        pins=named_pins,
        params=_parse_params(body[model_idx + 1:]),
        raw=" ".join(tokens),
    )


def _copy_device(
    device: Device,
    *,
    scope: str | None = None,
    name: str | None = None,
    pins: dict[str, str] | None = None,
) -> Device:
    return Device(
        name=name or device.name,
        kind=device.kind,
        scope=device.scope if scope is None else scope,
        model=device.model,
        pins=device.pins if pins is None else pins,
        params=device.params,
        raw=device.raw,
    )


def _instance_port_map(
    definition: SubcktDef,
    instance: Device,
    *,
    net_map: dict[str, str],
    prefix: str,
) -> dict[str, str]:
    mapped: dict[str, str] = {}
    for idx, port in enumerate(definition.ports, start=1):
        actual = _get_instance_pin(instance, port, str(idx))
        if actual is None:
            continue
        mapped[port] = _map_net(actual, prefix=prefix, net_map=net_map)
    return mapped


def _get_instance_pin(instance: Device, port: str, positional_key: str) -> str | None:
    if port in instance.pins:
        return instance.pins[port]
    for key, value in instance.pins.items():
        if key.lower() == port.lower():
            return value
    return instance.pins.get(positional_key)


def _map_net(net: str, *, prefix: str, net_map: dict[str, str]) -> str:
    if net in net_map:
        return net_map[net]
    if not prefix or net in GLOBAL_NETS:
        return net
    return f"{prefix}.{net}"


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


def _is_excluded_net_node(node: str, exclude_nets: set[str]) -> bool:
    return node.startswith("#") and node[1:] in exclude_nets


def _is_high_degree_net_node(
    adj: dict[str, set[str]],
    node: str,
    max_degree: int | None,
) -> bool:
    return (
        max_degree is not None
        and max_degree >= 0
        and node.startswith("#")
        and len(adj.get(node, ())) > max_degree
    )


def _include_path(line: str, *, base_dir: Path) -> Path | None:
    try:
        tokens = shlex.split(line, comments=False, posix=True)
    except ValueError:
        return None
    if len(tokens) < 2:
        return None
    if tokens[0].lower() not in {".include", "include", ".inc", "inc"}:
        return None
    target = Path(tokens[1])
    if not target.is_absolute():
        target = base_dir / target
    return target


def _subckt_header(line: str) -> tuple[str, list[str]] | None:
    tokens = line.split()
    if len(tokens) >= 2 and tokens[0].lower() in {".subckt", "subckt"}:
        ports = []
        for token in tokens[2:]:
            if "=" in token:
                break
            if token.lower() in {"params:", "parameters:"}:
                break
            ports.append(token)
        return tokens[1], ports
    return None


def _is_ends(line: str) -> bool:
    token = line.split(maxsplit=1)[0].lower()
    return token in {".ends", "ends"}
