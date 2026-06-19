import json

from click.testing import CliRunner

from netlist_crawler.cli import main


def test_cli_help() -> None:
    result = CliRunner().invoke(main, ["--help"])

    assert result.exit_code == 0
    assert "Semantic static analysis" in result.output


def test_brief_reports_semantic_patterns() -> None:
    result = CliRunner().invoke(
        main,
        ["brief", "examples/simple_diff_pair.sp"],
    )

    assert result.exit_code == 0
    assert "Devices: 5; Nets: 8" in result.output
    assert "differential_pair: M1, M2" in result.output
    assert "active_load: M4, M5" in result.output


def test_brief_reports_hierarchy_expansion() -> None:
    result = CliRunner().invoke(
        main,
        [
            "brief",
            "examples/hierarchical_ota.sp",
            "--topcell",
            "ota_top",
            "--expand-depth",
            "1",
        ],
    )

    assert result.exit_code == 0
    assert "Topcell: ota_top" in result.output
    assert "Hierarchy: expanded to depth 1" in result.output
    assert "differential_pair: XCORE.M1, XCORE.M2" in result.output


def test_brief_reports_cascode_pattern() -> None:
    result = CliRunner().invoke(
        main,
        ["brief", "examples/cascode_stage.sp", "--topcell", "cascode_stage"],
    )

    assert result.exit_code == 0
    assert "cascode: M1, M2" in result.output
    assert "intermediate_net=ncas" in result.output


