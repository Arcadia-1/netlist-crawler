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

    def matches_model_include(self, path: str) -> bool:
        lowered = path.lower()
        return any(marker in lowered for marker in self.include_markers)


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
