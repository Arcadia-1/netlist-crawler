from netlist_crawler.parasitics import test_all


def test_parasitic_fixture_matrix() -> None:
    assert test_all.main() == 0