def test_annotate_reports_device_roles_and_net_labels() -> None:
    result = CliRunner().invoke(
        main,
        ["annotate", "examples/simple_diff_pair.sp", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    devices = {device["name"]: device for device in payload["devices"]}
    assert any(role["role"] == "differential_pair" for role in devices["M1"]["roles"])
    assert any(role["role"] == "active_load" for role in devices["M4"]["roles"])

    nets = {net["name"]: net for net in payload["nets"]}
    assert any(label["label"] == "differential_input" for label in nets["vinp"]["labels"])
    assert any(label["label"] == "bias" for label in nets["vbias"]["labels"])
    assert not any(label["label"] == "input_candidate" for label in nets["vbias"]["labels"])
    assert any(label["label"] == "loaded_output" for label in nets["voutp"]["labels"])


def test_annotate_reports_cascode_net_labels() -> None:
    result = CliRunner().invoke(
        main,
        [
            "annotate",
            "examples/cascode_stage.sp",
            "--topcell",
            "cascode_stage",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    nets = {net["name"]: net for net in json.loads(result.output)["nets"]}
    assert any(label["label"] == "cascode_internal" for label in nets["ncas"]["labels"])
    assert any(label["label"] == "bias" for label in nets["vbias_cas"]["labels"])


def test_benchmark_seed_tasks_pass() -> None:
    result = CliRunner().invoke(
        main,
        ["benchmark", "benchmarks/seed_tasks.json", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["total"] == 4
    assert payload["passed"] == 4
    assert payload["failed"] == 0


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


def test_parameter_metadata_is_reported_without_polluting_ports() -> None:
    listed = CliRunner().invoke(
        main,
        ["list-subckts", "examples/param_subckt.sp", "--format", "json"],
    )
    assert listed.exit_code == 0
    subckt = json.loads(listed.output)["subcircuits"][0]
    assert subckt["ports"] == ["vin", "vout", "vss", "vbias"]
    assert subckt["params"] == {"WN": "10u", "LN": "LMIN"}

    summarized = CliRunner().invoke(
        main,
        [
            "summarize",
            "examples/param_subckt.sp",
            "--topcell",
            "param_amp",
            "--format",
            "json",
        ],
    )
    assert summarized.exit_code == 0
    payload = json.loads(summarized.output)
    assert payload["summary"]["parameters"] == {"WBIAS": "20u", "LMIN": "180n"}
    assert payload["devices"][0]["params"] == {"w": "WN", "l": "LN"}


def test_list_subckts_follows_relative_includes() -> None:
    result = CliRunner().invoke(
        main,
        ["list-subckts", "examples/include_top.sp", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    names = {subckt["name"] for subckt in payload["subcircuits"]}
    assert names == {"inc_diff", "include_top"}


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


def test_include_file_subckt_can_be_expanded() -> None:
    result = CliRunner().invoke(
        main,
        [
            "summarize",
            "examples/include_top.sp",
            "--topcell",
            "include_top",
            "--expand-depth",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["devices"] == 3
    assert payload["summary"]["subcircuits"] == ["inc_diff", "include_top"]
    assert payload["nets"]["XCORE.tail"] == ["XCORE.M1.S", "XCORE.M2.S", "XCORE.M3.D"]


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


def test_path_can_exclude_high_degree_intermediate_nets() -> None:
    result = CliRunner().invoke(
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
            "--max-degree",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is False
    assert payload["reason"] == "disconnected"


def test_neighborhood_keeps_high_degree_net_visible_without_expanding() -> None:
    result = CliRunner().invoke(
        main,
        [
            "neighborhood",
            "examples/rail_bridge.sp",
            "--topcell",
            "rail_bridge",
            "--net",
            "a",
            "--depth",
            "3",
            "--max-degree",
            "1",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert "vdd" in payload["nets"]
    assert {device["name"] for device in payload["devices"]} == {"M1"}


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


def test_detect_and_explain_cascode_role() -> None:
    detected = CliRunner().invoke(
        main,
        [
            "detect",
            "examples/cascode_stage.sp",
            "--topcell",
            "cascode_stage",
            "--pattern",
            "cascode",
            "--format",
            "json",
        ],
    )
    assert detected.exit_code == 0
    payload = json.loads(detected.output)
    assert len(payload["matches"]) == 1
    assert payload["matches"][0]["devices"] == ["M1", "M2"]
    assert payload["matches"][0]["evidence"]["intermediate_net"] == "ncas"

    explained = CliRunner().invoke(
        main,
        [
            "explain",
            "examples/cascode_stage.sp",
            "--topcell",
            "cascode_stage",
            "--device",
            "M2",
            "--format",
            "json",
        ],
    )
    assert explained.exit_code == 0
    roles = json.loads(explained.output)["roles"]
    assert any(role["pattern"] == "cascode" for role in roles)


def test_explain_net_reports_bias_semantics() -> None:
    result = CliRunner().invoke(
        main,
        [
            "explain-net",
            "examples/simple_diff_pair.sp",
            "--net",
            "vbias",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["found"] is True
    assert payload["pin_roles"] == {"G": 1}
    assert any(item["class"] == "bias" for item in payload["classes"])
    assert payload["devices"][0]["device"] == "M3"


def test_explain_net_distinguishes_mirror_control_from_bias() -> None:
    result = CliRunner().invoke(
        main,
        [
            "explain-net",
            "examples/simple_diff_pair.sp",
            "--net",
            "voutp",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    classes = {item["class"] for item in json.loads(result.output)["classes"]}
    assert "signal_output" in classes
    assert "mirror_control" in classes
    assert "bias" not in classes


def test_classify_path_reports_signal_path() -> None:
    result = CliRunner().invoke(
        main,
        [
            "classify-path",
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
    assert payload["path_type"] == "signal_path"
    assert payload["confidence"] >= 0.75


def test_export_graph_json_includes_semantic_nodes_and_edges() -> None:
    result = CliRunner().invoke(
        main,
        [
            "export-graph",
            "examples/simple_diff_pair.sp",
            "--format",
            "json",
        ],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["schema"] == "netlist-crawler.graph.v1"
    assert any(node["id"] == "device:M1" for node in payload["nodes"])
    assert any(node["id"] == "net:vinp" for node in payload["nodes"])
    assert any(
        edge["source"] == "device:M1" and edge["target"] == "net:vinp" and edge["role"] == "G"
        for edge in payload["edges"]
    )
    vinp = next(node for node in payload["nodes"] if node["id"] == "net:vinp")
    assert any(item["class"] == "signal_input" for item in vinp["classes"])


def test_export_graph_preserves_controlled_and_coupled_devices(tmp_path) -> None:
    netlist = tmp_path / "controlled_sources.sp"
    netlist.write_text(
        """
        .subckt controlled in_p in_n out_p out_n ctrl sense lp ls swp swn
        E1 out_p out_n in_p in_n vcvs gain=10
        F1 out_p out_n VSENSE gain=2
        G1 out_p out_n ctrl 0 vccs gm=1m
        H1 out_p out_n VSENSE transresistance=5k
        B1 out_p 0 v=V(in_p,in_n)*2
        L1 lp 0 1u
        L2 ls 0 2u
        K1 L1 L2 k=0.98
        W1 swp swn ctrl 0 relay vt=0.5
        .ends controlled
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        ["export-graph", str(netlist), "--topcell", "controlled", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    devices = {
        node["name"]: node
        for node in payload["nodes"]
        if node["type"] == "device"
    }
    assert {"E1", "F1", "G1", "H1", "B1", "K1", "W1"} <= set(devices)
    assert devices["E1"]["kind"] == "E"
    assert devices["E1"]["model"] == "vcvs"
    assert devices["E1"]["params"] == {"gain": "10"}
    assert devices["F1"]["kind"] == "F"
    assert devices["K1"]["kind"] == "K"
    assert devices["W1"]["kind"] == "W"
    assert any(
        edge["source"] == "device:F1" and edge["target"] == "net:out_p" and edge["role"] == "OUTP"
        for edge in payload["edges"]
    )
    assert any(
        edge["source"] == "device:K1" and edge["target"] == "net:L1" and edge["role"] == "L1"
        for edge in payload["edges"]
    )
    assert any(edge["target"] == "net:in_p" for edge in payload["edges"])


def test_dollar_pins_x_instances_use_named_port_mapping(tmp_path) -> None:
    netlist = tmp_path / "dollar_pins.sp"
    netlist.write_text(
        """
        .subckt top CLK EN AGND AVDD AVSS OUT
        XI12 / ND2D1A $PINS A1=CLK A2=EN SUB=AGND Z=OUT vdd=AVDD vss=AVSS
        .ends top
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        ["summarize", str(netlist), "--topcell", "top", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    assert payload["summary"]["devices"] == 1
    assert payload["summary"]["nets"] == 6
    device = payload["devices"][0]
    assert device["name"] == "XI12"
    assert device["model"] == "ND2D1A"
    assert device["pins"] == {
        "A1": "CLK",
        "A2": "EN",
        "SUB": "AGND",
        "Z": "OUT",
        "vdd": "AVDD",
        "vss": "AVSS",
    }
    assert "/" not in payload["nets"]
    assert "ND2D1A" not in payload["nets"]


def test_x_prefixed_pex_primitives_are_not_subckt_instances(tmp_path) -> None:
    netlist = tmp_path / "pex_primitives.sp"
    netlist.write_text(
        """
        .subckt inv in out vss
        XM1 out in vss vss nch w=1u l=0.1u
        XR1 out mid 12
        XC1 mid vss 4f
        XU1 in out leafcell
        .ends inv
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    result = CliRunner().invoke(
        main,
        ["summarize", str(netlist), "--topcell", "inv", "--format", "json"],
    )

    assert result.exit_code == 0
    payload = json.loads(result.output)
    devices = {device["name"]: device for device in payload["devices"]}
    assert payload["summary"]["device_kinds"] == {"C": 1, "M": 1, "R": 1, "X": 1}
    assert devices["XM1"]["kind"] == "M"
    assert devices["XM1"]["model"] == "nch"
    assert devices["XM1"]["pins"] == {"D": "out", "G": "in", "S": "vss", "B": "vss"}
    assert devices["XR1"]["kind"] == "R"
    assert devices["XR1"]["pins"] == {"1": "out", "2": "mid"}
    assert devices["XC1"]["kind"] == "C"
    assert devices["XU1"]["kind"] == "X"
    assert devices["XU1"]["model"] == "leafcell"


def test_export_graph_graphml_smoke() -> None:
    result = CliRunner().invoke(
        main,
        [
            "export-graph",
            "examples/simple_diff_pair.sp",
            "--format",
            "graphml",
        ],
    )

    assert result.exit_code == 0
    assert result.output.startswith("<?xml")
    assert '<node id="device:M1">' in result.output
    assert '<data key="role">G</data>' in result.output
