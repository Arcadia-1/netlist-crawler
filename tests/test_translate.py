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


def test_spectre_mega_suffix_is_converted_inside_expressions() -> None:
    result = convert_text(
        "parameters FCLK=10M FALT=10meg PERIOD=1/10M HALF={1/(2*10M)}\n",
        source="spectre",
        target="ngspice",
        fragment=True,
    )

    assert ".param FCLK=10000000 FALT=10000000 PERIOD={1/10000000} HALF={1/(2*10000000)}" in result.text


def test_spectre_pulse_without_width_uses_half_of_converted_period() -> None:
    result = convert_text(
        "VCLK (CLK 0) vsource dc=1.8 type=pulse val0=1.8 val1=0 period=1/10M\n",
        source="spectre",
        target="ngspice",
        fragment=True,
    )

    assert "PULSE(1.8 0 0 1e-12 1e-12 {(1/10000000)/2} {1/10000000})" in result.text


def test_maestro_metadata_and_operating_point_are_explicitly_supported() -> None:
    source = """\
simulatorOptions options reltol=1e-3 vabstol=1e-6 iabstol=1e-12 temp=27 tnom=27 sensfile=\"../psf/sens.output\" checklimitdest=psf
dcOp dc write=\"spectre.dc\" maxiters=150 annotate=status
finalTimeOP info what=oppoint where=rawfile
saveOptions options save=allpub
"""

    result = convert_text(
        source, source="spectre", target="ngspice", fragment=True)

    assert result.issues == ()
    assert ".options reltol=0.001 vntol=1e-06 abstol=1e-12 tnom=27" in result.text
    assert ".temp 27" in result.text
    assert result.text.splitlines().count(".op") == 1
    assert "handled Spectre PSF metadata no-op" in result.text
    assert "handled Spectre-only output/reporting options" in result.text
    assert "sensfile=" in result.text
    assert "save=allpub" in result.text


def test_unknown_spectre_option_remains_a_strict_error() -> None:
    with pytest.raises(TranslationError, match="unsupported Spectre simulator option mystery"):
        convert_text(
            "simulatorOptions options mystery=42\n",
            source="spectre",
            target="ngspice",
            fragment=True,
        )


def test_spectre_stb_is_an_actionable_nonfatal_analysis_diagnostic() -> None:
    result = convert_text(
        "stb stb start=1 stop=1G dec=20 probe=XDUT.IPRB0 localgnd=VSS annotate=status\n",
        source="spectre",
        target="ngspice",
        fragment=True,
    )

    assert [issue.code for issue in result.issues] == ["analysis-stb"]
    assert "no native ngspice directive" in result.issues[0].message
    assert "Middlebrook return-ratio" in result.issues[0].message
    assert "probe=XDUT.IPRB0" in result.text
    assert "sweep=dec points=20 start=1 stop=1000000000" in result.text


def test_spectre_xf_is_an_actionable_nonfatal_analysis_diagnostic() -> None:
    result = convert_text(
        "xf ( VO 0 ) xf start=1m stop=1G dec=40 annotate=status\n",
        source="spectre",
        target="ngspice",
        fragment=True,
    )

    assert [issue.code for issue in result.issues] == ["analysis-xf"]
    assert "no direct ngspice directive" in result.issues[0].message
    assert "explicit AC transfer bench" in result.issues[0].message
    assert "output=VO 0" in result.text
    assert "sweep=dec points=40 start=0.001 stop=1000000000" in result.text
    assert not any(line.lower().startswith("xxf ") for line in result.text.splitlines())


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


def test_spice_to_spectre_preserves_four_terminal_bjt_model() -> None:
    result = convert_text(
        "Q0 c b e sub pnp_model area=0.4624p m=36\n",
        source="ngspice",
        target="spectre",
    )

    assert "Q0 (c b e sub) pnp_model area=4.624e-13 m=36" in result.text


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


def test_sky130_profile_maps_short_spectre_macro_wrappers() -> None:
    source = """\
subckt amp d g s b c0 c1
NM0 (d g s b) nfet_01v8_lvt w=420n l=150n as=111.3f ps=1.37u m=1
PM0 (d g s b) pfet_01v8 w=550n l=150n as=145.75f ps=1.63u m=1
PMLVT (d g s b) pfet_01v8_lvt w=8u l=2u m=48
C0 (c0 c1) cap_mim_m3_1 l=4u w=4u m=30
ends amp
"""

    result = convert_text(
        source,
        source="spectre",
        target="ngspice",
        profile="sky130",
        fragment=True,
    )

    assert "XNM0 d g s b sky130_fd_pr__nfet_01v8_lvt" in result.text
    assert "XPM0 d g s b sky130_fd_pr__pfet_01v8" in result.text
    assert "XPMLVT d g s b sky130_fd_pr__pfet_01v8_lvt" in result.text
    assert "XC0 c0 c1 sky130_fd_pr__cap_mim_m3_1" in result.text
    assert "w=0.42 l=0.15 as=0.1113 ps=1.37" in result.text
    assert "w=0.55 l=0.15 as=0.14575 ps=1.63" in result.text
    assert "w=8 l=2 m=48 mult=48" in result.text
    assert "l=4 w=4 m=30 mult=30" in result.text
    assert result.text.count("m=1 mult=1") == 2


def test_sky130_profile_maps_fets_pnp_and_scalable_poly_resistors() -> None:
    source = """\
N0 (d g s b) nfet_01v8 w=1u l=150n m=2
N5 (d g s b) nfet_05v0_nvt w=1u l=500n m=3
Q0 (c b e sub) pnp_05v5_W0p68L0p68 area=0.4624p m=36
R0 (a z sub) res_xhigh_po_1p41 r=88.5489K l=60u w=1.41u
R1 (a z sub) res_high_po_0p69 r=106.07K l=200u w=690n m=4
"""

    result = convert_text(
        source,
        source="spectre",
        target="ngspice",
        profile="sky130",
        fragment=True,
    )

    assert "XN0 d g s b sky130_fd_pr__nfet_01v8 w=1 l=0.15 m=2 mult=2" in result.text
    assert "XN5 d g s b sky130_fd_pr__nfet_05v0_nvt w=1 l=0.5 m=3 mult=3" in result.text
    assert "XQ0 c b e sky130_fd_pr__pnp_05v5_W0p68L0p68 m=36 mult=36" in result.text
    assert "area=" not in result.text
    assert "XR0 a z sub sky130_fd_pr__res_xhigh_po l=60 w=1.41" in result.text
    assert "XR1 a z sub sky130_fd_pr__res_high_po l=200 w=0.69 m=4 mult=4" in result.text
    assert "r=" not in result.text


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
