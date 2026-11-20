import csv
import os
import xml.etree.ElementTree as ET

import pytest

from pipeline.export.export import decide, fetch_way, run


def fused(surface="dirt", agreement="0.9", votes="10", way_id="1"):
    return {"way_id": way_id, "surface": surface, "agreement": agreement, "votes": votes, "frames": votes,
            "passes": "1", "water_share": "0.0"}


@pytest.mark.parametrize("surface, current, expected", [
    ("dirt", "", ("add", "unpaved")),
    ("paved", "", ("add", "paved")),
    ("dirt", "asphalt", ("change", "unpaved")),
    ("paved", "ground", ("change", "paved")),
    ("dirt", "gravel", ("agree", "")),
    ("paved", "concrete", ("agree", "")),
    ("mud", "dirt", ("agree", "")),
    ("dirt", "wood", ("unknown", "")),
])
def test_decide_compares_model_surface_with_current_osm_tag(surface, current, expected):
    assert decide(fused(surface), current, 0.7, 5) == expected


@pytest.mark.parametrize("agreement, votes, surface", [("0.6", "10", "dirt"), ("0.9", "3", "dirt"), ("", "0", "")])
def test_decide_skips_weak_or_missing_votes(agreement, votes, surface):
    assert decide(fused(surface, agreement, votes), "", 0.7, 5) == ("weak", "")


def fake_fetch(tags_by_way):
    def fetch(way_id):
        return {"id": int(way_id), "version": 3, "nodes": [10, 11], "tags": tags_by_way[way_id],
                "coords": [(20.0, 105.0), (20.001, 105.001)]}
    return fetch


def write_ways(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_run_writes_osmchange_only_for_add_and_change_and_keeps_other_tags(tmp_path):
    ways_csv = write_ways(tmp_path / "ways.csv", [
        fused("dirt", way_id="1"), fused("paved", way_id="2"), fused("dirt", way_id="3", votes="1")])
    tags = {"1": {"highway": "unclassified", "name": "Đường xóm"}, "2": {"highway": "residential", "surface": "asphalt"},
            "3": {"highway": "track"}}

    rows = run(ways_csv, tmp_path / "out", fetch=fake_fetch(tags))

    assert [r["status"] for r in rows] == ["add", "agree", "weak"]
    root = ET.parse(tmp_path / "out" / "changes.osc").getroot()
    edited = root.findall("./modify/way")
    assert [w.get("id") for w in edited] == ["1"]
    assert edited[0].get("version") == "3"
    assert [n.get("ref") for n in edited[0].findall("nd")] == ["10", "11"]
    assert {t.get("k"): t.get("v") for t in edited[0].findall("tag")} == {
        "highway": "unclassified", "name": "Đường xóm", "surface": "unpaved"}
    page = (tmp_path / "out" / "review.html").read_text(encoding="utf-8")
    assert "/*GEOJSON*/null" not in page and '"way_id": "1"' in page


@pytest.mark.skipif(os.environ.get("RUN_NETWORK_TESTS") != "1", reason="calls the OSM API")
def test_fetch_way_reads_real_osm_way():
    way = fetch_way("590633402")
    assert way["tags"]["highway"] == "unclassified"
    assert len(way["coords"]) == len(way["nodes"]) > 2
