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
    "B": ("P", "N"),
    "E": ("OUTP", "OUTN", "INP", "INN"),
    "F": ("OUTP", "OUTN"),
    "G": ("OUTP", "OUTN", "INP", "INN"),
    "H": ("OUTP", "OUTN"),
    "K": ("L1", "L2"),
    "W": ("P", "N"),
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
    params: dict[str, str] = field(default_factory=dict)
    devices: list[Device] = field(default_factory=list)


@dataclass
class HierarchyInstance:
    """A subcircuit instance boundary fact preserved during expansion."""

    id: str
    name: str
    kind: str
    definition: str
    scope: str
    expanded: bool
    instance_path: list[str]
    port_map: dict[str, str]
    member_prefix: str
    members: dict[str, list[str]] = field(default_factory=dict)
    pins: dict[str, str] = field(default_factory=dict)
    raw: str = ""


@dataclass
class StructuralCircuit:
    """Device/net graph extracted from a SPICE-like netlist."""

    source: str
    topcell: str = ""
    subcircuits: list[str] = field(default_factory=list)
    devices: list[Device] = field(default_factory=list)
    directives: list[str] = field(default_factory=list)
    parameters: dict[str, str] = field(default_factory=dict)
    expanded: bool = False
    expand_depth: int = 0
    hierarchy_instances: list[HierarchyInstance] = field(default_factory=list)

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
            "parameters": self.parameters,
            "device_kinds": dict(sorted(kinds.items())),
            "top_nets": [
                {"net": net, "degree": degree}
                for net, degree in high_degree[:10]
            ],
        }

    def to_json_dict(self) -> dict:
        hierarchy_instances = sorted(
            self.hierarchy_instances,
            key=lambda item: (len(item.instance_path), item.instance_path, item.id),
        )
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
            "hierarchy": {
                "instances": [
                    {
                        "id": item.id,
                        "name": item.name,
                        "kind": item.kind,
                        "definition": item.definition,
                        "scope": item.scope,
                        "expanded": item.expanded,
                        "instance_path": item.instance_path,
                        "port_map": item.port_map,
                        "member_prefix": item.member_prefix,
                        "members": item.members,
                        "pins": item.pins,
                        "raw": item.raw,
                    }
                    for item in hierarchy_instances
                ]
            },
        }


def parse_structural_netlist(
    path: Path,
    *,
    topcell: str | None = None,
    expand_depth: int = 0,
) -> StructuralCircuit:
    """Parse a pragmatic subset of SPICE/Spectre netlist structure."""
    subckts, top_devices, directives, parameters = _parse_netlist_model(path)
    circuit = StructuralCircuit(
        source=str(path),
        topcell=topcell or "",
        subcircuits=list(subckts),
        directives=directives,
        parameters=parameters,
        expanded=bool(topcell and expand_depth > 0),
        expand_depth=expand_depth,
    )

    if topcell:
        definition = subckts.get(topcell)
        if definition is None:
            return circuit
        if expand_depth > 0:
            hierarchy: list[HierarchyInstance] = []
            circuit.devices = _expand_subckt(
                subckts,
                definition,
                prefix="",
                net_map={},
                depth=expand_depth,
                hierarchy=hierarchy,
            )
            circuit.hierarchy_instances = hierarchy
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
    subckts, _, _, _ = _parse_netlist_model(path)
    return [
        {
            "name": definition.name,
            "ports": definition.ports,
            "params": definition.params,
            "devices": len(definition.devices),
        }
        for definition in subckts.values()
    ]


def _parse_netlist_model(path: Path) -> tuple[dict[str, SubcktDef], list[Device], list[str], dict[str, str]]:
    subckts: dict[str, SubcktDef] = {}
    top_devices: list[Device] = []
    directives: list[str] = []
    parameters: dict[str, str] = {}
    current_subckt = ""
    current_def: SubcktDef | None = None
    lines = list(_logical_lines(path))
    known_subckts = {
        header[0]
        for line in lines
        if (header := _subckt_header(line.strip())) is not None
    }
    for line in lines:
        stripped = line.strip()
        if not stripped:
            continue
        header = _subckt_header(stripped)
        if header is not None:
            subckt_name, ports, subckt_params = header
            current_subckt = subckt_name
            current_def = SubcktDef(name=subckt_name, ports=ports, params=subckt_params)
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
            parameters.update(_param_directive(stripped))
            continue
        device = _parse_device_line(stripped, known_subckts=known_subckts)
        if device is None:
            continue
        if current_def is None:
            top_devices.append(device)
            continue
        current_def.devices.append(_copy_device(device, scope=current_subckt))
    return subckts, top_devices, directives, parameters


