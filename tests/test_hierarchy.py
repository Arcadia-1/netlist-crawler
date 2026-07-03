"""Tests for the design-hierarchy tree/DAG analysis."""
from pathlib import Path

from netlist_crawler.hierarchy import build_hierarchy, render_tree, tree_report

OTA = Path("examples/hierarchical_ota.sp")


def test_roots_and_depth():
    h = build_hierarchy(OTA)
    assert h.roots == ["ota_top"]            # only cell never instantiated
    assert h.depth("ota_top") == 1
    assert h.depth("diff_core") == 0         # leaf-of-hierarchy (only primitives)


def test_flat_counts_via_dag_dp():
    h = build_hierarchy(OTA)
    # ota_top instantiates diff_core (3 MOS) + load_core (2 MOS) = 5 flattened
    assert h.flat_counts("ota_top")["M"] == 5
    assert h.flat_counts("diff_core")["M"] == 3
    assert h.flat_counts("load_core")["M"] == 2


def test_flat_counts_memoized_is_stable():
    h = build_hierarchy(OTA)
    first = dict(h.flat_counts("ota_top"))
    second = dict(h.flat_counts("ota_top"))     # served from cache
    assert first == second


def test_reuse_counter():
    h = build_hierarchy(OTA)
    reuse = h.reuse()
    assert reuse["diff_core"] == 1
    assert reuse["load_core"] == 1


def test_render_tree_lines():
    h = build_hierarchy(OTA)
    lines = render_tree(h, "ota_top")
    assert any("ota_top" in ln for ln in lines)
    assert any("diff_core" in ln for ln in lines)
    assert any("load_core" in ln for ln in lines)


def test_tree_report_contains_stats():
    h = build_hierarchy(OTA)
    rpt = tree_report(h, "ota_top")
    assert "Top cell      : ota_top" in rpt
    assert "Hierarchy depth: 1" in rpt
    assert "Most-reused cells" in rpt


def test_undefined_leaf_counts_as_one():
    # a cell that instantiates an undefined std-cell master counts it as 1 leaf
    h = build_hierarchy(OTA)
    # diff_core/load_core are primitive-only; flat stdcell count is 0 here
    assert h.flat_counts("ota_top").get("Xleaf", 0) == 0
