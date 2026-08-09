from __future__ import annotations

import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from netlist_crawler.translate import convert_text


MODEL_ENV = "SKY130_CONTINUOUS_MODEL_LIB"


def _run_drain_current(tmp_path: Path, model_lib: Path, multiplicity: int) -> float:
    converted = convert_text(
        f"NM0 (d g 0 0) nfet_01v8_lvt w=10u l=150n m={multiplicity}\n",
        source="spectre",
        target="ngspice",
        profile="sky130",
        fragment=True,
    )
    deck = tmp_path / f"m{multiplicity}.spi"
    deck.write_text(
        "* executable Sky130 multiplicity regression\n"
        f'.lib "{model_lib}" tt\n'
        "Vd d 0 1.8\n"
        "Vg g 0 1.8\n"
        f"{converted.text}"
        ".op\n"
        ".control\n"
        "op\n"
        "print -i(vd)\n"
        "quit\n"
        ".endc\n"
        ".end\n",
        encoding="utf-8",
    )
    completed = subprocess.run(
        ["ngspice", "-b", str(deck)],
        cwd=tmp_path,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    match = re.search(r"-i\(vd\)\s*=\s*([+-]?[0-9.eE+-]+)", completed.stdout)
    assert match, completed.stdout
    return float(match.group(1))


@pytest.mark.skipif(shutil.which("ngspice") is None, reason="ngspice is not installed")
def test_sky130_x_instance_m_preserves_nominal_current(tmp_path: Path) -> None:
    raw_model = os.environ.get(MODEL_ENV)
    if not raw_model:
        pytest.skip(f"set {MODEL_ENV} to run the executable Sky130 regression")
    model_lib = Path(raw_model)
    if not model_lib.is_file():
        pytest.skip(f"{MODEL_ENV} does not name a file")

    one = _run_drain_current(tmp_path, model_lib, 1)
    four = _run_drain_current(tmp_path, model_lib, 4)

    assert one > 0
    assert four == pytest.approx(4 * one, rel=0.01)
