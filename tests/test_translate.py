from __future__ import annotations

from pathlib import Path

import pytest

from netlist_crawler.translate import (
    TranslationError,
    convert_file,
    convert_text,
    verify_spectre_spice,
)


SPECTRE_DECK = """\
simulator lang=spectre
parameters VDD=1.8 WN=10u
subckt amp in out vdd vss
M1 (out in vss vss) nch w=WN l=180n
R1 (vdd out) resistor r=10k
ends amp
VDD (vdd 0) vsource dc=1.8
X1 (in out vdd 0) amp
tran1 tran stop=1u step=1n
"""


SPICE_DECK = """\
.param VDD=1.8 WN=10u
.subckt amp in out vdd vss
M1 out in vss vss nch w=WN l=180n
R1 vdd out 10k
.ends amp
VDD vdd 0 1.8
X1 in out vdd 0 amp
.tran 1n 1u
.end
"""


def test_spectre_to_spice_is_generic_by_default() -> None:
    result = convert_text(
        SPECTRE_DECK,
        source="spectre",
        target="ngspice",
        fragment=True,
    )

    assert result.issues == ()
    assert ".param VDD=1.8 WN=1e-05" in result.text
    assert "M1 out in vss vss nch w={WN} l=1.8e-07" in result.text
    assert "R1 vdd out 10000" in result.text
    assert ".tran 1e-09 1e-06 0" in result.text
    assert "sky130" not in result.text.lower()


def test_spice_to_spectre_converts_devices_sources_and_analysis() -> None:
    result = convert_text(
        SPICE_DECK,
        source="ngspice",
        target="spectre",
    )

    assert result.text.startswith("simulator lang=spectre\n")
    assert "M1 (out in vss vss) nch w=WN l=1.8e-07" in result.text
    assert "R1 (vdd out) resistor r=10000" in result.text
    assert "VDD (vdd 0) vsource dc=1.8" in result.text
    assert "tran1 tran step=1e-09 stop=1e-06" in result.text


def test_sky130_profile_is_explicit_and_fragment_safe() -> None:
    source = """\
simulator lang=spectre
include "/pdk/sky130/models.scs" section=tt
M0 (d g s b) nch_18_mac l=1u w=2u
"""

    result = convert_text(
        source,
        source="spectre",
        target="ngspice",
        profile="sky130",
        fragment=True,
    )

    assert "omitted sky130 model include" in result.text
    assert "XM0 d g s b nch_18_mac l=1e-06 w=2e-06" in result.text


def test_sky130_full_deck_requires_resolvable_model_library() -> None:
    with pytest.raises(TranslationError, match="needs --model-lib/--pdk-root"):
        convert_text(
            'include "/pdk/sky130/models.scs" section=tt\n',
            source="spectre",
            target="ngspice",
            profile="sky130",
        )


def test_permissive_mode_reports_unsupported_statements() -> None:
    result = convert_text(
        "statistics {\n",
        source="spectre",
        target="spice",
        strict=False,
        fragment=True,
    )

    assert result.issues[0].code == "statement"
    assert "unsupported [statement]" in result.text


def test_convert_file_preserves_source_and_writes_only_output(tmp_path: Path) -> None:
    source = tmp_path / "input.scs"
    output = tmp_path / "output.spi"
    source.write_text(SPECTRE_DECK, encoding="utf-8")

    convert_file(
        source,
        output,
        source="spectre",
        target="ngspice",
        fragment=True,
    )

    assert source.read_text(encoding="utf-8") == SPECTRE_DECK
    assert output.read_text(encoding="utf-8").startswith("* input.scs")


def test_pair_and_roundtrip_consistency(tmp_path: Path) -> None:
    scs = tmp_path / "circuit.scs"
    spi = tmp_path / "circuit.spi"
    scs.write_text(SPECTRE_DECK, encoding="utf-8")
    spi.write_text(SPICE_DECK, encoding="utf-8")

    result = verify_spectre_spice(scs, spi)

    assert result.equivalent, result.pair_diff
    assert result.roundtrip_equivalent, result.roundtrip_diff
    assert result.ok
