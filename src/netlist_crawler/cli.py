"""Command line entry point for Netlist Crawler."""

from __future__ import annotations

from pathlib import Path

import click


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
def main() -> None:
    """Semantic static analysis for LLM-assisted analog circuit understanding."""


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
def summarize(netlist: Path) -> None:
    """Summarize a netlist at a high level."""
    click.echo(f"Netlist summary is not implemented yet: {netlist}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--net", "net_name", required=True, help="Net to inspect.")
@click.option("--depth", default=1, show_default=True, help="Traversal depth.")
def neighborhood(netlist: Path, net_name: str, depth: int) -> None:
    """Inspect the neighborhood around a net."""
    click.echo(
        f"Neighborhood query is not implemented yet: {netlist}, "
        f"net={net_name}, depth={depth}"
    )


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--from", "source", required=True, help="Source net.")
@click.option("--to", "target", required=True, help="Target net.")
def path(netlist: Path, source: str, target: str) -> None:
    """Find likely connectivity paths between two nets."""
    click.echo(
        f"Path query is not implemented yet: {netlist}, "
        f"from={source}, to={target}"
    )


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--pattern", required=True, help="Pattern to detect, e.g. diff-pair.")
def detect(netlist: Path, pattern: str) -> None:
    """Detect analog semantic patterns."""
    click.echo(f"Pattern detection is not implemented yet: {netlist}, pattern={pattern}")


@main.command()
@click.argument("netlist", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("--device", required=True, help="Device name to explain.")
def explain(netlist: Path, device: str) -> None:
    """Explain the likely role of a device."""
    click.echo(f"Device explanation is not implemented yet: {netlist}, device={device}")


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
