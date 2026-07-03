"""Design-hierarchy tree/DAG analysis.

`summarize` and `list-subckts` give *flat* views: a count of devices in one
scope, or a flat list of subckt names.  Neither answers the structural
questions a reviewer actually asks first:

  - What is this chip built from, as a tree?
  - How deep is the hierarchy, and what is the top cell?
  - Which leaf cells are reused the most (the workhorses)?
  - How many transistors does each block hold *flattened*, without paying the
    cost of actually flattening a million-device design?

The instantiation graph is a DAG (cells are reused, so a child has many
parents), not a pure tree — but rendered from a root it reads as a tree with
multiplicity (``×N``) on each edge.  Flattened device counts are computed by
**memoized DFS over the DAG**: ``flat(cell) = direct primitives +
Σ count·flat(child)``.  Each cell is solved once, so a 5000-instance design
with heavy reuse costs O(unique cells), not O(flattened instances).
"""
from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from .structural import _parse_netlist_model, SubcktDef


@dataclass
class Hierarchy:
    """Parsed instantiation DAG + memoized analyses."""

    defs: dict[str, SubcktDef]
    # cell -> Counter(child_master -> instance count); only X (subckt) instances
    children: dict[str, Counter] = field(default_factory=dict)
    roots: list[str] = field(default_factory=list)
    _flat_cache: dict[str, Counter] = field(default_factory=dict)
    _depth_cache: dict[str, int] = field(default_factory=dict)

    def is_defined(self, cell: str) -> bool:
        return cell in self.defs

    def direct_primitives(self, cell: str) -> Counter:
        """Primitive (non-expandable) leaf devices declared directly in cell.

        Counts by kind: M/R/C/... primitives, plus X instances whose master is
        NOT a defined subckt (library std cells, varactors, etc.) bucketed as
        ``leaf:<model>``-free ``X`` so they're visible but not expanded.
        """
        c: Counter = Counter()
        for dev in self.defs[cell].devices:
            if dev.kind == "X" and dev.model in self.defs:
                continue                       # expandable — handled via children
            key = dev.kind if dev.kind != "X" else "Xleaf"
            c[key] += 1
        return c

    def flat_counts(self, cell: str) -> Counter:
        """Flattened primitive counts by kind, via memoized DFS over the DAG."""
        if cell not in self.defs:
            return Counter({"Xleaf": 1})       # undefined leaf cell = 1 leaf
        cached = self._flat_cache.get(cell)
        if cached is not None:
            return cached
        # guard against pathological cycles (not expected in real netlists)
        self._flat_cache[cell] = Counter()
        total = Counter(self.direct_primitives(cell))
        for child, n in self.children.get(cell, {}).items():
            child_flat = self.flat_counts(child)
            for k, v in child_flat.items():
                total[k] += n * v
        self._flat_cache[cell] = total
        return total

    def depth(self, cell: str) -> int:
        """Levels of hierarchy below cell (0 = leaf / only primitives)."""
        if cell not in self.defs:
            return 0
        if cell in self._depth_cache:
            return self._depth_cache[cell]
        self._depth_cache[cell] = 0
        kids = [c for c in self.children.get(cell, {}) if c in self.defs]
        d = 0 if not kids else 1 + max(self.depth(c) for c in kids)
        self._depth_cache[cell] = d
        return d

    def reuse(self) -> Counter:
        """Total times each cell is instantiated anywhere in the design."""
        total: Counter = Counter()
        for par, kids in self.children.items():
            for child, n in kids.items():
                total[child] += n
        return total


def build_hierarchy(path: Path) -> Hierarchy:
    """Parse a netlist and build its instantiation DAG."""
    subckts, _top, _dirs, _params = _parse_netlist_model(path)
    children: dict[str, Counter] = {}
    for name, d in subckts.items():
        c: Counter = Counter()
        for dev in d.devices:
            if dev.kind == "X":
                c[dev.model] += 1
        children[name] = c
    instantiated: set[str] = set()
    for c in children.values():
        instantiated |= set(c)
    roots = sorted(n for n in subckts if n not in instantiated)
    return Hierarchy(defs=subckts, children=children, roots=roots)


def _fmt_counts(c: Counter) -> str:
    """Compact 'M=282 C=4432 ...' summary, transistor-first."""
    order = ["M", "C", "R", "D", "Q", "Xleaf"]
    parts = []
    for k in order:
        if c.get(k):
            label = "stdcell" if k == "Xleaf" else k
            parts.append(f"{label}={c[k]:,}")
    for k in sorted(c):
        if k not in order and c[k]:
            parts.append(f"{k}={c[k]:,}")
    return " ".join(parts) if parts else "(empty)"


def render_tree(
    h: Hierarchy,
    root: str,
    *,
    max_depth: int = 6,
    min_instances: int = 1,
) -> list[str]:
    """Render the instantiation tree under ``root`` as indented text lines.

    Each line: ``<cell>  ×N  [flat: M=… C=…]``.  Reused cells appear under
    every parent (it's a DAG) but their subtree is expanded only the first
    time per path; depth is capped by ``max_depth``.
    """
    lines: list[str] = []

    def walk(cell: str, mult: int, prefix: str, depth: int, last: bool) -> None:
        connector = "" if depth == 0 else ("└─ " if last else "├─ ")
        flat = h.flat_counts(cell)
        ntr = flat.get("M", 0)
        mult_s = f" ×{mult}" if mult > 1 else ""
        tag = "  ⟨undefined leaf⟩" if cell not in h.defs else ""
        lines.append(f"{prefix}{connector}{cell}{mult_s}"
                     f"  [flat: {_fmt_counts(flat)}]{tag}"
                     if depth == 0 or cell in h.defs
                     else f"{prefix}{connector}{cell}{mult_s}{tag}")
        if cell not in h.defs or depth >= max_depth:
            return
        kids = h.children.get(cell, {})
        # show defined children first (expandable), sorted by flattened M desc
        shown = [(c, n) for c, n in kids.items() if n >= min_instances]
        shown.sort(key=lambda cn: (-(cn[0] in h.defs),
                                   -h.flat_counts(cn[0]).get("M", 0), cn[0]))
        child_prefix = prefix + ("   " if last else "│  ") if depth > 0 else ""
        for i, (child, n) in enumerate(shown):
            walk(child, n, child_prefix, depth + 1, i == len(shown) - 1)

    walk(root, 1, "", 0, True)
    return lines


def tree_report(h: Hierarchy, root: str, *, max_depth: int = 6) -> str:
    """Full text report: stats header + tree + reuse leaderboard."""
    out: list[str] = []
    flat = h.flat_counts(root)
    out.append(f"Top cell      : {root}")
    out.append(f"Defined cells : {len(h.defs)}")
    out.append(f"Hierarchy depth: {h.depth(root)}")
    out.append(f"Flattened     : {_fmt_counts(flat)}")
    out.append("")
    out.append("Instantiation tree (flattened primitive counts per cell):")
    out.extend("  " + ln for ln in render_tree(h, root, max_depth=max_depth))
    out.append("")
    reuse = h.reuse()
    out.append("Most-reused cells (total instantiations across design):")
    for cell, n in reuse.most_common(12):
        kind = "leaf" if cell not in h.defs else f"depth {h.depth(cell)}"
        tr = h.flat_counts(cell).get("M", 0)
        out.append(f"  {n:>6,} ×  {cell:<32s} ({kind}, flat M={tr:,})")
    return "\n".join(out)
