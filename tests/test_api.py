from pathlib import Path

import netlist_crawler as nc


def test_public_api_exports_structural_workflow() -> None:
    circuit = nc.parse_structural_netlist(Path("examples/simple_diff_pair.sp"))

    assert isinstance(circuit, nc.StructuralCircuit)
    assert circuit.summary()["devices"] == 5

    matches = nc.detect_semantics(circuit, "diff-pair")
    assert matches[0]["devices"] == ["M1", "M2"]

    annotations = nc.annotate_circuit(circuit)
    assert any(device["name"] == "M3" for device in annotations["devices"])


def test_public_api_exports_benchmark_runner() -> None:
    result = nc.run_benchmark(Path("benchmarks/seed_tasks.json"))

    assert result["total"] == 4
    assert result["failed"] == 0
