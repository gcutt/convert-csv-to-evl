from src.converter import convert_csv_to_evl

def test_conversion():
    lines = convert_csv_to_evl("data/sample.csv")
    assert lines[0].startswith("EVBD")
    assert lines[1].isdigit()
    assert len(lines) == int(lines[1]) + 2