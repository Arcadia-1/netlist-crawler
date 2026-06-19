"""Netlist Crawler public Python API."""

from .benchmark import run_benchmark
from .structural import (
    Device,
    StructuralCircuit,
    annotate_circuit,
    detect_semantics,
    explain_device,
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
    "detect_semantics",
    "explain_device",
    "list_subcircuits",
    "neighborhood",
    "net_path",
    "parse_structural_netlist",
    "run_benchmark",
]
