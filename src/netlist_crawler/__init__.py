"""Netlist Crawler public Python API."""

from .benchmark import run_benchmark
from .ir import (
    IR_SCHEMA,
    annotation_coverage,
    check_annotations,
    circuit_from_ir,
    export_ir,
    read_ir,
    validate_ir,
    write_ir,
)
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
    "IR_SCHEMA",
    "StructuralCircuit",
    "__version__",
    "annotate_circuit",
    "annotation_coverage",
    "check_annotations",
    "classify_path",
    "circuit_from_ir",
    "detect_semantics",
    "explain_device",
    "explain_net",
    "export_ir",
    "export_graph",
    "list_subcircuits",
    "neighborhood",
    "net_path",
    "parse_structural_netlist",
    "read_ir",
    "run_benchmark",
    "validate_ir",
    "write_ir",
]
