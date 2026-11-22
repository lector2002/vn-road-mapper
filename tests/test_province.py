import csv
import json

import pytest

from tools import province


def box(*bounds):
    return pytest.importorskip("shapely.geometry").box(*bounds)


def write_boundary(out, poly):
    out.mkdir(parents=True, exist_ok=True)
    (out / "boundary.geojson").write_text(json.dumps(
        {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {},
                                                     "geometry": poly.__geo_interface__}]}))


def photo(source, seq, pid, lat, lon, t):
    return {"source": source, "sequence": seq, "photo_id": pid, "sequence_index": "", "lat": lat, "lon": lon,
            "captured_at": t, "heading": "", "url": ""}


def test_thin_keeps_newest_photo_per_cell():
    rows = [photo("mapillary", "a", "1", 18.0, 105.0, 1000), photo("mapillary", "b", "2", 18.0001, 105.0001, 2000),
            photo("kartaview", "c", "3", 18.01, 105.0, 500)]
    kept = province.thin(rows, 50)
    assert sorted(r["photo_id"] for r in kept) == ["2", "3"]


def test_kartaview_photos_only_inside_outline(tmp_path, monkeypatch):
    cache = tmp_path / "kv.json"
    cache.write_text(json.dumps([
        {"id": "1", "nwLat": "18.5", "nwLng": "105.0", "seLat": "18.0", "seLng": "105.5"},
        {"id": "2", "nwLat": "10.5", "nwLng": "106.0", "seLat": "10.0", "seLng": "106.5"}]))
    listed = []

    def list_photos(seq):
        listed.append(seq)
        return [{"id": "10", "lat": "18.2", "lng": "105.2", "shotDate": "2025-01-01 00:00:00", "sequenceIndex": "0",
                 "imageLthUrl": "https://cdn/x.jpg"},
                {"id": "11", "lat": "19.2", "lng": "105.2", "shotDate": "2025-01-01 00:00:01", "sequenceIndex": "1"}]

    monkeypatch.setattr(province.kartaview, "list_photos", list_photos)
    rows = province.kartaview_photos(box(105.0, 18.0, 106.0, 19.0), cache)
    assert listed == ["1"]
    assert [r["photo_id"] for r in rows] == ["10"] and rows[0]["url"] == "https://cdn/x.jpg"


def test_frames_makes_one_run_per_sequence_and_skips_downloaded(tmp_path, monkeypatch):
    rows = [photo("mapillary", "s1", "1", 18.0, 105.0, 1_700_000_000_000),
            photo("mapillary", "s1", "2", 18.001, 105.0, 1_700_000_001_000),
            photo("kartaview", "9", "3", 18.002, 105.0, 1_700_000_002_000)]
    province.write(tmp_path / "imagery.csv", province.IMAGERY_FIELDS, rows)
    got = []
    monkeypatch.setattr(province, "download", lambda r, target: (got.append(r["photo_id"]), target.write_bytes(b"x")))
    province.frames(tmp_path, log=lambda *a: None)
    assert sorted(got) == ["1", "2", "3"]
    run = tmp_path / "runs" / "mapillary-s1"
    assert [r["filename"] for r in province.read(run / "frames.csv")] == ["1.jpg", "2.jpg"]
    assert province.read(run / "frames.csv")[0]["timestamp"] == "2023-11-14T22:13:20.000Z"
    assert province.read(tmp_path / "runs" / "kartaview-9" / "kartaview.csv")[0]["sequence_id"] == "9"
    got.clear()
    province.frames(tmp_path, log=lambda *a: None)
    assert got == []


