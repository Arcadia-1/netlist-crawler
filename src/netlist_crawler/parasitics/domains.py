"""Power-domain classification + cross-domain coupling aggregation.

Post-layout extracts of mixed-signal / power-split designs carry millions of
coupling caps, but the question an analog designer actually asks is coarser:

    "Did the power split work — is digital/clock noise staying out of my
     analog supplies and references?"

This module answers that by collapsing the per-net-pair Cc map (already
canonical-net level) one more level, onto *power domains*, and separating
benign intra-domain coupling (VDD↔GND decap within one block) from the
cross-domain coupling that actually leaks noise between blocks.

The classifier is purely name-based and self-calibrating: domains are
*discovered* from the supply/ground net names present in the design
(``VDDANA``→domain ``ANA``, ``GNDTIA``→domain ``TIA``), not hardcoded.  So
it works on any naming scheme that tags supplies by function, which is the
near-universal convention for power-split layouts.
"""
from __future__ import annotations

import re
from collections import defaultdict

# Net roles ----------------------------------------------------------------
SUPPLY, GROUND, REFERENCE, BIAS = "supply", "ground", "reference", "bias"
INPUT, OUTPUT, CLOCK, CORE = "input", "output", "clock", "core"

# Prefix tables.  Longer/more-specific prefixes first so e.g. ``AVDD`` is
# matched before ``VDD`` and the domain suffix comes out clean.  Note we do
# NOT list ``VDDA``/``VDDD`` — they collide with the dominant ``VDD<DOMAIN>``
# convention (``VDDANA`` must strip to ``ANA``, not ``NA``).  Plain ``VDD``
# already handles both ``VDDA`` (→ domain ``A``) and ``VDDANA`` (→ ``ANA``).
_GROUND_PREFIXES = ("AVSS", "DVSS", "AGND", "DGND", "VSS", "GND")
_SUPPLY_PREFIXES = ("AVDD", "DVDD", "VDD", "VCC")

_REF_PREFIXES = ("VREF", "VINCM", "VCM", "VBG")
_BIAS_PREFIXES = ("VCAS", "VBN", "VBP", "VB", "IB", "IREF", "IBIAS")
_IN_PREFIXES = ("VINP", "VINN", "VIN", "VIP", "INP", "INN")
_OUT_PREFIXES = ("DOUT", "DOUTP", "DOUTN", "OUTP", "OUTN", "DO", "OUT")
_CLK_PREFIXES = ("DCLK", "CLKIN", "CLKSH", "CLK", "SCLK", "GCLK")

# Domains that are noise *aggressors* vs noise-sensitive *victims*.  Used only
# to tag cross-domain pairs in the report; both are heuristic and the report
# says so.  Aggressor = anything switching hard (digital / data / clock).
_AGGRESSOR_TOKENS = ("DIG", "DAT", "CLK", "SPI", "LOGIC", "DECODE")
_VICTIM_TOKENS = ("ANA", "TIA", "CMP", "GM", "AMP", "ADC", "REF", "VCM")

_CORE_RE = re.compile(r"^(XI|NET|N|X)\d", re.IGNORECASE)
_BUS_SUFFIX_RE = re.compile(r"[_<]\d+>?$")          # strip trailing bus index


def _domain_suffix(upper: str, prefix: str) -> str:
    """Domain tag = what's left after the supply/ground prefix.

    ``VDDANA`` → ``ANA``; bare ``VDD`` → ``MAIN``.  Trailing bus indices
    (``VDDANA_3``, ``VDDANA<3>``) are stripped first by the caller.
    """
    tag = upper[len(prefix):].lstrip("_")
    return tag or "MAIN"


def classify_net(net: str) -> tuple[str, str]:
    """Return ``(domain, role)`` for a canonical net name.

    ``domain`` is an UPPERCASE function tag (``ANA``, ``TIA``, ``REF``,
    ``CORE`` …); ``role`` is one of the module-level role constants.
    Unknown internal nets fall through to ``(CORE, core)``.
    """
    if not net:
        return ("CORE", CORE)
    upper = _BUS_SUFFIX_RE.sub("", net.upper())
    for p in _GROUND_PREFIXES:
        if upper.startswith(p):
            return (_domain_suffix(upper, p), GROUND)
    for p in _SUPPLY_PREFIXES:
        if upper.startswith(p):
            return (_domain_suffix(upper, p), SUPPLY)
    for p in _REF_PREFIXES:
        if upper.startswith(p):
            return ("REF", REFERENCE)
    for p in _IN_PREFIXES:
        if upper.startswith(p):
            return ("SIGNAL", INPUT)
    for p in _OUT_PREFIXES:
        if upper.startswith(p):
            return ("DATA", OUTPUT)
    for p in _CLK_PREFIXES:
        if upper.startswith(p):
            return ("CLK", CLOCK)
    for p in _BIAS_PREFIXES:
        if upper.startswith(p) or "BIAS" in upper:
            return ("BIAS", BIAS)
    if _CORE_RE.match(net):
        return ("CORE", CORE)
    return ("CORE", CORE)


def _is_aggressor(domain: str) -> bool:
    return any(t in domain for t in _AGGRESSOR_TOKENS)


def _is_victim(domain: str, role: str) -> bool:
    return role in (REFERENCE, INPUT) or any(t in domain for t in _VICTIM_TOKENS)


def aggregate_domain_coupling(
    cc_pairs: dict[tuple[str, str], float],
) -> dict:
    """Collapse a canonical net-pair Cc map onto power domains.

    Returns a dict with:
      - ``domains``   : sorted set of domain tags seen
      - ``intra``     : {domain: Σ Cc within that domain}  (benign decap)
      - ``cross``     : {(domA, domB): Σ Cc}  domA < domB, domains differ
      - ``risky``     : subset of ``cross`` where one side is an aggressor
                        and the other a victim, as a sorted list of
                        ``(domA, domB, sumCc)`` descending
    """
    intra: dict[str, float] = defaultdict(float)
    cross: dict[tuple[str, str], float] = defaultdict(float)
    role_of: dict[str, str] = {}
    for (a, b), v in cc_pairs.items():
        da, ra = classify_net(a)
        db, rb = classify_net(b)
        role_of.setdefault(da, ra)
        role_of.setdefault(db, rb)
        if da == db:
            intra[da] += v
        else:
            key = (da, db) if da < db else (db, da)
            cross[key] += v
    risky: list[tuple[str, str, float]] = []
    for (da, db), v in cross.items():
        a_agg = _is_aggressor(da) and _is_victim(db, role_of.get(db, CORE))
        b_agg = _is_aggressor(db) and _is_victim(da, role_of.get(da, CORE))
        if a_agg or b_agg:
            risky.append((da, db, v))
    risky.sort(key=lambda t: -t[2])
    return {
        "domains": sorted(set(intra) | {d for pair in cross for d in pair}),
        "intra": dict(intra),
        "cross": dict(cross),
        "risky": risky,
    }
