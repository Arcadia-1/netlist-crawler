"""Command line entry point for Netlist Crawler."""

from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

import click

from .benchmark import run_benchmark
from .structural import (
    COMMON_NETS,
    annotate_circuit,
    classify_path as structural_classify_path,
    detect_semantics,
    dumps_json,
    explain_device,
    explain_net as structural_explain_net,
    export_graph as structural_export_graph,
    list_subcircuits,
    neighborhood as structural_neighborhood,
    net_path,
    parse_structural_netlist,
)


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Semantic static analysis for LLM-assisted analog circuit understanding."""


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def annotate(
    netlist: Path,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Annotate devices and nets with structural semantic labels."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    annotation = annotate_circuit(circuit)
    if output_format == "json":
        click.echo(dumps_json(annotation))
        return
    click.echo("Device roles:")
    for device in annotation["devices"]:
        roles = ", ".join(role["role"] for role in device["roles"]) or "none"
        click.echo(f"- {device['name']}: {roles}")
    click.echo("Net labels:")
    for net in annotation["nets"]:
        labels = ", ".join(label["label"] for label in net["labels"]) or "none"
        click.echo(f"- {net['name']}: {labels}")


@main.command()
@click.argument("tasks", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def benchmark(tasks: Path, output_format: str) -> None:
    """Run a structural/semantic benchmark task file."""
    result = run_benchmark(tasks)
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    click.echo(
        f"Benchmark: {result['passed']}/{result['total']} passed "
        f"({result['failed']} failed)"
    )
    for item in result["results"]:
        status = "PASS" if item["passed"] else "FAIL"
        click.echo(f"{status} {item['name']} [{item['kind']}]")
        if item.get("error"):
            click.echo(f"  error: {item['error']}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--max-patterns", default=20, show_default=True, help="Maximum semantic matches.")
def brief(netlist: Path, topcell: str | None, expand_depth: int, max_patterns: int) -> None:
    """Emit a compact LLM-readable circuit brief."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    for line in _brief_lines(circuit, max_patterns=max_patterns):
        click.echo(line)


@main.command("list-subckts")
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def list_subckts(netlist: Path, output_format: str) -> None:
    """List subcircuit definitions and direct device counts."""
    subckts = list_subcircuits(netlist)
    if output_format == "json":
        click.echo(dumps_json({"subcircuits": subckts}))
        return
    for subckt in subckts:
        ports = ", ".join(subckt["ports"])
        click.echo(f"{subckt['name']} ({subckt['devices']} devices): {ports}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def summarize(
    netlist: Path,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Summarize a netlist at a high level."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    summary = circuit.summary()
    if output_format == "json":
        click.echo(dumps_json(circuit.to_json_dict()))
        return

    click.echo(f"Source: {summary['source']}")
    if summary["topcell"]:
        click.echo(f"Topcell: {summary['topcell']}")
    if summary["subcircuits"]:
        click.echo(f"Subcircuits: {', '.join(summary['subcircuits'])}")
    click.echo(f"Devices: {summary['devices']}")
    click.echo(f"Nets: {summary['nets']}")
    click.echo(f"Directives: {summary['directives']}")
    click.echo("Device kinds:")
    for kind, count in summary["device_kinds"].items():
        click.echo(f"  {kind}: {count}")
    click.echo("Top nets:")
    for item in summary["top_nets"]:
        click.echo(f"  {item['net']}: degree {item['degree']}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--net", "net_name", required=True, help="Net to inspect.")
@click.option("--depth", default=1, show_default=True, help="Traversal depth.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--exclude-common-nets", is_flag=True, help="Do not traverse common rails.")
@click.option("--exclude-net", multiple=True, help="Net to keep visible but not traverse.")
@click.option("--max-degree", type=int, help="Keep high-degree nets visible but do not expand them.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def neighborhood(
    netlist: Path,
    net_name: str,
    depth: int,
    topcell: str | None,
    expand_depth: int,
    exclude_common_nets: bool,
    exclude_net: tuple[str, ...],
    max_degree: int | None,
    output_format: str,
) -> None:
    """Inspect the neighborhood around a net."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = structural_neighborhood(
        circuit,
        net_name,
        depth,
        exclude_nets=_exclude_nets(exclude_common_nets, exclude_net),
        max_degree=max_degree,
    )
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    if not result["found"]:
        click.echo(f"Net not found: {net_name}")
        return
    click.echo(f"Net: {net_name}")
    click.echo("Neighbor nets:")
    for net in result["nets"]:
        click.echo(f"  {net}")
    click.echo("Devices:")
    for device in result["devices"]:
        pins = ", ".join(f"{role}={net}" for role, net in device["pins"].items())
        label = f"{device['name']} ({device['kind']}"
        if device["model"]:
            label += f", {device['model']}"
        label += ")"
        click.echo(f"  {label}: {pins}")


@main.command("explain-net")
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--net", "net_name", required=True, help="Net name to explain.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def explain_net(
    netlist: Path,
    net_name: str,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Explain the likely semantic role of a net."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = structural_explain_net(circuit, net_name)
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    if not result["found"]:
        click.echo(f"Net not found: {net_name}")
        return
    click.echo(f"Net: {net_name}")
    click.echo(f"Degree: {result['degree']}")
    click.echo("Classes: " + _format_classes(result["classes"]))
    click.echo("Pin roles: " + _format_counts(result["pin_roles"]))
    click.echo("Labels: " + _format_labels(result["labels"]))
    click.echo("Devices:")
    for device in result["devices"]:
        click.echo(
            f"  {device['device']}.{device['role']} "
            f"({device['kind']}, {device['model'] or 'unknown'})"
        )


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--from", "source", required=True, help="Source net.")
@click.option("--to", "target", required=True, help="Target net.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--exclude-common-nets", is_flag=True, help="Do not traverse common rails.")
@click.option("--exclude-net", multiple=True, help="Net to exclude from traversal.")
@click.option("--max-degree", type=int, help="Exclude high-degree intermediate nets from path search.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def path(
    netlist: Path,
    source: str,
    target: str,
    topcell: str | None,
    expand_depth: int,
    exclude_common_nets: bool,
    exclude_net: tuple[str, ...],
    max_degree: int | None,
    output_format: str,
) -> None:
    """Find likely connectivity paths between two nets."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = net_path(
        circuit,
        source,
        target,
        exclude_nets=_exclude_nets(exclude_common_nets, exclude_net),
        max_degree=max_degree,
    )
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    if not result["found"]:
        click.echo(f"No structural path from {source} to {target}: {result['reason']}")
        return
    click.echo(" -> ".join(result["path"]))


