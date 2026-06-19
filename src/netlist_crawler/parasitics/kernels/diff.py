"""Format-invariant diff of two post-layout extractions.

The problem this solves (see WORK / DIFF_BASELINE notes): two valid
extractions of the *same* layout — or two packagings of one xRC run —
can look wildly different at the raw-edge level:

  * subnode names are arbitrary per run (``c_18125_p`` vs ``VINP:127``);
  * ground capacitance lands on the bare rail in one format and on a
    rail *mesh subnode* in another (Cg vs Cc bucketing flips);
  * a gate-R / contact-stub export option adds ~one R segment per device.

A naive ``ΣCg`` / ``ΣCc`` comparison therefore screams about changes
that are pure representation.  This kernel compares **representation-
invariant physical quantities** instead, by first BFS-attributing every
subnode back to its canonical net (NOT name-folding — that's what fails
on anonymous ``c_NNN`` names) and then bucketing:

  * total R, device count + model histogram                (global)
  * internal R per net                                     (per-net)
  * ground capacitance per net  (Cg + any Cc whose far end
    BFS-resolves to a rail)                                (per-net)
  * true inter-net coupling per net-pair                   (per-pair)
  * rail-to-rail (power-mesh-internal) cap                 (reported,
    excluded from "coupling" — it is near-shorted)

Two extractions of one layout then reconcile to ~0 on every physical
bucket, and the verdict is "electrically equivalent" — the residual is
the gate-R export delta + the Cg/Cc rebucketing, which sit below the
significance threshold.
"""
from __future__ import annotations

from collections import defaultdict

from ..ir import Circuit, is_power
from .r_network import _build_adjacency, _build_canonical_node_map


def _named_nets(c: Circuit) -> list[str]:
    """Every non-anonymous canonical net name in the circuit."""
    named: set[str] = set()
    for edges in (c.r_edges, c.cg_edges, c.cc_edges):
        for e in edges:
            for n in (e[0], e[1]):
                cn = c.canonical(n)
                if not cn:
                    continue
                if cn.startswith("c_") or cn.lstrip("_").isdigit():
                    continue
                named.add(cn)
    return sorted(named)


def summarize(c: Circuit) -> dict:
    """Reduce a Circuit to representation-invariant physical buckets.

    Every node is BFS-attributed to its canonical net via the R-mesh, so
    anonymous-subnode netlists (Maestro calibreview ``c_NNN_n``) and
    name-carrying ones (xRC ``N_VINP_…`` / DSPF ``VINP:127``) collapse to
    the same per-net numbers.
    """
    adj = _build_adjacency(c)
    node2net = _build_canonical_node_map(c, _named_nets(c), adj=adj)

    def net_of(n: str) -> str:
        return node2net.get(n) or c.canonical(n)

    def rail(n: str) -> bool:
        return is_power(net_of(n))

    total_R = 0.0
    R_int: dict[str, float] = defaultdict(float)
    for a, b, r, _ in c.r_edges:
        if r <= 0:
            continue
        total_R += r
        na, nb = net_of(a), net_of(b)
        if na == nb:
            R_int[na] += r

    Cg: dict[str, float] = defaultdict(float)       # to AC ground, per net
    Cc: dict[tuple[str, str], float] = defaultdict(float)  # true coupling
    rail2rail = 0.0
    intra = 0.0
    for a, b, v, _ in c.cg_edges:
        if v <= 0:
            continue
        Cg[net_of(a) if not rail(a) else net_of(b)] += v
    for a, b, v, _ in c.cc_edges:
        if v <= 0:
            continue
        na, nb = net_of(a), net_of(b)
        ra, rb = is_power(na), is_power(nb)
        if ra and rb:
            rail2rail += v
        elif ra or rb:
            Cg[nb if ra else na] += v            # ground cap mis-bucketed as Cc
        elif na == nb:
            intra += v                           # same-net subnode cap (~shorted)
        else:
            Cc[tuple(sorted((na, nb)))] += v

    models: dict[str, int] = defaultdict(int)
    for d in c.devices:
        models[d.model] += 1

    return {
        "total_R": total_R,
        "n_devices": len(c.devices),
        "models": dict(models),
        "R_int": dict(R_int),
        "Cg": dict(Cg),
        "Cc": dict(Cc),
        "ground_total": sum(Cg.values()),
        "coupling_total": sum(Cc.values()),
        "rail2rail": rail2rail,
        "intra_net_cap": intra,
    }


def _rel(a: float, b: float) -> float:
    """Relative difference |a-b| / max(|a|,|b|); 0 if both ~0."""
    m = max(abs(a), abs(b))
    return abs(a - b) / m if m > 1e-30 else 0.0


def diff_circuits(
    ca: Circuit,
    cb: Circuit,
    *,
    rtol: float = 1e-3,
    c_atol: float = 1e-16,      # 0.1 fF — below this a per-net Cg delta is noise
) -> dict:
    """Compare two extractions on representation-invariant buckets.

    Returns a report dict with global deltas, per-net ground-cap deltas
    (only the significant ones), and an ``equivalent`` verdict.

    ``rtol`` governs the global total-R / total-C equivalence test.
    ``c_atol`` is the per-net ground-cap significance floor (default
    0.1 fF) — deltas below it are representation noise, not real change.
    """
    sa, sb = summarize(ca), summarize(cb)

    dR = _rel(sa["total_R"], sb["total_R"])
    dCg = _rel(sa["ground_total"], sb["ground_total"])
    dCc = _rel(sa["coupling_total"], sb["coupling_total"])
    same_devices = sa["models"] == sb["models"]

    # Per-net ground-cap deltas above the significance floor.
    nets = set(sa["Cg"]) | set(sb["Cg"])
    net_deltas = []
    for n in nets:
        va, vb = sa["Cg"].get(n, 0.0), sb["Cg"].get(n, 0.0)
        if abs(va - vb) >= c_atol:
            net_deltas.append({"net": n, "a": va, "b": vb, "delta": vb - va})
    net_deltas.sort(key=lambda d: -abs(d["delta"]))

    equivalent = (
        dR <= rtol
        and dCg <= rtol
        and dCc <= rtol
        and same_devices
        and not net_deltas
    )

    return {
        "equivalent": equivalent,
        "global": {
            "total_R": (sa["total_R"], sb["total_R"], dR),
            "ground_total": (sa["ground_total"], sb["ground_total"], dCg),
            "coupling_total": (sa["coupling_total"], sb["coupling_total"], dCc),
            "n_devices": (sa["n_devices"], sb["n_devices"]),
            "same_models": same_devices,
            "rail2rail": (sa["rail2rail"], sb["rail2rail"]),
        },
        "net_ground_deltas": net_deltas,
        "summary_a": sa,
        "summary_b": sb,
    }