def _expand_subckt(
    subckts: dict[str, SubcktDef],
    definition: SubcktDef,
    *,
    prefix: str,
    net_map: dict[str, str],
    depth: int,
    hierarchy: list[HierarchyInstance],
) -> list[Device]:
    expanded: list[Device] = []
    for device in definition.devices:
        mapped_pins = {
            role: _map_net(net, prefix=prefix, net_map=net_map)
            for role, net in device.pins.items()
        }
        hier_name = f"{prefix}.{device.name}" if prefix else device.name
        child_def = subckts.get(device.model)
        if device.kind == "X" and child_def is not None:
            child_map = _instance_port_map(child_def, device, net_map=net_map, prefix=prefix)
            is_expanded = depth > 0
            member_devices: list[str] = []
            member_nets: list[str] = []
            if is_expanded:
                child_devices = _expand_subckt(
                    subckts,
                    child_def,
                    prefix=hier_name,
                    net_map=child_map,
                    depth=depth - 1,
                    hierarchy=hierarchy,
                )
                expanded.extend(child_devices)
                member_devices = [child.name for child in child_devices]
                member_nets = sorted(
                    {
                        net
                        for child in child_devices
                        for net in child.pins.values()
                        if net.startswith(f"{hier_name}.")
                    }
                )
            hierarchy.append(
                HierarchyInstance(
                    id=hier_name,
                    name=device.name,
                    kind=device.kind,
                    definition=child_def.name,
                    scope=definition.name,
                    expanded=is_expanded,
                    instance_path=hier_name.split("."),
                    port_map=child_map,
                    member_prefix=f"{hier_name}.",
                    members={"devices": member_devices, "nets": member_nets},
                    pins=mapped_pins,
                    raw=device.raw,
                )
            )
            if is_expanded:
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


def explain_net(circuit: StructuralCircuit, net_name: str) -> dict:
    """Explain structural and semantic evidence for one net."""
    return _explain_net_from_annotation(circuit, net_name, annotate_circuit(circuit))


def _explain_net_from_annotation(
    circuit: StructuralCircuit,
    net_name: str,
    annotation: dict,
) -> dict:
    nets = circuit.nets()
    pins = nets.get(net_name)
    if pins is None:
        return {"net": net_name, "found": False, "labels": [], "devices": []}

    label_map = {
        net["name"]: net["labels"]
        for net in annotation["nets"]
    }
    devices = circuit.device_by_name()
    connected = []
    pin_roles: Counter[str] = Counter()
    device_kinds: Counter[str] = Counter()
    for pin in pins:
        device_name, role = pin.rsplit(".", 1)
        device = devices[device_name]
        pin_roles[role] += 1
        device_kinds[device.kind] += 1
        connected.append({
            "device": device.name,
            "kind": device.kind,
            "model": device.model,
            "role": role,
            "pins": device.pins,
        })

    labels = label_map.get(net_name, [])
    classes = _net_classes_from_labels(net_name, labels, pin_roles)
    return {
        "net": net_name,
        "found": True,
        "degree": len(pins),
        "pins": pins,
        "pin_roles": dict(sorted(pin_roles.items())),
        "device_kinds": dict(sorted(device_kinds.items())),
        "labels": labels,
        "classes": classes,
        "devices": connected,
    }


def classify_path(
    circuit: StructuralCircuit,
    source: str,
    target: str,
    *,
    exclude_nets: set[str] | None = None,
    max_degree: int | None = None,
) -> dict:
    """Find a path and classify its likely analog intent."""
    path = net_path(
        circuit,
        source,
        target,
        exclude_nets=exclude_nets,
        max_degree=max_degree,
    )
    if not path["found"]:
        return {
            **path,
            "path_type": "unknown",
            "confidence": 0.0,
            "evidence": {"reason": path["reason"]},
        }

    annotation = annotate_circuit(circuit)
    circuit_nets = circuit.nets()
    devices = circuit.device_by_name()
    net_nodes = [node for node in path["path"] if node in circuit_nets]
    device_nodes = [node for node in path["path"] if node in devices]
    net_classes = {
        net: _explain_net_from_annotation(circuit, net, annotation).get("classes", [])
        for net in net_nodes
    }

    path_type, confidence, reasons = _classify_path_evidence(
        source,
        target,
        net_classes,
        device_nodes,
    )
    return {
        **path,
        "path_type": path_type,
        "confidence": confidence,
        "evidence": {
            "net_classes": net_classes,
            "device_nodes": device_nodes,
            "reasons": reasons,
        },
    }


