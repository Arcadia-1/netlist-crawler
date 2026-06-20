import json
from pathlib import Path

import netlist_crawler as nc
from click.testing import CliRunner

from netlist_crawler.cli import main


def test_exported_ir_validates_and_rebuilds_circuit() -> None:
    ir = nc.export_ir(Path("examples/simple_diff_pair.sp"))

    assert ir["schema"] == nc.IR_SCHEMA
    assert ir["source"]["dialect"] == "spice"
    assert any(item["id"] == "M1" for item in ir["instances"])
    assert any(item["id"] == "voutp" for item in ir["nets"])
    assert any(item["source"] == "netlist-crawler.rules" for item in ir["annotations"])

    validation = nc.validate_ir(ir)
    assert validation["valid"] is True

    coverage = nc.annotation_coverage(ir)
    assert coverage["complete"] is True

    circuit = nc.circuit_from_ir(ir)
    assert circuit.summary()["devices"] == 5
    assert nc.classify_path(circuit, "vinp", "voutp")["path_type"] == "signal_path"


def test_export_ir_preserves_expanded_hierarchy_port_map(tmp_path: Path) -> None:
    netlist = tmp_path / "hierarchy.sp"
    netlist.write_text(
        """
        .subckt gain_stage IN OUT VDD VSS
        M1 OUT IN tail VSS nch
        M2 OUT tail VDD VDD pch
        .ends gain_stage
        .subckt TOP vin vout vdd vss
        XAMP vin vout vdd vss gain_stage
        .ends TOP
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    ir = nc.export_ir(netlist, topcell="TOP", expand_depth=1)

    assert [item["id"] for item in ir["instances"]] == ["XAMP.M1", "XAMP.M2"]
    hierarchy = ir["hierarchy"]["instances"]
    assert len(hierarchy) == 1
    xamp = hierarchy[0]
    assert xamp["id"] == "XAMP"
    assert xamp["name"] == "XAMP"
    assert xamp["definition"] == "gain_stage"
    assert xamp["scope"] == "TOP"
    assert xamp["expanded"] is True
    assert xamp["instance_path"] == ["XAMP"]
    assert xamp["pins"] == {"1": "vin", "2": "vout", "3": "vdd", "4": "vss"}
    assert xamp["port_map"] == {"IN": "vin", "OUT": "vout", "VDD": "vdd", "VSS": "vss"}
    assert xamp["member_prefix"] == "XAMP."
    assert xamp["members"]["devices"] == ["XAMP.M1", "XAMP.M2"]
    assert xamp["members"]["nets"] == ["XAMP.tail"]
    assert nc.validate_ir(ir)["valid"] is True


def test_ir_without_rule_annotations_reports_missing_coverage() -> None:
    ir = nc.export_ir(Path("examples/simple_diff_pair.sp"), include_rule_annotations=False)

    coverage = nc.annotation_coverage(ir)
    checked = nc.check_annotations(ir)

    assert coverage["complete"] is False
    assert checked["ok"] is False
    assert coverage["devices"]["missing"] == ["M1", "M2", "M3", "M4", "M5"]
    assert "vinp" in coverage["nets"]["missing"]


def test_check_annotations_reports_conflicting_overlay() -> None:
    ir = nc.export_ir(Path("examples/simple_diff_pair.sp"))
    ir["annotations"].append({
        "id": "ann:test:bad-vdd",
        "target": {"type": "net", "id": "vdd"},
        "label": "signal_input",
        "status": "candidate",
        "source": "workflow.agent",
        "confidence": 0.9,
        "evidence": {"reason": "intentional conflict"},
    })

    result = nc.check_annotations(ir)

    assert result["ok"] is False
    assert any(error["kind"] == "annotation_conflict" for error in result["errors"])


def test_ir_cli_round_trip_and_query_input(tmp_path: Path) -> None:
    ir_path = tmp_path / "simple.nlc.json"

    exported = CliRunner().invoke(
        main,
        ["export-ir", "examples/simple_diff_pair.sp", "-o", str(ir_path)],
    )
    assert exported.exit_code == 0, exported.output

    validated = CliRunner().invoke(main, ["validate-ir", str(ir_path), "--format", "json"])
    assert validated.exit_code == 0
    assert json.loads(validated.output)["valid"] is True

    coverage = CliRunner().invoke(main, ["annotation-coverage", str(ir_path), "--format", "json"])
    assert coverage.exit_code == 0
    assert json.loads(coverage.output)["complete"] is True

    checked = CliRunner().invoke(main, ["check-annotations", str(ir_path), "--format", "json"])
    assert checked.exit_code == 0
    assert json.loads(checked.output)["ok"] is True

    explained = CliRunner().invoke(
        main,
        ["explain-net", str(ir_path), "--net", "vbias", "--format", "json"],
    )
    assert explained.exit_code == 0
    assert any(item["class"] == "bias" for item in json.loads(explained.output)["classes"])


def test_annotation_check_commands_fail_on_incomplete_coverage(tmp_path: Path) -> None:
    ir_path = tmp_path / "incomplete.nlc.json"
    ir = nc.export_ir(Path("examples/simple_diff_pair.sp"), include_rule_annotations=False)
    nc.write_ir(ir, ir_path)

    coverage = CliRunner().invoke(main, ["annotation-coverage", str(ir_path), "--format", "json"])
    checked = CliRunner().invoke(main, ["check-annotations", str(ir_path), "--format", "json"])

    assert coverage.exit_code == 1
    assert json.loads(coverage.output)["complete"] is False
    assert checked.exit_code == 1
    assert json.loads(checked.output)["ok"] is False


def test_export_ir_disambiguates_duplicate_instance_names(tmp_path: Path) -> None:
    netlist = tmp_path / "duplicate_names.sp"
    netlist.write_text(
        """
        .SUBCKT duplicate_names A B C D
        XA2 A B leaf
        XA2 C D leaf
        .ENDS duplicate_names
        """.strip()
        + "\n",
        encoding="utf-8",
    )

    ir = nc.export_ir(netlist, topcell="duplicate_names")

    ids = [item["id"] for item in ir["instances"]]
    assert ids == ["duplicate_names.XA2#1", "duplicate_names.XA2#2"]
    assert [item["name"] for item in ir["instances"]] == ["XA2", "XA2"]
    assert {edge["device"] for edge in ir["edges"]} == set(ids)
    assert nc.validate_ir(ir)["valid"] is True


def test_validate_ir_accepts_subckt_annotation_target(tmp_path: Path) -> None:
    netlist = tmp_path / "hierarchy.sp"
    netlist.write_text(
        """
        .subckt child IN OUT
        M1 OUT IN 0 0 nch
        .ends child
        .subckt TOP A Y
        X1 A Y child
        .ends TOP
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    ir = nc.export_ir(netlist, topcell="TOP", expand_depth=1)
    ir["annotations"].extend([
        {
            "id": "ann:test:subckt",
            "target": {"type": "subckt", "id": "X1"},
            "label": "gain_stage",
            "status": "candidate",
            "source": "workflow.agent",
            "confidence": 0.8,
            "evidence": {"definition": "child"},
        },
        {
            "id": "ann:test:subckt-group",
            "target": {
                "type": "group",
                "id": "group:test:X1",
                "members": [{"type": "subckt", "id": "X1"}],
            },
            "label": "analog_block",
            "status": "candidate",
            "source": "workflow.agent",
            "confidence": 0.8,
            "evidence": {},
        },
    ])

    assert nc.validate_ir(ir)["valid"] is True


def test_validate_ir_rejects_bad_subckt_annotation_reference(tmp_path: Path) -> None:
    netlist = tmp_path / "hierarchy.sp"
    netlist.write_text(
        """
        .subckt child IN OUT
        M1 OUT IN 0 0 nch
        .ends child
        .subckt TOP A Y
        X1 A Y child
        .ends TOP
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    ir = nc.export_ir(netlist, topcell="TOP", expand_depth=1)
    ir["annotations"].append({
        "id": "ann:test:missing-subckt",
        "target": {"type": "subckt", "id": "X2"},
        "label": "gain_stage",
        "status": "candidate",
        "source": "workflow.agent",
        "confidence": 0.8,
        "evidence": {},
    })

    validation = nc.validate_ir(ir)

    assert validation["valid"] is False
    assert any(error["kind"] == "annotation_reference" for error in validation["errors"])


def test_validate_ir_rejects_bad_hierarchy_member_reference(tmp_path: Path) -> None:
    netlist = tmp_path / "hierarchy.sp"
    netlist.write_text(
        """
        .subckt child IN OUT
        M1 OUT IN 0 0 nch
        .ends child
        .subckt TOP A Y
        X1 A Y child
        .ends TOP
        """.strip()
        + "\n",
        encoding="utf-8",
    )
    ir = nc.export_ir(netlist, topcell="TOP", expand_depth=1)
    ir["hierarchy"]["instances"][0]["members"]["devices"].append("X1.MISSING")

    result = nc.validate_ir(ir)

    assert result["valid"] is False
    assert any(error["kind"] == "hierarchy_reference" for error in result["errors"])


def test_validate_ir_rejects_bad_annotation_reference() -> None:
    ir = nc.export_ir(Path("examples/simple_diff_pair.sp"))
    ir["annotations"].append({
        "id": "ann:test:missing-net",
        "target": {"type": "net", "id": "missing"},
        "label": "bias",
        "status": "candidate",
        "source": "workflow.agent",
        "confidence": 0.5,
        "evidence": {},
    })

    validation = nc.validate_ir(ir)

    assert validation["valid"] is False
    assert any(error["kind"] == "annotation_reference" for error in validation["errors"])
