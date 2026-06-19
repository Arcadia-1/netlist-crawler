from click.testing import CliRunner

from netlist_crawler.cli import main


def test_cli_help() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Semantic static analysis" in result.output
