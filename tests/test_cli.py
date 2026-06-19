import json

from click.testing import CliRunner

from netlist_crawler.cli import main


def test_cli_help() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Semantic static analysis" in result.output


def test_summarize_json_on_simple_diff_pair() -> None:
    result = CliRunner().invoke(
        main,
        ["summarize", "examples/simple_diff_pair.sp", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["devices"] == 5
    assert payload["summary"]["device_kinds"] == {"M": 5}
    assert payload["nets"]["tail"] == ["M1.S", "M2.S", "M3.D"]


def test_summarize_can_restrict_to_topcell() -> None:
    result = CliRunner().invoke(
        main,
        [
            "summarize",
            "examples/two_subckts.sp",
            "--topcell",
            "bias_block",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["topcell"] == "bias_block"
    assert payload["summary"]["subcircuits"] == ["gain_stage", "bias_block"]
    assert payload["summary"]["device_kinds"] == {"M": 1, "R": 1}
    assert {device["scope"] for device in payload["devices"]} == {"bias_block"}


def test_list_subckts_reports_ports_and_counts() -> None:
    result = CliRunner().invoke(
        main,
        ["list-subckts", "examples/hierarchical_ota.sp", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = {subckt["name"] for subckt in payload["subcircuits"]}
    assert names == {"diff_core", "load_core", "ota_top"}
    ota_top = next(subckt for subckt in payload["subcircuits"] if subckt["name"] == "ota_top")
    assert ota_top["ports"] == ["vinp", "vinn", "voutp", "voutn", "vdd", "vss", "vbias"]
    assert ota_top["devices"] == 2


def test_topcell_selection_prevents_cross_subckt_paths() -> None:
    result = CliRunner().invoke(
        main,
        [
            "path",
            "examples/two_subckts.sp",
            "--topcell",
            "gain_stage",
            "--from",
            "vin",
            "--to",
            "vdd",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is False
    assert payload["reason"] == "missing endpoint"


def test_expand_depth_exposes_hierarchical_devices_and_local_nets() -> None:
    result = CliRunner().invoke(
        main,
        [
            "summarize",
            "examples/hierarchical_ota.sp",
            "--topcell",
            "ota_top",
            "--expand-depth",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["expanded"] is True
    assert payload["summary"]["devices"] == 5
    assert "XCORE.M1" in {device["name"] for device in payload["devices"]}
    assert payload["nets"]["XCORE.tail"] == ["XCORE.M1.S", "XCORE.M2.S", "XCORE.M3.D"]
    assert "XLOAD.M4.D" in payload["nets"]["voutp"]


def test_detect_works_on_expanded_hierarchy() -> None:
    result = CliRunner().invoke(
        main,
        [
            "detect",
            "examples/hierarchical_ota.sp",
            "--topcell",
            "ota_top",
            "--expand-depth",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    diff_pair = next(
        match for match in payload["matches"]
        if match["pattern"] == "differential_pair"
    )
    assert diff_pair["devices"] == ["XCORE.M1", "XCORE.M2"]
    assert diff_pair["evidence"]["shared_source"] == "XCORE.tail"


def test_named_port_hierarchy_expands_by_formal_port_name() -> None:
    result = CliRunner().invoke(
        main,
        [
            "summarize",
            "examples/named_port_hierarchy.sp",
            "--topcell",
            "top",
            "--expand-depth",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["devices"] == 2
    assert payload["nets"]["a"] == ["XINV.M1.G", "XINV.M2.G"]
    assert payload["nets"]["y"] == ["XINV.M1.D", "XINV.M2.D"]


def test_neighborhood_reports_adjacent_devices() -> None:
    result = CliRunner().invoke(
        main,
        [
            "neighborhood",
            "examples/simple_diff_pair.sp",
            "--net",
            "tail",
            "--depth",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is True
    assert {device["name"] for device in payload["devices"]} == {"M1", "M2", "M3"}
    assert {"tail", "vinp", "vinn", "vbias", "voutp", "voutn", "vss"} <= set(payload["nets"])


def test_path_finds_structural_route_between_nets() -> None:
    result = CliRunner().invoke(
        main,
        [
            "path",
            "examples/simple_diff_pair.sp",
            "--from",
            "vinp",
            "--to",
            "voutp",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is True
    assert payload["path"] == ["vinp", "M1", "voutp"]


def test_path_can_exclude_common_rail_traversal() -> None:
    without_filter = CliRunner().invoke(
        main,
        [
            "path",
            "examples/rail_bridge.sp",
            "--topcell",
            "rail_bridge",
            "--from",
            "a",
            "--to",
            "b",
            "--format",
            "json",
        ],
    )
    assert without_filter.exit_code == 0
    assert json.loads(without_filter.output)["found"] is True

    with_filter = CliRunner().invoke(
        main,
        [
            "path",
            "examples/rail_bridge.sp",
            "--topcell",
            "rail_bridge",
            "--from",
            "a",
            "--to",
            "b",
            "--exclude-common-nets",
            "--format",
            "json",
        ],
    )

    assert with_filter.exit_code == 0
    payload = json.loads(with_filter.output)
    assert payload["found"] is False
    assert payload["reason"] == "disconnected"


def test_detect_reports_initial_semantic_patterns() -> None:
    result = CliRunner().invoke(
        main,
        ["detect", "examples/simple_diff_pair.sp", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    patterns = {match["pattern"] for match in payload["matches"]}
    assert "differential_pair" in patterns
    assert "current_mirror" in patterns
    assert "tail_current_source" in patterns
    assert "active_load" in patterns

    diff_pair = next(
        match for match in payload["matches"]
        if match["pattern"] == "differential_pair"
    )
    assert diff_pair["devices"] == ["M1", "M2"]
    assert diff_pair["evidence"]["shared_source"] == "tail"


def test_explain_reports_device_roles() -> None:
    result = CliRunner().invoke(
        main,
        [
            "explain",
            "examples/simple_diff_pair.sp",
            "--device",
            "M3",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is True
    assert any(role["pattern"] == "tail_current_source" for role in payload["roles"])


def test_explain_reports_active_load_role() -> None:
    result = CliRunner().invoke(
        main,
        [
            "explain",
            "examples/simple_diff_pair.sp",
            "--device",
            "M4",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert any(role["pattern"] == "active_load" for role in payload["roles"])
