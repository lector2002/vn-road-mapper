import csv
import os
from collections import Counter

import pytest

from pipeline.mapmatch import match
from pipeline.mapmatch.match import build_request, parse_response

# Points along OSM way 590633402, an unpaved road near Hoa Binh.
ROAD = [(20.7994696, 105.356364), (20.7998703, 105.3560994), (20.8002063, 105.3555683), (20.8003703, 105.3553349),
        (20.8006777, 105.3550909), (20.8010638, 105.3548066), (20.8012293, 105.3546939), (20.8019492, 105.354075)]
ROAD_WAY = 590633402


def frame_rows(points, start_second=0):
    return [{"filename": f"{i + 1:06d}.jpg", "timestamp": f"2026-03-01T02:00:{start_second + 3 * i:02d}.000Z",
             "lat": str(lat), "lon": str(lon), "heading": ""} for i, (lat, lon) in enumerate(points)]


def write_frames_csv(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "timestamp", "lat", "lon", "heading"])
        writer.writeheader()
        writer.writerows(rows)
    return path


def test_request_carries_one_shape_point_per_frame_with_epoch_time():
    body = build_request(frame_rows(ROAD[:2]), "auto")
    assert body["shape"][0] == {"lat": 20.7994696, "lon": 105.356364, "time": 1772330400}
    assert body["shape"][1]["time"] == 1772330403
    assert body["costing"] == "auto"


def test_response_maps_matched_and_interpolated_points_to_way_and_leaves_unmatched_blank():
    rows = frame_rows(ROAD[:3])
    response = {
        "edges": [{"way_id": 11}, {"way_id": 22}],
        "matched_points": [
            {"lat": 20.1, "lon": 105.1, "type": "matched", "edge_index": 0, "distance_from_trace_point": 3.21},
            {"lat": 20.2, "lon": 105.2, "type": "interpolated", "edge_index": 1, "distance_from_trace_point": 0.5},
            {"lat": 20.3, "lon": 105.3, "type": "unmatched"},
        ],
    }
    out = parse_response(rows, response)
    assert [m["way_id"] for m in out] == [11, 22, ""]
    assert out[0]["distance_m"] == 3.2
    assert out[2]["matched_lat"] == ""


def test_response_with_invalid_edge_index_counts_as_unmatched():
    out = parse_response(frame_rows(ROAD[:1]), {
        "edges": [], "matched_points": [{"lat": 1, "lon": 2, "type": "matched", "edge_index": 4294967295}]})
    assert out[0]["way_id"] == ""


def test_frames_without_gps_stay_in_output_with_blank_way(tmp_path, monkeypatch):
    rows = frame_rows(ROAD[:2]) + [{"filename": "000003.jpg", "timestamp": "2026-03-01T02:00:09.000Z",
                                    "lat": "", "lon": "", "heading": ""}]
    sent = {}

    def fake_post(url, body):
        sent["points"] = len(body["shape"])
        return {"edges": [{"way_id": 7}], "matched_points": [
            {"lat": 1, "lon": 2, "type": "matched", "edge_index": 0, "distance_from_trace_point": 1}] * 2}

    monkeypatch.setattr(match, "post_trace", fake_post)
    _, matches = match.run(write_frames_csv(tmp_path / "frames.csv", rows), tmp_path / "out")
    assert sent["points"] == 2
    assert [m["way_id"] for m in matches] == [7, 7, ""]


@pytest.mark.skipif(os.environ.get("RUN_NETWORK_TESTS") != "1", reason="calls the public Valhalla server")
def test_trace_along_real_road_matches_mostly_to_that_way(tmp_path):
    _, matches = match.run(write_frames_csv(tmp_path / "frames.csv", frame_rows(ROAD)), tmp_path / "out")
    ways = Counter(m["way_id"] for m in matches)
    assert ways.most_common(1)[0][0] == ROAD_WAY
    assert ways[ROAD_WAY] >= len(ROAD) // 2
