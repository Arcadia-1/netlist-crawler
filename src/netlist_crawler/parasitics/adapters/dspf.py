"""DSPF 1.5 syntax adapter (Calibre / HSPICE Detailed Standard Parasitic
Format — one self-contained file).

DSPF is the sibling packaging of the Spectre split form: SAME devices +
SAME parasitic mesh, different syntax.  Where Spectre wraps pins in
``( ... )`` and tags caps with the ``capacitor`` keyword, DSPF is bare
SPICE-style positional tokens with the element kind encoded in the
**leading character** of the instance name::

    cGND/1074 GND:1497 VSS       0.0465853f   # grounded cap  (c…)
    cc_1      VDD:1067 GND:943   2.02e-19      # coupling cap  (cc…)
    rGND/1193 GND:1495 GND:1497  0.253835      # parasitic R   (r…)
    XMM88 MM88:d MM88:g MM88:s MM88:b nch_ulvt_mac L=3e-08 W=3e-07 …

Node names are ``net:subnode`` (``GND:1497``) or ``inst:pin``
(``MM88:g``).  The ``*|NET`` / ``*|S`` / ``*|I`` comment blocks map every
subnode and device pin to its canonical net — we read them into
``Circuit.alias`` so kernels fold subnodes exactly like the Spectre
``N_<net>_…`` rule does.

Cg vs Cc discrimination (why this differs from mrpp/spectre's pure
``is_power``): in a multi-supply extract the rail names are project
nets (``GNDANA``, ``VDDANA``) that ``is_power`` doesn't know, so the
``is_power`` test alone under-counts Cg.  But DSPF gives us a stronger
signal: the element NAME.  Calibre only ever names a cross-net coupling
cap ``cc_*``; a ``c<net>/…`` cap is always to-rail or between two
subnodes of the SAME net (distributed self-cap) — i.e. Cg.  Routing
purely by the ``cc`` prefix reproduces the Spectre split's Cg/Cc split
element-for-element (validated: 23 798 Cg / 87 129 Cc on a real SAR
core; an earlier is_power+bare-end heuristic mis-bucketed 896 same-net
two-subnode caps as Cc).
"""
from __future__ import annotations

import os
import re

from ..ir import Circuit, Device, is_power
from ._util import parse_si


_SUBCKT_RE = re.compile(r"^\.subckt\s+(\S+)\s*(.*)$", re.I)
_ENDS_RE   = re.compile(r"^\.ends\b", re.I)
_DESIGN_RE = re.compile(r'^\*\|DESIGN\s+"?([^"\s]+)"?', re.I)
_GROUND_RE = re.compile(r"^\*\|GROUND_NET\s+(\S+)", re.I)
_NET_RE    = re.compile(r"^\*\|NET\s+(\S+)", re.I)
# *|I (<pinNode> <inst> <pin> ...)   and   *|S (<subnode> ...)
_I_RE      = re.compile(r"^\*\|I\s*\(\s*(\S+)", re.I)
_S_RE      = re.compile(r"^\*\|S\s*\(\s*(\S+)", re.I)
_PARAM_RE  = re.compile(r"(\w+)\s*=\s*(\S+)")


def _is_mos(model_lc: str) -> bool:
    return (model_lc.endswith("_mac")
            or "nch" in model_lc or "pch" in model_lc
            or "nfet" in model_lc or "pfet" in model_lc
            or "nmos" in model_lc or "pmos" in model_lc)


def _iter_logical_lines(path: str):
    """Yield logical lines, joining SPICE ``+`` continuations onto the
    previous line.  A leading ``+`` continues the element/params above."""
    buf = ""
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw in fh:
            line = raw.rstrip("\n").rstrip("\r")
            stripped = line.lstrip()
            if stripped.startswith("+"):
                buf += " " + stripped[1:].strip()
                continue
            if buf:
                yield buf
            buf = line
        if buf:
            yield buf


