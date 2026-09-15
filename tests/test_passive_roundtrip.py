from pathlib import Path

import pytest

from netlist_crawler.translate import TranslationError, convert_text, verify_spectre_spice


def test_passive_noise_multiplicity_and_initial_state_are_preserved(tmp_path: Path):
    source = "R0 (a b) resistor r=100k isnoisy=no m=2\nC0 (a b) capacitor c=1p m=3 ic=0.4\nL0 (a b) inductor l=2n ic=1m\n"
    converted = convert_text(source, source="spectre", target="ngspice", fragment=True)
    assert "R0 a b 100000 noisy=0 m=2" in converted.text
    assert "C0 a b 1e-12 m=3 ic=0.4" in converted.text
    assert "L0 a b 2e-09 ic=0.001" in converted.text
    scs, spi = tmp_path / "circuit.scs", tmp_path / "circuit.spi"
    scs.write_text(source)
    spi.write_text(converted.text)
    assert verify_spectre_spice(scs, spi).ok
    spi.write_text(converted.text.replace(" noisy=0", ""))
    assert not verify_spectre_spice(scs, spi).ok


@pytest.mark.parametrize("source,target,text", [
    ("spectre", "ngspice", "R0 (a b) resistor r=1k strange=1"),
    ("ngspice", "spectre", "R0 a b 1k strange=1"),
    ("spectre", "ngspice", "R0 (a b) resistor r=1k isnoisy=maybe"),
    ("ngspice", "spectre", "R0 a b 1k noisy=2"),
])
def test_unknown_passive_options_never_disappear(source, target, text):
    with pytest.raises(TranslationError):
        convert_text(text, source=source, target=target)
    result = convert_text(text, source=source, target=target, strict=False)
    assert result.issues