def test_match_uses_present_frames_and_skips_done_runs(tmp_path, monkeypatch):
    run = tmp_path / "runs" / "mapillary-s1"
    (run / "frames").mkdir(parents=True)
    province.write(run / "frames.csv", ["filename", "timestamp", "lat", "lon", "heading"],
                   [{"filename": f"{i}.jpg", "timestamp": "2025-01-01T00:00:0%dZ" % i, "lat": 18, "lon": 105, "heading": ""}
                    for i in range(3)])
    for i in (0, 1):
        (run / "frames" / f"{i}.jpg").write_bytes(b"x")
    calls = []

    def fake_run(frames_csv, out_dir, url, costing):
        rows = province.read(frames_csv)
        calls.append((len(rows), url, costing))
        return None, [{"filename": r["filename"], "way_id": "1", "matched_lat": "", "matched_lon": "", "distance_m": ""}
                      for r in rows]

    from pipeline.mapmatch import match as mm
    monkeypatch.setattr(mm, "run", fake_run)
    province.match(tmp_path, "http://localhost:8002", log=lambda *a: None)
    province.match(tmp_path, "http://localhost:8002", log=lambda *a: None)
    assert calls == [(2, "http://localhost:8002", "motor_scooter")]
    (run / "frames" / "1.jpg").unlink()
    (run / "frames" / "2.jpg").write_bytes(b"x")
    province.match(tmp_path, "http://localhost:8002", log=lambda *a: None)
    assert len(calls) == 2 and {m["filename"] for m in province.read(run / "matches.csv")} == {"0.jpg", "2.jpg"}


def test_match_stops_without_caching_when_valhalla_is_down(tmp_path, monkeypatch):
    run = tmp_path / "runs" / "mapillary-s1"
    (run / "frames").mkdir(parents=True)
    province.write(run / "frames.csv", ["filename", "timestamp", "lat", "lon", "heading"],
                   [{"filename": f"{i}.jpg", "timestamp": "2025-01-01T00:00:0%dZ" % i, "lat": 18, "lon": 105, "heading": ""}
                    for i in range(4)])
    for i in range(4):
        (run / "frames" / f"{i}.jpg").write_bytes(b"x")

    def down(*a, **k):
        raise ConnectionRefusedError("connection refused")

    from pipeline.mapmatch import match as mm
    monkeypatch.setattr(mm, "run", down)
    with pytest.raises(OSError):
        province.match(tmp_path, "http://localhost:8002", log=lambda *a: None)
    assert not (run / "matches.csv").exists()


def test_timed_appends_step_seconds(tmp_path, capsys):
    assert province.timed(tmp_path, "frames", lambda: 3) == 3
    province.timed(tmp_path, "segment", lambda: None)
    with open(tmp_path / "timings.csv") as f:
        assert [r["step"] for r in csv.DictReader(f)] == ["frames", "segment"]


def test_outline_reads_boundary(tmp_path):
    write_boundary(tmp_path, box(1, 2, 3, 4))
    assert province.outline(tmp_path).bounds == (1, 2, 3, 4)


def test_db_rows_from_step_files(tmp_path, monkeypatch):
    write_boundary(tmp_path, box(105, 18, 106, 19))
    data = json.loads((tmp_path / "boundary.geojson").read_text())
    data["features"][0]["properties"]["name"] = "Tỉnh Hà Tĩnh"
    (tmp_path / "boundary.geojson").write_text(json.dumps(data))

    class FakeWays:
        def __init__(self, pbf):
            self.ways = {"7": {"id": 7, "tags": {"highway": "track"}, "coords": [(18.1, 105.1), (18.2, 105.2)]},
                         "8": {"id": 8, "tags": {"highway": "footway"}, "coords": [(18.1, 105.1), (18.2, 105.2)]}}

    monkeypatch.setattr(province, "Ways", FakeWays)
    province.write(tmp_path / "flood_risk.csv", province.FLOOD_FIELDS,
                   [{"way_id": 7, "history": "", "water": "3", "z_min": "2.5", "rel_min": "-1", "flood_risk": "high"}])
    rows = province.db_rows(tmp_path)
    assert rows["roads"] == [(7, "Tỉnh Hà Tĩnh", "track", "", "", "LINESTRING(105.1 18.1,105.2 18.2)")]
    assert rows["flood"] == [(7, "Tỉnh Hà Tĩnh", None, 3.0, 2.5, -1.0, "high")]
    assert rows["votes"] == [] and rows["proposals"] == []


