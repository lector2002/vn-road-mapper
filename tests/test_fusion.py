import csv

import pytest

from pipeline.fusion.fuse import fuse, load_run, main


def frame(way, label, confidence=0.9, run="r1", name=None):
    return {"filename": name or f"{way}-{label}.jpg", "way_id": way, "label": label,
            "confidence": str(confidence), "run": run}


def by_way(ways):
    return {w["way_id"]: w for w in ways}


def test_majority_surface_wins_and_agreement_is_its_share_of_votes():
    ways = by_way(fuse([frame("1", "dirt")] * 3 + [frame("1", "paved")]))
    assert ways["1"]["surface"] == "dirt"
    assert ways["1"]["agreement"] == 0.75
    assert ways["1"]["votes"] == 4


def test_low_confidence_frames_do_not_vote():
    ways = by_way(fuse([frame("1", "paved", 0.9), frame("1", "dirt", 0.3), frame("1", "dirt", 0.4)]))
    assert ways["1"]["surface"] == "paved"
    assert ways["1"]["votes"] == 1
    assert ways["1"]["frames"] == 3


def test_vegetation_and_water_frames_do_not_vote_for_surface_but_water_is_reported():
    ways = by_way(fuse([frame("1", "dirt"), frame("1", "water"), frame("1", "water"), frame("1", "vegetation")]))
    assert ways["1"]["surface"] == "dirt"
    assert ways["1"]["agreement"] == 1.0
    assert ways["1"]["water_share"] == 0.5


def test_way_with_no_surface_votes_gets_blank_surface():
    ways = by_way(fuse([frame("1", "vegetation")]))
    assert ways["1"]["surface"] == ""
    assert ways["1"]["agreement"] == ""


def test_passes_counts_distinct_runs():
    ways = by_way(fuse([frame("1", "dirt", run="a"), frame("1", "dirt", run="b"), frame("1", "dirt", run="b")]))
    assert ways["1"]["passes"] == 2


def write_csv(path, fields, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def make_run(folder, labels_by_way):
    folder.mkdir()
    seg, matches = [], []
    for i, (way, label) in enumerate(labels_by_way):
        name = f"{i + 1:06d}.jpg"
        seg.append({"filename": name, "label": label, "confidence": "0.9"})
        matches.append({"filename": name, "way_id": way})
    write_csv(folder / "segmentation.csv", ["filename", "label", "confidence"], seg)
    write_csv(folder / "matches.csv", ["filename", "way_id"], matches)
    return folder


def test_unmatched_frames_are_dropped_when_loading_a_run(tmp_path):
    run = make_run(tmp_path / "r", [("5", "dirt"), ("", "paved")])
    assert [f["way_id"] for f in load_run(run)] == ["5"]


def test_cli_fuses_two_rides_over_the_same_way(tmp_path):
    a = make_run(tmp_path / "a", [("5", "dirt"), ("5", "dirt")])
    b = make_run(tmp_path / "b", [("5", "dirt"), ("5", "paved"), ("6", "paved")])

    main([str(a), str(b), "--out", str(tmp_path / "out")])

    with open(tmp_path / "out" / "ways.csv", encoding="utf-8") as f:
        ways = by_way(list(csv.DictReader(f)))
    assert ways["5"]["surface"] == "dirt"
    assert ways["5"]["passes"] == "2"
    assert float(ways["5"]["agreement"]) == pytest.approx(0.75)
    assert ways["6"]["surface"] == "paved"


def test_width_is_median_of_frames_that_have_one():
    frames = [{**frame("1", "dirt"), "width_m": w} for w in ["3.0", "", "3.4", "9.0"]]
    way = by_way(fuse(frames))["1"]
    assert way["width_m"] == 3.4
    assert way["width_class"] == "one_car"
    assert way["width_frames"] == 3


def test_run_without_widths_csv_gives_blank_width(tmp_path):
    run = make_run(tmp_path / "r", [("5", "dirt")])
    way = by_way(fuse(load_run(run)))["5"]
    assert way["width_m"] == ""
    assert way["width_class"] == ""
    assert way["width_frames"] == 0
