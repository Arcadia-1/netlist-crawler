import json
from pathlib import Path

from click.testing import CliRunner

from netlist_crawler.cli import main
from netlist_crawler.structural import detect_semantics, parse_structural_netlist


def _write_netlist(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "fixture.sp"
    path.write_text(body.strip() + "\n", encoding="utf-8")
    return path


def test_diff_pair_detector_rejects_same_gate_and_drain(tmp_path: Path) -> None:
    netlist = _write_netlist(
        tmp_path,
        """
        .subckt no_diff vin out tail vss
        M1 out vin tail vss nch
        M2 out vin tail vss nch
        .ends no_diff
        """,
    )
    circuit = parse_structural_netlist(netlist, topcell="no_diff")

    assert detect_semantics(circuit, "diff-pair") == []


def test_current_mirror_detector_requires_a_diode_connected_device(tmp_path: Path) -> None:
    netlist = _write_netlist(
        tmp_path,
        """
        .subckt no_mirror gate out1 out2 vss
        M1 out1 gate vss vss nch
        M2 out2 gate vss vss nch
        .ends no_mirror
        """,
    )
    circuit = parse_structural_netlist(netlist, topcell="no_mirror")

    assert detect_semantics(circuit, "current-mirror") == []


def test_cascode_detector_requires_bias_like_upper_gate(tmp_path: Path) -> None:
    netlist = _write_netlist(
        tmp_path,
        """
        .subckt no_cascode vin ctrl vout vss
        M1 nmid vin tail vss nch
        M2 vout ctrl nmid vss nch
        .ends no_cascode
        """,
    )
    circuit = parse_structural_netlist(netlist, topcell="no_cascode")

    assert detect_semantics(circuit, "cascode") == []


def test_detect_rejects_unknown_patterns_with_cli_error() -> None:
    result = CliRunner().invoke(
        main,
        ["detect", "examples/simple_diff_pair.sp", "--pattern", "not-a-pattern"],
    )

    assert result.exit_code != 0
    assert "unsupported pattern: not-a-pattern" in result.output


def test_annotate_json_keeps_agent_facing_contract() -> None:
    result = CliRunner().invoke(
        main,
        ["annotate", "examples/simple_diff_pair.sp", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert set(payload) == {"devices", "nets", "patterns", "source", "topcell"}

    device = payload["devices"][0]
    assert set(device) == {"kind", "model", "name", "pins", "roles"}

    net = payload["nets"][0]
    assert set(net) == {"labels", "name", "pins"}

    pattern = payload["patterns"][0]
    assert {"confidence", "devices", "evidence", "pattern"} <= set(pattern)
