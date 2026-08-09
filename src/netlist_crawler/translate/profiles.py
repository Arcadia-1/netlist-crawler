"""Optional PDK profiles for netlist dialect translation.

Profiles are deliberately separate from the syntax translators.  Selecting no
profile keeps translation PDK-neutral; selecting ``sky130`` opts into model
include discovery and the small set of known macro-device mappings below.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TranslationProfile:
    """PDK-specific hints used by otherwise generic translators."""

    name: str
    include_markers: tuple[str, ...] = ()
    subcircuit_masters: frozenset[str] = frozenset()
    master_aliases: tuple[tuple[str, str], ...] = ()
    parameter_aliases: tuple[tuple[str, str, str], ...] = ()
    parameter_copies: tuple[tuple[str, str, str], ...] = ()
    parameter_drops: tuple[tuple[str, str], ...] = ()
    node_drops: tuple[tuple[str, int], ...] = ()
    parameter_scales: tuple[tuple[str, str, float], ...] = ()

    def matches_model_include(self, path: str) -> bool:
        lowered = path.lower()
        return any(marker in lowered for marker in self.include_markers)

    def map_master(self, master: str) -> str:
        """Map a source-PDK wrapper name to the target profile's model name."""
        aliases = dict(self.master_aliases)
        return aliases.get(master.lower(), master)

    def map_parameters(self, master: str, params: dict[str, str]) -> dict[str, str]:
        """Map wrapper parameters without mutating the parser-owned dictionary."""
        mapped = dict(params)
        for alias_master, source, target in self.parameter_aliases:
            if alias_master == master.lower() and source in mapped:
                mapped[target] = mapped.pop(source)
        for copy_master, source, target in self.parameter_copies:
            if copy_master == master.lower() and source in mapped and target not in mapped:
                mapped[target] = mapped[source]
        for drop_master, parameter in self.parameter_drops:
            if drop_master == master.lower():
                mapped.pop(parameter, None)
        return mapped

    def map_nodes(self, master: str, nodes: list[str]) -> list[str]:
        """Adapt source wrapper terminals to the selected target wrapper."""
        dropped = {
            index for drop_master, index in self.node_drops
            if drop_master == master.lower()
        }
        return [node for index, node in enumerate(nodes) if index not in dropped]

    def parameter_scale(self, master: str, parameter: str) -> float:
        """Return a profile-unit scaling factor for one source parameter."""
        for scale_master, scale_parameter, factor in self.parameter_scales:
            if scale_master == master.lower() and scale_parameter == parameter:
                return factor
        return 1.0


