from src.unit_catalog import load_units


def test_unit_map_matches_expected_ranges():
    units = load_units()
    expected = {
        "0": (7, 15),
        "1": (16, 34),
        "2": (35, 39),
        "3": (40, 46),
        "4": (47, 63),
        "5": (64, 84),
        "6": (85, 99),
        "7": (100, 108),
        "8": (109, 114),
        "9": (115, 130),
        "10": (131, 135),
        "11": (136, 149),
    }

    assert len(units) == len(expected)
    for unit in units:
        assert unit.id in expected
        expected_start, expected_end = expected[unit.id]
        assert unit.start_page == expected_start
        assert unit.end_page == expected_end
