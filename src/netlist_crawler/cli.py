"""Command line entry point for Netlist Crawler."""

from __future__ import annotations

from pathlib import Path

import click

from .structural import (
    detect_semantics,
    dumps_json,
    explain_device,
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
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def neighborhood(
    netlist: Path,
    net_name: str,
    depth: int,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Inspect the neighborhood around a net."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = structural_neighborhood(circuit, net_name, depth)
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


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--from", "source", required=True, help="Source net.")
@click.option("--to", "target", required=True, help="Target net.")
@click.option("--topcell", help="Restrict analysis to one subcircuit definition.")
@click.option("--expand-depth", default=0, show_default=True, help="Expand subckt instances.")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text")
def path(
    netlist: Path,
    source: str,
    target: str,
    topcell: str | None,
    expand_depth: int,
    output_format: str,
) -> None:
    """Find likely connectivity paths between two nets."""
    circuit = parse_structural_netlist(netlist, topcell=topcell, expand_depth=expand_depth)
    result = net_path(circuit, source, target)
    if output_format == "json":
        click.echo(dumps_json(result))
        return
    if not result["found"]:
        click.echo(f"No structural path from {source} to {target}: {result['reason']}")
        return
    click.echo(" -> ".join(result["path"]))


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


if __name__ == "__main__":
    main()