SKY130 = TranslationProfile(
    name="sky130",
    include_markers=("sky130",),
    # These cell names are macro/subcircuit devices in the source task decks,
    # so ngspice must receive X instances rather than primitive M instances.
    subcircuit_masters=frozenset(
        {
            "nch_ulvt_mac",
            "pch_ulvt_mac",
            "nch_mac",
            "pch_mac",
            "nch_18_mac",
            "pch_18_mac",
        }
    ),
    master_aliases=(
        ("nfet_01v8", "sky130_fd_pr__nfet_01v8"),
        ("nfet_01v8_lvt", "sky130_fd_pr__nfet_01v8_lvt"),
        ("nfet_05v0_nvt", "sky130_fd_pr__nfet_05v0_nvt"),
        ("pfet_01v8", "sky130_fd_pr__pfet_01v8"),
        ("pfet_01v8_lvt", "sky130_fd_pr__pfet_01v8_lvt"),
        ("cap_mim_m3_1", "sky130_fd_pr__cap_mim_m3_1"),
        ("pnp_05v5_w0p68l0p68", "sky130_fd_pr__pnp_05v5_W0p68L0p68"),
        ("res_high_po_0p69", "sky130_fd_pr__res_high_po"),
        ("res_xhigh_po_0p35", "sky130_fd_pr__res_xhigh_po"),
        ("res_xhigh_po_0p69", "sky130_fd_pr__res_xhigh_po"),
        ("res_xhigh_po_1p41", "sky130_fd_pr__res_xhigh_po"),
    ),
    # The continuous wrappers use ``mult`` only in mismatch-area terms.  The
    # ngspice X-instance ``m`` is what preserves nominal current/capacitance.
    # A Spectre multiplicity therefore has to drive both parameters; replacing
    # m with mult silently changes the electrical circuit.
    parameter_copies=(
        ("nfet_01v8", "m", "mult"),
        ("nfet_01v8_lvt", "m", "mult"),
        ("nfet_05v0_nvt", "m", "mult"),
        ("pfet_01v8", "m", "mult"),
        ("pfet_01v8_lvt", "m", "mult"),
        ("cap_mim_m3_1", "m", "mult"),
        ("pnp_05v5_w0p68l0p68", "m", "mult"),
        ("res_high_po_0p69", "m", "mult"),
        ("res_xhigh_po_0p35", "m", "mult"),
        ("res_xhigh_po_0p69", "m", "mult"),
        ("res_xhigh_po_1p41", "m", "mult"),
    ),
    # Cadence stores a computed nominal ``r`` on scalable physical resistor
    # cells.  The continuous ngspice wrapper recomputes R from l/w and does not
    # declare that parameter.  Likewise, the fixed-size PNP wrapper does not
    # declare Cadence's informational emitter area.
    parameter_drops=(
        ("pnp_05v5_w0p68l0p68", "area"),
        ("res_high_po_0p69", "r"),
        ("res_xhigh_po_0p35", "r"),
        ("res_xhigh_po_0p69", "r"),
        ("res_xhigh_po_1p41", "r"),
    ),
    # Cadence's PNP symbol exposes a fourth substrate terminal; the continuous
    # W0p68L0p68 wrapper is a three-terminal vertical PNP.
    node_drops=(
        ("pnp_05v5_w0p68l0p68", 3),
    ),
    parameter_scales=tuple(
        (master, parameter, factor)
        for master in (
            "nfet_01v8_lvt",
            "nfet_01v8",
            "nfet_05v0_nvt",
            "pfet_01v8",
            "pfet_01v8_lvt",
            "cap_mim_m3_1",
            "res_high_po_0p69",
            "res_xhigh_po_0p35",
            "res_xhigh_po_0p69",
            "res_xhigh_po_1p41",
        )
        for parameter, factor in (
            ("l", 1e6), ("w", 1e6),
            ("ps", 1e6), ("pd", 1e6),
            ("sa", 1e6), ("sb", 1e6), ("sd", 1e6),
            ("as", 1e12), ("ad", 1e12),
        )
    ),
)


def get_profile(name: str | None) -> TranslationProfile | None:
    """Return a named translation profile, or ``None`` for generic mode."""

    if name is None or name.lower() in {"", "generic", "none"}:
        return None
    if name.lower() == "sky130":
        return SKY130
    raise ValueError(f"unknown translation profile: {name}")


def find_sky130_model_library(
    *,
    model_lib: str | Path | None = None,
    pdk_root: str | Path | None = None,
) -> Path | None:
    """Locate the Sky130 continuous ngspice library without extra packages.

    An explicit ``model_lib`` wins.  Otherwise ``pdk_root`` and ``PDK_ROOT``
    are checked both as a directory containing ``sky130A`` and as ``sky130A``
    itself.  Missing paths return ``None`` so the caller can choose between a
    strict error and an explicit warning.
    """

    if model_lib is not None:
        candidate = Path(model_lib).expanduser()
        return candidate if candidate.is_file() else None

    roots: list[Path] = []
    for raw in (pdk_root, os.environ.get("PDK_ROOT")):
        if raw:
            roots.append(Path(raw).expanduser())

    relative = Path("libs.tech/combined/continuous/sky130.lib.spice")
    for root in roots:
        for candidate_root in (root / "sky130A", root):
            candidate = candidate_root / relative
            if candidate.is_file():
                return candidate
    return None
