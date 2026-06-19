import json
from pathlib import Path

from click.testing import CliRunner

from netlist_crawler.cli import main


def test_scan_cli_reports_parasitic_summary_sections() -> None:
    result = CliRunner().invoke(
        main,
        [
            "scan",
            "examples/parasitics/f1_rc_ladder.flat.scs",
            "--top",
            "3",
            "--no-cache",
        ],
    )

    assert result.exit_code == 0, result.output
    assert "# Format         : spectre" in result.output
    assert "# R edges        :            3" in result.output
    assert "## 1. Per-net" in result.output
    assert "## 7. Red flags" in result.output


def test_prescribe_cli_writes_agent_consumable_json(tmp_path: Path) -> None:
    output = tmp_path / "rc_model.json"

    result = CliRunner().invoke(
        main,
        [
            "prescribe",
            "examples/parasitics/f2_diffpair_cc.flat.scs",
            "--nets",
            "nIP,nOP",
            "--no-cache",
            "-o",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["format"] == "spectre"
    assert [item["net"] for item in payload["prescriptions"]] == ["nIP", "nOP"]
    assert payload["prescriptions"][0]["cc_distribution"] == {"nB": 1e-15}


def test_inject_cli_rewrites_mos_pin_and_adds_rc_block(tmp_path: Path) -> None:
    schematic = tmp_path / "schematic.scs"
    schematic.write_text(
        """
simulator lang=spectre
subckt DUT (in out VSS)
M1 (out in VSS VSS) nch w=1u l=1u
ends DUT
""".lstrip(),
        encoding="utf-8",
    )
    prescription = tmp_path / "rx.json"
    prescription.write_text(
        json.dumps(
            {
                "prescriptions": [
                    {
                        "net": "out",
                        "r_common": 1.0,
                        "r_branch": {"M1.D": 2.0},
                        "pin_entries": [
                            {"instance": "M1", "role": "D", "key": "M1.D"}
                        ],
                        "cc_distribution": {"in": 2e-16},
                    }
                ],
                "inter_net_couplings": [],
            }
        ),
        encoding="utf-8",
    )
    output = tmp_path / "injected.scs"

    result = CliRunner().invoke(
        main,
        [
            "inject",
            str(schematic),
            str(prescription),
            "--dut",
            "DUT",
            "-o",
            str(output),
        ],
    )

    assert result.exit_code == 0, result.output
    text = output.read_text(encoding="utf-8")
    assert "M1 (out_M1_D_post in VSS VSS) nch" in text
    assert "R_rc_common_out (out out_hub) resistor r=1" in text
    assert "R_rc_M1_D_out (out_hub out_M1_D_post) resistor r=2" in text
    assert "C_rc_d_out_in (out in) capacitor c=2e-16" in text
