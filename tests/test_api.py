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

    explained_net = nc.explain_net(circuit, "vbias")
    assert any(item["class"] == "bias" for item in explained_net["classes"])

    path = nc.classify_path(circuit, "vinp", "voutp")
    assert path["path_type"] == "signal_path"

    graph = nc.export_graph(circuit)
    assert graph["schema"] == "netlist-crawler.graph.v1"
    assert any(node["id"] == "device:M1" for node in graph["nodes"])


def test_public_api_exports_benchmark_runner() -> None:
    result = nc.run_benchmark(Path("benchmarks/seed_tasks.json"))

    assert result["total"] == 4
    assert result["failed"] == 0
