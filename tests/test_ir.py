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
