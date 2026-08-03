"""Structural consistency checks for paired Spectre and SPICE netlists."""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass
from pathlib import Path

from .core import TranslationIssue, convert_text


_IGNORED = {".end", ".control", ".endc", "run", "quit"}
_NUMBER_TOKEN = re.compile(
    r"(?<![A-Za-z0-9_.$])[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?(?:meg|[tgkmunpfa])?(?![A-Za-z0-9_])",
    re.IGNORECASE,
)
_SUFFIX = {
    "t": 1e12,
    "g": 1e9,
    "meg": 1e6,
    "k": 1e3,
    "m": 1e-3,
    "u": 1e-6,
    "n": 1e-9,
    "p": 1e-12,
    "f": 1e-15,
    "a": 1e-18,
}


@dataclass(frozen=True)
class ConsistencyResult:
    """Pair and round-trip comparison results."""

    equivalent: bool
    roundtrip_equivalent: bool
    scs_to_spice_issues: tuple[TranslationIssue, ...]
    spice_to_scs_issues: tuple[TranslationIssue, ...]
    pair_diff: str = ""
    roundtrip_diff: str = ""

    @property
    def ok(self) -> bool:
        return self.equivalent and self.roundtrip_equivalent


def verify_spectre_spice(
    scs_path: str | Path,
    spice_path: str | Path,
    *,
    profile: str | None = None,
    model_lib: str | Path | None = None,
    pdk_root: str | Path | None = None,
    corner: str = "tt",
    strict: bool = True,
) -> ConsistencyResult:
    """Compare SCS→SPICE and SPICE→SCS→SPICE normalized structures."""

    scs = Path(scs_path).read_text(encoding="utf-8", errors="replace")
    spice = Path(spice_path).read_text(encoding="utf-8", errors="replace")
    from_scs = convert_text(
        scs,
        source="spectre",
        target="ngspice",
        profile=profile,
        fragment=True,
        model_lib=model_lib,
        pdk_root=pdk_root,
        corner=corner,
        strict=strict,
        title=Path(scs_path).name,
    )
    from_spice = convert_text(
        spice,
        source="ngspice",
        target="spectre",
        strict=strict,
        title=Path(spice_path).name,
    )
    roundtrip = convert_text(
        from_spice.text,
        source="spectre",
        target="ngspice",
        profile=profile,
        fragment=True,
        model_lib=model_lib,
        pdk_root=pdk_root,
        corner=corner,
        strict=strict,
        title=Path(spice_path).name,
    )

    expected = normalize_spice(spice)
    actual = normalize_spice(from_scs.text)
    roundtrip_actual = normalize_spice(roundtrip.text)
    return ConsistencyResult(
        equivalent=actual == expected,
        roundtrip_equivalent=roundtrip_actual == expected,
        scs_to_spice_issues=from_scs.issues,
        spice_to_scs_issues=from_spice.issues,
        pair_diff=_diff(expected, actual, "provided.spi", "from_scs.spi"),
        roundtrip_diff=_diff(expected, roundtrip_actual, "provided.spi", "roundtrip.spi"),
    )


def normalize_spice(text: str) -> list[str]:
    """Return stable comparison lines without comments or run-control noise."""

    normalized: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("*"):
            continue
        line = line.split(";", 1)[0].strip()
        if not line or line.lower() in _IGNORED:
            continue
        tokens = [_normalize_token(token) for token in line.split()]
        if tokens and tokens[0] == ".param":
            normalized.extend(f".param {token}" for token in tokens[1:])
            continue
        if tokens and tokens[0] in {".meas", ".measure", "measure"}:
            tokens[0] = ".meas"
        if tokens and tokens[0] == ".tran" and len(tokens) == 4 and tokens[3] == "0":
            tokens.pop()
        if tokens and tokens[0][:1] in {"v", "i"} and len(tokens) >= 5 and tokens[3] == "dc":
            tokens.pop(3)
        normalized.append(" ".join(tokens))
    return normalized


def _normalize_token(token: str) -> str:
    text = token.strip("'\"").replace("{", "").replace("}", "").lower()

    def replace(match: re.Match[str]) -> str:
        raw = match.group(0).lower()
        suffix = next((item for item in sorted(_SUFFIX, key=len, reverse=True) if raw.endswith(item)), "")
        number = raw[:-len(suffix)] if suffix else raw
        try:
            return f"{float(number) * (_SUFFIX[suffix] if suffix else 1):.12g}"
        except ValueError:
            return raw

    return _NUMBER_TOKEN.sub(replace, text)


def _diff(expected: list[str], actual: list[str], left: str, right: str) -> str:
    if expected == actual:
        return ""
    return "\n".join(
        difflib.unified_diff(expected, actual, fromfile=left, tofile=right, lineterm="")
    )