def test_summary_counts_coverage_by_class(tmp_path):
    province.write(tmp_path / "flood_risk.csv", province.FLOOD_FIELDS,
                   [{"way_id": 1, "highway": "track", "length_m": 500, "flood_risk": "high"},
                    {"way_id": 2, "highway": "track", "length_m": 1500, "flood_risk": "low"}])
    province.write(tmp_path / "ways.csv", ["way_id", "surface"], [{"way_id": 1, "surface": "unpaved"}])
    province.write(tmp_path / "proposals.csv", ["way_id", "status", "proposed_surface"],
                   [{"way_id": 1, "status": "add", "proposed_surface": "unpaved"}])
    province.write(tmp_path / "imagery.csv", province.IMAGERY_FIELDS, [photo("mapillary", "s", "1", 18, 105, 1)])
    province.write(tmp_path / "timings.csv", ["step", "seconds", "finished"], [{"step": "frames", "seconds": 9}])
    (tmp_path / "runs").mkdir()
    s = province.summary(tmp_path, log=lambda *a: None)
    assert s["road_km"] == 2.0 and s["road_km_with_call"] == 0.5
    assert s["km_by_highway"] == {"track": [2.0, 0.5]}
    assert s["flood_risk_with_call"] == {"high": 1} and s["proposed_tags"] == {"unpaved": 1}
    assert s["seconds"] == {"frames": 9}


def test_pieces_split_where_photos_are_far_apart():
    rows = [{"lat": 18.0, "lon": 105.0}, {"lat": 18.0005, "lon": 105.0}, {"lat": 18.05, "lon": 105.0}]
    assert [len(p) for p in province.pieces(rows, 1000)] == [2, 1]
    assert province.pieces([]) == []


def test_pending_segmentation_skips_runs_labelled_beyond_their_frames(tmp_path):
    run = tmp_path / "runs" / "mapillary-s1"
    (run / "frames").mkdir(parents=True)
    province.write(run / "frames.csv", ["filename"], [{"filename": "0.jpg"}])
    (run / "frames" / "0.jpg").write_bytes(b"x")
    assert province.pending_segmentation(tmp_path) == [run]
    province.write(run / "segmentation.csv", ["filename"], [{"filename": "0.jpg"}, {"filename": "extra.jpg"}])
    assert province.pending_segmentation(tmp_path) == []


def test_seconds_by_step_sums_reruns(tmp_path, capsys):
    for seconds in (2, 3):
        province.timed(tmp_path, "segment", lambda s=seconds: s)
    rows = province.read(tmp_path / "timings.csv")
    assert set(province.seconds_by_step(tmp_path)) == {"segment"}
    assert province.seconds_by_step(tmp_path)["segment"] == sum(int(r["seconds"]) for r in rows)


def test_runs_of_leaves_out_sequences_a_refresh_dropped(tmp_path):
    for name in ("mapillary-old", "mapillary-new"):
        (tmp_path / "runs" / name).mkdir(parents=True)
        province.write(tmp_path / "runs" / name / "frames.csv", ["filename"], [])
    assert [p.name for p in province.runs_of(tmp_path)] == ["mapillary-new", "mapillary-old"]
    province.write(tmp_path / "imagery.csv", ["source", "sequence"], [{"source": "mapillary", "sequence": "new"}])
    assert [p.name for p in province.runs_of(tmp_path)] == ["mapillary-new"]


def test_kartaview_sequences_lists_again_when_cache_is_old(tmp_path, monkeypatch):
    import os
    cache = tmp_path / "kv.json"
    cache.write_text(json.dumps([{"id": 1}]))
    pages = []

    def get(url):
        pages.append(url)
        return json.dumps({"result": {"data": [{"id": 2}], "hasMoreData": False}}).encode()

    monkeypatch.setattr(province.kartaview, "get", get)
    assert province.kartaview_sequences(cache) == [{"id": 1}] and not pages
    old = cache.stat().st_mtime - 8 * 86400
    os.utime(cache, (old, old))
    assert [s["id"] for s in province.kartaview_sequences(cache)] == [2] and len(pages) == 1