def export_graph(circuit: StructuralCircuit, *, include_semantics: bool = True) -> dict:
    """Export a stable bipartite graph for downstream workflows."""
    annotations = annotate_circuit(circuit) if include_semantics else None
    device_roles = {}
    net_labels = {}
    patterns = []
    if annotations is not None:
        device_roles = {
            device["name"]: device["roles"]
            for device in annotations["devices"]
        }
        net_labels = {
            net["name"]: net["labels"]
            for net in annotations["nets"]
        }
        patterns = annotations["patterns"]

    nodes = []
    edges = []
    for device in circuit.devices:
        nodes.append({
            "id": f"device:{device.name}",
            "type": "device",
            "name": device.name,
            "kind": device.kind,
            "model": device.model,
            "scope": device.scope,
            "params": device.params,
            "roles": device_roles.get(device.name, []),
        })
        for role, net in device.pins.items():
            edges.append({
                "source": f"device:{device.name}",
                "target": f"net:{net}",
                "type": "pin",
                "role": role,
            })

    for net, pins in circuit.nets().items():
        labels = net_labels.get(net, [])
        nodes.append({
            "id": f"net:{net}",
            "type": "net",
            "name": net,
            "degree": len(pins),
            "pins": pins,
            "labels": labels,
            "classes": _net_classes_from_labels(net, labels, _pin_roles_from_pins(pins)),
        })

    return {
        "schema": "netlist-crawler.graph.v1",
        "source": circuit.source,
        "summary": circuit.summary(),
        "nodes": sorted(nodes, key=lambda item: item["id"]),
        "edges": sorted(edges, key=lambda item: (item["source"], item["target"], item["role"])),
        "patterns": patterns,
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


def annotate_circuit(circuit: StructuralCircuit) -> dict:
    """Return device roles and net labels derived from structural evidence."""
    matches = detect_semantics(circuit, "all")
    device_roles: dict[str, list[dict]] = {
        device.name: [] for device in circuit.devices
    }
    net_labels: dict[str, list[dict]] = {
        net: [] for net in circuit.nets()
    }

    for match in matches:
        for device in match["devices"]:
            device_roles.setdefault(device, []).append({
                "role": match["pattern"],
                "confidence": match["confidence"],
            })
        _apply_net_labels_from_match(net_labels, match)

    for net, pins in circuit.nets().items():
        if net in COMMON_NETS:
            _add_net_label(net_labels, net, "supply", 0.95, {"reason": "common net name"})
        gate_pins = [pin for pin in pins if pin.endswith(".G")]
        non_gate_pins = [pin for pin in pins if not pin.endswith(".G")]
        if gate_pins and not non_gate_pins and not _looks_like_bias_gate(net):
            _add_net_label(
                net_labels,
                net,
                "input_candidate",
                0.66,
                {"gate_pins": gate_pins},
            )
        if _looks_like_bias_gate(net):
            _add_net_label(
                net_labels,
                net,
                "bias",
                0.78,
                {"reason": "bias-like net name"},
            )

    return {
        "source": circuit.source,
        "topcell": circuit.topcell,
        "devices": [
            {
                "name": device.name,
                "kind": device.kind,
                "model": device.model,
                "pins": device.pins,
                "roles": device_roles.get(device.name, []),
            }
            for device in circuit.devices
        ],
        "nets": [
            {
                "name": net,
                "pins": pins,
                "labels": net_labels.get(net, []),
            }
            for net, pins in circuit.nets().items()
        ],
        "patterns": matches,
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


def _pin_roles_from_pins(pins: list[str]) -> Counter[str]:
    roles: Counter[str] = Counter()
    for pin in pins:
        if "." not in pin:
            continue
        _, role = pin.rsplit(".", 1)
        roles[role] += 1
    return roles


def _net_classes_from_labels(
    net: str,
    labels: list[dict],
    pin_roles: Counter[str],
) -> list[dict]:
    classes = []
    label_names = {item["label"] for item in labels}
    if net in COMMON_NETS:
        classes.append({
            "class": "supply",
            "confidence": 0.95,
            "evidence": {"reason": "common net name"},
        })
    if "bias" in label_names:
        classes.append({
            "class": "bias",
            "confidence": 0.82,
            "evidence": {"labels": sorted(label_names)},
        })
    if "bias_or_mirror_control" in label_names:
        classes.append({
            "class": "mirror_control",
            "confidence": 0.72,
            "evidence": {"labels": sorted(label_names)},
        })
    if "differential_input" in label_names or "input_candidate" in label_names:
        classes.append({
            "class": "signal_input",
            "confidence": 0.78,
            "evidence": {"labels": sorted(label_names)},
        })
    if "loaded_output" in label_names or "output_candidate" in label_names:
        classes.append({
            "class": "signal_output",
            "confidence": 0.76,
            "evidence": {"labels": sorted(label_names)},
        })
    if "tail" in label_names:
        classes.append({
            "class": "tail",
            "confidence": 0.82,
            "evidence": {"labels": sorted(label_names)},
        })
    if "cascode_internal" in label_names:
        classes.append({
            "class": "internal_cascode",
            "confidence": 0.8,
            "evidence": {"labels": sorted(label_names)},
        })
    if pin_roles and not classes:
        if set(pin_roles) == {"G"} and not _looks_like_bias_gate(net):
            classes.append({
                "class": "signal_input",
                "confidence": 0.62,
                "evidence": {"pin_roles": dict(sorted(pin_roles.items()))},
            })
        elif pin_roles.get("D", 0) >= 1:
            classes.append({
                "class": "internal_or_output",
                "confidence": 0.55,
                "evidence": {"pin_roles": dict(sorted(pin_roles.items()))},
            })
    return classes


def _classify_path_evidence(
    source: str,
    target: str,
    net_classes: dict[str, list[dict]],
    device_nodes: list[str],
) -> tuple[str, float, list[str]]:
    source_classes = _class_names(net_classes.get(source, []))
    target_classes = _class_names(net_classes.get(target, []))
    all_classes = {
        klass
        for classes in net_classes.values()
        for klass in _class_names(classes)
    }
    reasons = []

    if "supply" in all_classes:
        reasons.append("path touches a common supply or ground net")
        return "supply_path", 0.86, reasons
    if _is_feedback_candidate(source, target):
        reasons.append("endpoint names suggest a feedback relationship")
        return "feedback_path", 0.68, reasons
    if (
        "signal_input" in source_classes
        and ("signal_output" in target_classes or "internal_or_output" in target_classes)
    ):
        reasons.append("source looks like signal input and target looks like output")
        return "signal_path", 0.8, reasons
    if (
        "signal_input" in target_classes
        and ("signal_output" in source_classes or "internal_or_output" in source_classes)
    ):
        reasons.append("target looks like signal input and source looks like output")
        return "signal_path", 0.78, reasons
    if (
        "bias" in source_classes
        or "bias" in target_classes
        or "mirror_control" in source_classes
        or "mirror_control" in target_classes
    ):
        reasons.append("endpoint has bias or mirror-control semantic evidence")
        return "bias_path", 0.82, reasons
    if "tail" in all_classes:
        reasons.append("path traverses a tail-current-source net")
        return "bias_path", 0.76, reasons
    if device_nodes:
        reasons.append("path crosses active or passive devices")
        return "structural_path", 0.55, reasons
    reasons.append("no semantic evidence beyond connectivity")
    return "unknown", 0.2, reasons


def _class_names(classes: list[dict]) -> set[str]:
    return {item["class"] for item in classes}


def _is_feedback_candidate(source: str, target: str) -> bool:
    joined = f"{source} {target}".lower()
    return "fb" in joined or "feedback" in joined


def _looks_like_bias_gate(net: str) -> bool:
    n = net.lower()
    return "bias" in n or n.startswith(("vb", "vcas", "vbn", "vbp"))


def _apply_net_labels_from_match(net_labels: dict[str, list[dict]], match: dict) -> None:
    evidence = match["evidence"]
    if match["pattern"] == "differential_pair":
        for net in evidence["gate_nets"]:
            _add_net_label(net_labels, net, "differential_input", 0.82, {"pattern": "differential_pair"})
        for net in evidence["drain_nets"]:
            _add_net_label(net_labels, net, "output_candidate", 0.72, {"pattern": "differential_pair"})
    elif match["pattern"] == "tail_current_source":
        _add_net_label(net_labels, evidence["gate_net"], "bias", 0.84, {"pattern": "tail_current_source"})
        _add_net_label(net_labels, evidence["drain_connected_to_diff_pair_source"], "tail", 0.82, {"pattern": "tail_current_source"})
    elif match["pattern"] == "current_mirror":
        _add_net_label(net_labels, evidence["shared_gate"], "bias_or_mirror_control", 0.76, {"pattern": "current_mirror"})
    elif match["pattern"] == "active_load":
        for net in evidence["loaded_drain_nets"]:
            _add_net_label(net_labels, net, "loaded_output", 0.82, {"pattern": "active_load"})
    elif match["pattern"] == "cascode":
        _add_net_label(net_labels, evidence["upper_gate"], "bias", 0.84, {"pattern": "cascode"})
        _add_net_label(net_labels, evidence["intermediate_net"], "cascode_internal", 0.8, {"pattern": "cascode"})
        _add_net_label(net_labels, evidence["output_net"], "output_candidate", 0.76, {"pattern": "cascode"})


def _add_net_label(
    net_labels: dict[str, list[dict]],
    net: str | None,
    label: str,
    confidence: float,
    evidence: dict,
) -> None:
    if not net:
        return
    labels = net_labels.setdefault(net, [])
    if any(item["label"] == label for item in labels):
        return
    labels.append({
        "label": label,
        "confidence": confidence,
        "evidence": evidence,
    })


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
        continued = line.endswith("\\")
        if continued:
            line = line[:-1].rstrip()
        if line.startswith("+"):
            current += " " + line[1:].strip()
        elif current:
            current += " " + line
        else:
            current = line
        if continued:
            continue
        if current:
            yield current
            include = _include_path(current, base_dir=path.parent)
            if include and include.is_file():
                yield from _logical_lines(include, seen=seen)
        current = ""
    if current:
        yield current
        include = _include_path(current, base_dir=path.parent)
        if include and include.is_file():
            yield from _logical_lines(include, seen=seen)


def _parse_device_line(line: str, *, known_subckts: set[str] | None = None) -> Device | None:
    tokens = _tokenize_instance(line)
    if len(tokens) < 2:
        return None
    name = tokens[0]
    prefix = name[0].upper()
    params = _parse_params(tokens[1:])
    known_subckt_instance = _parse_known_subckt_instance(tokens, known_subckts or set(), line)
    if known_subckt_instance is not None:
        return known_subckt_instance

    if prefix == "X":
        prefixed_primitive = _parse_x_prefixed_primitive(tokens, line)
        if prefixed_primitive is not None:
            return prefixed_primitive
        dollar_pins = _parse_dollar_pins_x_instance(tokens)
        if dollar_pins is not None:
            return dollar_pins
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

    parenthesized = _parse_parenthesized_primitive(line, params)
    if parenthesized is not None:
        return parenthesized

    roles = PIN_ROLES.get(prefix)
    if roles is None:
        return None
    if len(tokens) < 1 + len(roles):
        return None
    nets = tokens[1:1 + len(roles)]
    model_idx = 1 + len(roles)
    model = _primitive_model(tokens, prefix, model_idx)
    return Device(
        name=name,
        kind=prefix,
        scope="",
        model=model,
        pins={role: net for role, net in zip(roles, nets)},
        params=params,
        raw=line,
    )


def _parse_parenthesized_primitive(line: str, params: dict[str, str]) -> Device | None:
    match = _INSTANCE_WITH_PARENS.match(line)
    if not match:
        return None
    name, pins, rest = match.groups()
    prefix = name[0].upper()
    roles = PIN_ROLES.get(prefix)
    if roles is None or prefix == "X":
        return None
    pin_tokens = pins.split()
    if len(pin_tokens) < len(roles):
        return None
    rest_tokens = rest.split()
    model = _primitive_model([name, *pin_tokens, *rest_tokens], prefix, 1 + len(pin_tokens))
    pin_roles = list(roles) + [str(index) for index in range(len(roles) + 1, len(pin_tokens) + 1)]
    return Device(
        name=name,
        kind=prefix,
        scope="",
        model=model,
        pins={role: net for role, net in zip(pin_roles, pin_tokens)},
        params=params,
        raw=line,
    )


def _primitive_model(tokens: list[str], prefix: str, model_idx: int) -> str:
    if model_idx >= len(tokens) or "=" in tokens[model_idx]:
        return ""
    if prefix in {"F", "H", "K"}:
        return ""
    return tokens[model_idx]


def _parse_known_subckt_instance(
    tokens: list[str],
    known_subckts: set[str],
    line: str,
) -> Device | None:
    if not known_subckts:
        return None
    body = tokens[1:]
    model_idx = None
    for idx, token in enumerate(body):
        if token in known_subckts:
            model_idx = idx
            break
    if model_idx is None:
        return None
    if any("=" in token for token in body[:model_idx]):
        return None

    pins = {
        str(idx): net
        for idx, net in enumerate(body[:model_idx], start=1)
        if net != "/"
    }
    return Device(
        name=tokens[0],
        kind="X",
        scope="",
        model=body[model_idx],
        pins=pins,
        params=_parse_params(body[model_idx + 1:]),
        raw=line,
    )


def _parse_x_prefixed_primitive(tokens: list[str], line: str) -> Device | None:
    name = tokens[0]
    if len(name) < 3 or not name[2].isdigit():
        return None
    kind = name[1].upper()
    if kind not in {"R", "C", "M"}:
        return None
    roles = PIN_ROLES[kind]
    if len(tokens) < 1 + len(roles):
        return None
    nets = tokens[1:1 + len(roles)]
    model_idx = 1 + len(roles)
    model = _primitive_model(tokens, kind, model_idx)
    return Device(
        name=name,
        kind=kind,
        scope="",
        model=model,
        pins={role: net for role, net in zip(roles, nets)},
        params=_parse_params(tokens[1:]),
        raw=line,
    )


def _parse_dollar_pins_x_instance(tokens: list[str]) -> Device | None:
    try:
        marker_idx = next(
            idx for idx, token in enumerate(tokens) if token.upper() == "$PINS"
        )
    except StopIteration:
        return None
    if marker_idx < 2:
        return None

    model = tokens[marker_idx - 1]
    positional_nets = [token for token in tokens[1:marker_idx - 1] if token != "/"]
    named_pins: dict[str, str] = {}
    param_tokens: list[str] = []
    for token in tokens[marker_idx + 1:]:
        if "=" not in token:
            param_tokens.append(token)
            continue
        key, value = token.split("=", 1)
        if not key or not value:
            param_tokens.append(token)
            continue
        named_pins[key] = value

    if not named_pins and not positional_nets:
        return None
    pins = {str(idx): net for idx, net in enumerate(positional_nets, start=1)}
    pins.update(named_pins)
    return Device(
        name=tokens[0],
        kind="X",
        scope="",
        model=model,
        pins=pins,
        params=_parse_params(param_tokens),
        raw=" ".join(tokens),
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
    ports = definition.ports or _infer_no_port_interface(definition, instance)
    for idx, port in enumerate(ports, start=1):
        actual = _get_instance_pin(instance, port, str(idx))
        if actual is None:
            continue
        mapped[port] = _map_net(actual, prefix=prefix, net_map=net_map)
    return mapped


def _infer_no_port_interface(definition: SubcktDef, instance: Device) -> list[str]:
    if not instance.pins or not definition.devices:
        return []
    first_device = definition.devices[0]
    candidates = list(first_device.pins.values())
    if len(candidates) < len(instance.pins):
        return []
    return candidates[:len(instance.pins)]


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


def _subckt_header(line: str) -> tuple[str, list[str], dict[str, str]] | None:
    tokens = line.split()
    if len(tokens) >= 2 and tokens[0].lower() in {".subckt", "subckt"}:
        ports = []
        params: dict[str, str] = {}
        in_params = False
        for token in tokens[2:]:
            lower = token.lower()
            if lower in {"params:", "parameters:"}:
                in_params = True
                continue
            if "=" in token:
                in_params = True
                key, value = token.split("=", 1)
                params[key] = value
                continue
            if in_params:
                continue
            ports.append(token)
        return tokens[1], ports, params
    return None


def _is_ends(line: str) -> bool:
    token = line.split(maxsplit=1)[0].lower()
    return token in {".ends", "ends"}


def _param_directive(line: str) -> dict[str, str]:
    tokens = line.split()
    if not tokens or tokens[0].lower() not in {".param", "param", "parameters"}:
        return {}
    return _parse_params(tokens[1:])
