"""Netlist Crawler public Python API."""

from .benchmark import run_benchmark
from .structural import (
    Device,
    StructuralCircuit,
    annotate_circuit,
    classify_path,
    detect_semantics,
    explain_device,
    explain_net,
    export_graph,
    list_subcircuits,
    neighborhood,
    net_path,
    parse_structural_netlist,
)

__version__ = "0.1.0"

__all__ = [
    "Device",
    "StructuralCircuit",
    "__version__",
    "annotate_circuit",
    "classify_path",
    "detect_semantics",
    "explain_device",
    "explain_net",
    "export_graph",
    "list_subcircuits",
    "neighborhood",
    "net_path",
    "parse_structural_netlist",
    "run_benchmark",
]