@main.command("classify-path")
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--from", "source", required=True, help="Source net.")
@click.option("--to", "target", required=True, help="Target net.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--exclude-common-nets", is_flag=True, help="Do not traverse common rails.")
@click.option("--exclude-net", multiple=True, help="Net to exclude from traversal.")
@click.option("--max-degree", type=int, help="Exclude high-degree intermediate nets from path search.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def classify_path(
    netlist: Path,
    source: str,
    target: str,
    topcell: str | None,
    expand_depth: int,
    exclude_common_nets: bool,
    exclude_net: tuple[str, ...],
    max_degree: int | None,
    output_format: str,
) -> None:
    """Find and classify a likely analog path between two nets."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = structural_classify_path(
        circuit,
        source,
        target,
        exclude_nets=_exclude_nets(exclude_common_nets, exclude_net),
        max_degree=max_degree,
    )
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    if not result["found"]:
        click.echo(f"No structural path from {source} to {target}: {result['reason']}")
        return
    click.echo(
        f"{result['path_type']} (confidence={result['confidence']}): "
        + " -> ".join(result["path"])
    )
    for reason in result["evidence"]["reasons"]:
        click.echo(f"  evidence: {reason}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--pattern", default="all", show_default=True, help="Pattern to detect.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def detect(
    netlist: Path,
    pattern: str,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Detect analog semantic patterns."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    try:
        hits = detect_semantics(circuit, pattern)
    except ValueError as exc:
        raise click.ClickException(str(exc)) from exc
    if output_format == "json":
        click.echo(dumps_json({"pattern": pattern, "matches": hits}))
        return
    if not hits:
        click.echo(f"No matches for pattern: {pattern}")
        return
    for hit in hits:
        evidence = ", ".join(f"{k}={v}" for k, v in hit["evidence"].items())
        click.echo(
            f"{hit['pattern']}: {', '.join(hit['devices'])} "
            f"(confidence={hit['confidence']})"
        )
        click.echo(f"  evidence: {evidence}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--device", required=True, help="Device name to explain.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def explain(
    netlist: Path,
    device: str,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Explain the likely role of a device."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = explain_device(circuit, device)
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    if not result["found"]:
        click.echo(f"Device not found: {device}")
        return
    pins = ", ".join(f"{role}={net}" for role, net in result["pins"].items())
    click.echo(f"{device} ({result['kind']}, {result['model']}): {pins}")
    if not result["roles"]:
        click.echo("No semantic role detected.")
        return
    for role in result["roles"]:
        click.echo(
            f"  {role['pattern']} with {', '.join(role['devices'])} "
            f"(confidence={role['confidence']})"
        )


@main.command("export-graph")
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--no-semantics", is_flag=True, help="Omit semantic labels and pattern matches.")
@click.option("--format", "output_format", type=click.Choice(["json", "graphml"]), default="json")
def export_graph(
    netlist: Path,
    topcell: str | None,
    expand_depth: int,
    no_semantics: bool,
    output_format: str,
) -> None:
    """Export the device-net graph for downstream workflows."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    graph = structural_export_graph(circuit, include_semantics=not no_semantics)
    if output_format == "graphml":
        click.echo(_graph_to_graphml(graph))
        return
    click.echo(dumps_json(graph))


