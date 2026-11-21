import csv
import json
import urllib.error

import pytest

from tools import pilot


def write_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def proposal(way_id, status="add", proposed="unpaved", highway="unclassified", votes="8"):
    return {"way_id": way_id, "status": status, "current_surface": "", "proposed_surface": proposed,
            "surface": "dirt" if proposed == "unpaved" else "paved", "agreement": "0.9", "votes": votes,
            "water_share": "0.0", "width_m": "", "name": "", "highway": highway}


@pytest.fixture
def run_dir(tmp_path):
    run = tmp_path / "run"
    run.mkdir()
    frames = [f"{i:06d}.jpg" for i in range(1, 7)]
    ways = ["1", "1", "1", "1", "2", "3"]
    labels = ["dirt", "dirt", "paved", "dirt", "paved", "paved"]
    write_csv(run / "matches.csv", [{"filename": f, "way_id": w} for f, w in zip(frames, ways)])
    write_csv(run / "segmentation.csv", [{"filename": f, "label": l, "confidence": "1.0"} for f, l in zip(frames, labels)])
    write_csv(run / "kartaview.csv", [{"filename": f, "photo_id": str(100 + i), "kartaview_way_id": "",
                                       "sequence_id": "77", "sequence_index": str(i)} for i, f in enumerate(frames)])
    return run


def test_photos_are_only_those_that_voted_for_the_proposal(run_dir):
    photos = pilot.photos_by_way([run_dir])
    assert photos["1"]["unpaved"] == [f"https://kartaview.org/details/77/{i}/track-info" for i in (0, 1, 3)]
    assert photos["1"]["paved"] == ["https://kartaview.org/details/77/2/track-info"]


def test_spread_keeps_both_ends():
    assert pilot.spread(list(range(9)), 3) == [0, 4, 8]
    assert pilot.spread([1, 2], 3) == [1, 2]


def test_pick_keeps_untagged_small_roads_with_photos_unpaved_first(run_dir):
    proposals = [proposal("2", proposed="paved", votes="20"), proposal("1"), proposal("3", status="agree"),
                 proposal("4"), proposal("2", highway="trunk")]
    rows = pilot.pick(proposals, pilot.photos_by_way([run_dir]))
    assert [r["way_id"] for r in rows] == ["1", "2"]
    assert rows[0]["osm"] == "https://www.openstreetmap.org/way/1"
    assert len(rows[0]["photos"].split()) == 3


def fake_fetch(tagged=(), gone=()):
    def fetch(way_id):
        if way_id in gone:
            raise urllib.error.HTTPError("u", 410, "Gone", {}, None)
        tags = {"highway": "unclassified", **({"surface": "asphalt"} if way_id in tagged else {})}
        return {"id": int(way_id), "version": 2, "nodes": [1, 2], "tags": tags,
                "coords": [(10.0, 105.0), (10.001, 105.002)]}
    return fetch


def test_build_writes_tag_fix_tasks_and_drops_ways_tagged_since(tmp_path, run_dir):
    write_csv(tmp_path / "proposals.csv", [proposal("1"), proposal("2", proposed="paved")])
    rows = pilot.build(tmp_path / "proposals.csv", [run_dir], tmp_path / "out", fetch=fake_fetch(tagged={"2"}))
    assert [r["way_id"] for r in rows] == ["1"]
    lines = (tmp_path / "out" / "challenge.geojson").read_text(encoding="utf-8").rstrip("\n").split("\n")
    assert len(lines) == 1 and lines[0].startswith("\x1e")
    task = json.loads(lines[0][1:])
    feature = task["features"][0]
    assert feature["properties"]["id"] == "way/1"
    assert feature["properties"]["photo_1"].startswith("https://kartaview.org/details/77/")
    assert feature["geometry"]["coordinates"][0] == [105.0, 10.0]
    assert task["cooperativeWork"] == {"meta": {"version": 2, "type": 1}, "operations": [{
        "operationType": "modifyElement",
        "data": {"id": "way/1", "operations": [{"operation": "setTags", "data": {"surface": "unpaved"}}]}}]}
    assert (tmp_path / "out" / "pilot.csv").read_text(encoding="utf-8").startswith("way_id,osm,")
    assert '"way_id": "1"' in (tmp_path / "out" / "review.html").read_text(encoding="utf-8")


@pytest.mark.parametrize("column, values, expected", [
    ("decision", ["accept"] * 9 + ["reject", ""], (9, 1, 1, True)),
    ("Task Status", ["Fixed"] * 8 + ["Not an Issue"] * 2 + ["Skipped"], (8, 2, 1, False)),
    ("TaskStatus", ["Fixed"] * 19 + ["Not_An_Issue", "Too_Hard", "Already_Fixed"], (19, 1, 2, True)),
])
def test_score_counts_accepted_against_the_90_percent_bar(tmp_path, column, values, expected):
    write_csv(tmp_path / "s.csv", [{"way_id": str(i), column: v} for i, v in enumerate(values)])
    r = pilot.score(tmp_path / "s.csv")
    assert (r["accepted"], r["rejected"], r["undecided"], r["passes"]) == expected


def test_score_without_a_decision_column_is_an_error(tmp_path):
    write_csv(tmp_path / "s.csv", [{"way_id": "1", "other": "x"}])
    with pytest.raises(ValueError):
        pilot.score(tmp_path / "s.csv")


def test_limit_counts_only_ways_still_untagged(tmp_path, run_dir):
    write_csv(tmp_path / "proposals.csv", [proposal("1"), proposal("2", proposed="paved")])
    rows = pilot.build(tmp_path / "proposals.csv", [run_dir], tmp_path / "out", limit=1,
                       fetch=fake_fetch(gone={"1"}))
    assert [r["way_id"] for r in rows] == ["2"]