def parse_dspf(path: str, *, dut_name: str | None = None) -> Circuit:
    """Parse a Calibre/HSPICE DSPF netlist into a Circuit."""
    c = Circuit(metadata={
        "source_file": os.path.abspath(path),
        "format": "dspf",
    })
    extra_power: set[str] = set()
    net_names: set[str] = set()
    cur_net: str | None = None
    saw_subckt = False

    def add_cap(name: str, a: str, b: str, val: float) -> None:
        if val != val:           # NaN
            return
        # Coupling caps are named ``cc_<n>`` (no slash).  Grounded caps are
        # ``c<net>/<id>`` — and when ``<net>`` itself starts with C/c
        # (CLKSH, CONV, CMP…) the name reads ``cCLKSH/…`` whose first two
        # chars lower-case to "cc"; a naive ``[:2]=="cc"`` test mis-files
        # those (≈896 on a real SAR core).  The reliable separator is the
        # slash: coupling never has one, grounded always does.
        if name.lower().startswith("cc") and "/" not in name:
            c.cc_edges.append((a, b, val, name))
            return
        # Non-`cc` prefix ⇒ grounded / intra-net cap.  Calibre DSPF only
        # ever names a CROSS-net coupling cap `cc_*`; a `c<net>/…` cap is
        # always to-rail or between two subnodes of the SAME net (a
        # distributed self-cap).  So everything here is Cg.  Using the
        # `is_power`/bare-end heuristic to "re-discover" coupling would
        # mis-bucket the same-net two-subnode caps (one project had 896
        # of them) — the prefix is the authoritative contract.
        pa = is_power(a, extra_power)
        pb = is_power(b, extra_power)
        if pa and pb:
            return               # pure rail-to-rail cap (defensive; rare)
        # Order the rail / bare terminal second for the kernel; when both
        # ends are subnodes of one net the order is immaterial.
        if pb or (":" not in b and ":" in a):
            c.cg_edges.append((a, b, val, name))
        elif pa or (":" not in a and ":" in b):
            c.cg_edges.append((b, a, val, name))
        else:
            c.cg_edges.append((a, b, val, name))

    for ln in _iter_logical_lines(path):
        s = ln.strip()
        if not s:
            continue

        if s.startswith("*"):
            # DSPF metadata comments carry the canonical-net mapping.
            m = _GROUND_RE.match(s)
            if m:
                extra_power.add(m.group(1))
                continue
            m = _NET_RE.match(s)
            if m:
                cur_net = m.group(1)
                net_names.add(cur_net)
                continue
            m = _S_RE.match(s)
            if m and cur_net:
                c.alias[m.group(1)] = cur_net
                continue
            m = _I_RE.match(s)
            if m and cur_net:
                c.alias[m.group(1)] = cur_net
                continue
            m = _DESIGN_RE.match(s)
            if m and dut_name is None and not saw_subckt:
                c.dut = m.group(1)
            continue

        m = _SUBCKT_RE.match(s)
        if m:
            saw_subckt = True
            if dut_name is None:
                c.dut = m.group(1)
            c.ports = m.group(2).split()
            continue
        if _ENDS_RE.match(s):
            cur_net = None
            continue

        toks = s.split()
        if len(toks) < 3:
            continue
        name = toks[0]
        k = name[0].lower()

        if k == "r":
            if len(toks) >= 4:
                val = parse_si(toks[3])
                if val == val:
                    c.r_edges.append((toks[1], toks[2], val, name))
            continue
        if k == "c":
            if len(toks) >= 4:
                add_cap(name, toks[1], toks[2], parse_si(toks[3]))
            continue
        if k in (".",):
            continue
        # everything else (x/m/d/q/j…) is a device instance.
        # Layout:  name node… model param=…  — params are the trailing
        # k=v tokens; model is the last token before the first param;
        # nodes are between.
        eq_idx = next((i for i, t in enumerate(toks) if "=" in t), len(toks))
        if eq_idx < 3:           # need >=1 node + model before params
            continue
        nodes = toks[1:eq_idx - 1]
        model = toks[eq_idx - 1]
        params = dict(_PARAM_RE.findall(" ".join(toks[eq_idx:])))
        if _is_mos(model.lower()):
            roles = ("D", "G", "S", "B")
            pins = {r: nodes[i] for i, r in enumerate(roles) if i < len(nodes)}
        else:
            pins = {str(i): n for i, n in enumerate(nodes)}
        c.devices.append(Device(name=name, model=model, pins=pins, params=params))

    if dut_name is not None:
        c.dut = dut_name
    elif not c.dut:
        c.dut = os.path.splitext(os.path.basename(path))[0]

    # Subnodes the *|NET blocks didn't cover: fold `net:subnode` whose
    # prefix is a declared net.  Device-pin nodes (`inst:pin`) keep their
    # *|I-supplied alias; if absent they stay unfolded (harmless).
    for node in c.nodes():
        if node in c.alias:
            continue
        if ":" in node:
            head = node.split(":", 1)[0]
            if head in net_names or is_power(head, extra_power):
                c.alias[node] = head

    c.metadata["extra_power"] = sorted(extra_power)
    c.metadata["n_lines_parsed"] = (
        len(c.r_edges) + len(c.cg_edges) + len(c.cc_edges) + len(c.devices)
    )
    return c
