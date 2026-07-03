"""Tests for power-domain classification + cross-domain coupling aggregation."""
from netlist_crawler.parasitics.domains import (
    classify_net,
    aggregate_domain_coupling,
    SUPPLY, GROUND, REFERENCE, BIAS, INPUT, OUTPUT, CLOCK, CORE,
)


def test_classify_supply_and_ground_discover_domain():
    assert classify_net("VDDANA") == ("ANA", SUPPLY)
    assert classify_net("GNDANA") == ("ANA", GROUND)
    assert classify_net("VDDTIA") == ("TIA", SUPPLY)
    assert classify_net("GNDDIG") == ("DIG", GROUND)
    # bare rails collapse to a MAIN domain
    assert classify_net("VDD") == ("MAIN", SUPPLY)
    assert classify_net("VSS") == ("MAIN", GROUND)


def test_classify_bus_index_stripped():
    assert classify_net("VDDANA_3") == ("ANA", SUPPLY)
    assert classify_net("GNDCMP<2>") == ("CMP", GROUND)


def test_classify_reference_input_output_clock_bias():
    assert classify_net("VREFN") == ("REF", REFERENCE)
    assert classify_net("VCM") == ("REF", REFERENCE)
    assert classify_net("VINP") == ("SIGNAL", INPUT)
    assert classify_net("DOUT1") == ("DATA", OUTPUT)
    assert classify_net("CLKIN") == ("CLK", CLOCK)
    assert classify_net("IBTIA") == ("BIAS", BIAS)


def test_classify_internal_core_fallback():
    assert classify_net("XI100") == ("CORE", CORE)
    assert classify_net("net13") == ("CORE", CORE)
    assert classify_net("") == ("CORE", CORE)


def test_aggregate_separates_intra_and_cross():
    cc = {
        ("VDDANA", "GNDANA"): 2.0e-12,   # intra ANA (decap)
        ("VDDDIG", "GNDDIG"): 1.0e-12,   # intra DIG (decap)
        ("VDDANA", "VDDDIG"): 5.0e-15,   # cross ANA<->DIG
        ("GNDDIG", "VREFN"): 3.0e-15,    # cross DIG<->REF  (aggressor->victim)
    }
    agg = aggregate_domain_coupling(cc)
    assert set(agg["domains"]) >= {"ANA", "DIG", "REF"}
    assert agg["intra"]["ANA"] == 2.0e-12
    assert agg["intra"]["DIG"] == 1.0e-12
    assert agg["cross"][("ANA", "DIG")] == 5.0e-15
    assert agg["cross"][("DIG", "REF")] == 3.0e-15


def test_risky_flags_digital_into_reference():
    cc = {
        ("GNDDIG", "VREFN"): 3.0e-15,    # DIG aggressor -> REF victim
        ("VDDANA", "GNDANA"): 2.0e-12,   # intra, not risky
        ("VDDTIA", "GNDGM"): 1.0e-15,    # cross but neither aggressor
    }
    agg = aggregate_domain_coupling(cc)
    risky_pairs = {(a, b) for a, b, _ in agg["risky"]}
    assert ("DIG", "REF") in risky_pairs
    # analog-to-analog cross coupling is not flagged as risky
    assert ("GM", "TIA") not in risky_pairs and ("TIA", "GM") not in risky_pairs