@main.command(
    add_help_option=False,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def scan(args: tuple[str, ...]) -> None:
    """Run the post-layout parasitic scan report engine."""
    from netlist_crawler.parasitics.scan import main as scan_main

    raise SystemExit(scan_main(list(args)))


@main.command(
    add_help_option=False,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def prescribe(args: tuple[str, ...]) -> None:
    """Extract an R/Cc prescription model from a post-layout netlist."""
    from netlist_crawler.parasitics.prescribe import main as prescribe_main

    raise SystemExit(prescribe_main(list(args)))


@main.command(
    add_help_option=False,
    context_settings={"ignore_unknown_options": True, "allow_extra_args": True},
)
@click.argument("args", nargs=-1, type=click.UNPROCESSED)
def inject(args: tuple[str, ...]) -> None:
    """Inject an extracted R/Cc prescription into a schematic netlist."""
    from netlist_crawler.parasitics.inject import main as inject_main

    raise SystemExit(inject_main(list(args)))


def _exclude_nets(exclude_common_nets: bool, exclude_net: tuple[str, ...]) -> set[str]:
    excluded = set(exclude_net)
    if exclude_common_nets:
        excluded.update(COMMON_NETS)
    return excluded


def _brief_lines(circuit, *, max_patterns: int) -> list[str]:
    summary = circuit.summary()
    lines = [
        f"Source: {summary['source']}",
    ]
    if summary["topcell"]:
        lines.append(f"Topcell: {summary['topcell']}")
    lines.extend([
        f"Devices: {summary['devices']}; Nets: {summary['nets']}",
        "Device kinds: " + _format_counts(summary["device_kinds"]),
        "Top nets: " + _format_top_nets(summary["top_nets"]),
    ])
    if summary["expanded"]:
        lines.append(f"Hierarchy: expanded to depth {summary['expand_depth']}")
    matches = detect_semantics(circuit, "all")[:max_patterns]
    lines.append("Semantic patterns:")
    if not matches:
        lines.append("- none detected")
        return lines
    for match in matches:
        evidence = "; ".join(
            f"{key}={_brief_value(value)}"
            for key, value in match["evidence"].items()
        )
        lines.append(
            f"- {match['pattern']}: {', '.join(match['devices'])}; "
            f"confidence={match['confidence']}; {evidence}"
        )
    return lines


def _format_counts(counts: dict) -> str:
    if not counts:
        return "none"
    return ", ".join(f"{key}={value}" for key, value in counts.items())


def _format_top_nets(top_nets: list[dict]) -> str:
    if not top_nets:
        return "none"
    return ", ".join(f"{item['net']}({item['degree']})" for item in top_nets[:8])


def _format_classes(classes: list[dict]) -> str:
    if not classes:
        return "none"
    return ", ".join(
        f"{item['class']}({item['confidence']})"
        for item in classes
    )


def _format_labels(labels: list[dict]) -> str:
    if not labels:
        return "none"
    return ", ".join(
        f"{item['label']}({item['confidence']})"
        for item in labels
    )


def _brief_value(value) -> str:
    if isinstance(value, list):
        return "/".join(str(item) for item in value)
    return str(value)


def _graph_to_graphml(graph: dict) -> str:
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<graphml xmlns="http://graphml.graphdrawing.org/xmlns">',
        '  <key id="kind" for="node" attr.name="kind" attr.type="string"/>',
        '  <key id="name" for="node" attr.name="name" attr.type="string"/>',
        '  <key id="type" for="node" attr.name="type" attr.type="string"/>',
        '  <key id="degree" for="node" attr.name="degree" attr.type="int"/>',
        '  <key id="role" for="edge" attr.name="role" attr.type="string"/>',
        '  <graph id="netlist" edgedefault="undirected">',
    ]
    for node in graph["nodes"]:
        lines.append(f'    <node id="{escape(node["id"])}">')
        for key in ("type", "name", "kind", "degree"):
            if key in node:
                lines.append(f'      <data key="{key}">{escape(str(node[key]))}</data>')
        lines.append("    </node>")
    for index, edge in enumerate(graph["edges"]):
        lines.append(
            f'    <edge id="e{index}" source="{escape(edge["source"])}" '
            f'target="{escape(edge["target"])}">'
        )
        lines.append(f'      <data key="role">{escape(edge["role"])}</data>')
        lines.append("    </edge>")
    lines.extend([
        "  </graph>",
        "</graphml>",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    main()
