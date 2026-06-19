"""Small benchmark task runner for Netlist Crawler."""

from __future__ import annotations

import json
from pathlib import Path

from .structural import detect_semantics, net_path, parse_structural_netlist


def run_benchmark(task_file: Path) -> dict:
    """Run a JSON benchmark task file."""
    tasks = json.loads(task_file.read_text(encoding="utf-8"))
    if not isinstance(tasks, list):
        raise ValueError("benchmark task file must contain a JSON list")

    results = [_run_task(task, base_dir=task_file.parent) for task in tasks]
    passed = sum(1 for result in results if result["passed"])
    return {
        "task_file": str(task_file),
        "total": len(results),
        "passed": passed,
        "failed": len(results) - passed,
        "results": results,
    }


def _run_task(task: dict, *, base_dir: Path) -> dict:
    kind = task.get("kind")
    try:
        if kind == "detect_pattern":
            return _detect_pattern_task(task, base_dir=base_dir)
        if kind == "path":
            return _path_task(task, base_dir=base_dir)
        if kind == "summary_count":
            return _summary_count_task(task, base_dir=base_dir)
        return _task_result(task, False, error=f"unsupported task kind: {kind}")
    except Exception as exc:  # pragma: no cover - defensive reporting path
        return _task_result(task, False, error=str(exc))


def _detect_pattern_task(task: dict, *, base_dir: Path) -> dict:
    circuit = _parse_task_circuit(task, base_dir=base_dir)
    matches = detect_semantics(circuit, task.get("pattern", "all"))
    expected_devices = task.get("expected_devices")
    expected_pattern = task.get("expected_pattern", task.get("pattern"))
    passed = False
    for match in matches:
        if expected_pattern and match["pattern"] != expected_pattern:
            continue
        if expected_devices is None or match["devices"] == expected_devices:
            passed = True
            break
    return _task_result(
        task,
        passed,
        observed={"matches": matches},
    )


def _path_task(task: dict, *, base_dir: Path) -> dict:
    circuit = _parse_task_circuit(task, base_dir=base_dir)
    result = net_path(
        circuit,
        task["from"],
        task["to"],
        exclude_nets=set(task.get("exclude_nets", ())),
    )
    expected_found = task.get("expected_found")
    passed = result["found"] == expected_found
    if task.get("expected_path") is not None:
        passed = passed and result.get("path") == task["expected_path"]
    return _task_result(task, passed, observed=result)


def _summary_count_task(task: dict, *, base_dir: Path) -> dict:
    circuit = _parse_task_circuit(task, base_dir=base_dir)
    summary = circuit.summary()
    passed = True
    for key, expected in task.get("expected", {}).items():
        if summary.get(key) != expected:
            passed = False
            break
    return _task_result(task, passed, observed={"summary": summary})


def _parse_task_circuit(task: dict, *, base_dir: Path):
    netlist = Path(task["netlist"])
    if not netlist.is_absolute():
        netlist = base_dir / netlist
    return parse_structural_netlist(
        netlist,
        topcell=task.get("topcell"),
        expand_depth=int(task.get("expand_depth", 0)),
    )


def _task_result(task: dict, passed: bool, *, observed: dict | None = None, error: str = "") -> dict:
    result = {
        "name": task.get("name", ""),
        "kind": task.get("kind", ""),
        "passed": passed,
    }
    if observed is not None:
        result["observed"] = observed
    if error:
        result["error"] = error
    return result
