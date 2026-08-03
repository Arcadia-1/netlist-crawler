from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from netlist_crawler.cli import main


SCS = """\
simulator lang=spectre
subckt inv in out vdd vss
M1 (out in vss vss) nch w=1u l=180n
ends inv
"""

SPI = """\
.subckt inv in out vdd vss
M1 out in vss vss nch w=1u l=180n
.ends inv
.end
"""


def test_convert_command_writes_requested_output(tmp_path: Path) -> None:
    source = tmp_path / "input.scs"
    output = tmp_path / "output.spi"
    source.write_text(SCS, encoding="utf-8")

    result = CliRunner().invoke(
        main,
        [
            "convert",
            str(source),
            "--from",
            "spectre",
            "--to",
            "ngspice",
            "--fragment",
            "-o",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    assert f"wrote {output}" in result.output
    assert "M1 out in vss vss nch w=1e-06 l=1.8e-07" in output.read_text(encoding="utf-8")


def test_convert_command_is_strict_by_default(tmp_path: Path) -> None:
    source = tmp_path / "unsupported.scs"
    output = tmp_path / "output.spi"
    source.write_text("statistics {\n", encoding="utf-8")

    result = CliRunner().invoke(
        main,
        ["convert", str(source), "--from", "spectre", "--to", "spice", "-o", str(output)],
    )

    assert result.exit_code != 0
    assert "unsupported Spectre statement" in result.output
    assert not output.exists()


def test_verify_equivalence_command_reports_both_checks(tmp_path: Path) -> None:
    scs = tmp_path / "circuit.scs"
    spi = tmp_path / "circuit.spi"
    scs.write_text(SCS, encoding="utf-8")
    spi.write_text(SPI, encoding="utf-8")

    result = CliRunner().invoke(main, ["verify-equivalence", str(scs), str(spi)])

    assert result.exit_code == 0, result.output
    assert "SCS -> SPICE: ok" in result.output
    assert "SPICE -> SCS -> SPICE: ok" in result.output


def test_main_help_lists_translation_commands() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "convert" in result.output
    assert "verify-equivalence" in result.output
