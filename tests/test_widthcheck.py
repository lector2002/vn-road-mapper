import pytest

import json

from tools import mapillary
from tools.widthcheck import find_photos, images_in, metres, on_way, pick, project, score, split

# A straight north-south way about 111 m long at the equator.
WAY = [(0.0, 0.0), (0.001, 0.0)]


@pytest.mark.parametrize("value, expected", [
    ("3", 3.0), ("3.5 m", 3.5), ("2,5", 2.5), ("4 metres", 4.0),
    ("3-4", None), ("narrow", None), ("", None), (None, None), ("2102", None), ("0.2", None),
])
def test_metres_reads_plain_numbers_only(value, expected):
    assert metres(value) == expected


def test_project_gives_distance_and_position_along_the_way():
    dist, along, length, bearing = project(0.0005, 0.00002, WAY)
    assert dist == pytest.approx(2.2, abs=0.1)
    assert along == pytest.approx(55, abs=1)
    assert length == pytest.approx(110.5, abs=1)
    assert bearing == pytest.approx(0, abs=0.5)


def test_photo_on_the_way_looking_along_it_counts_either_direction():
    assert on_way(0.0005, 0.0, 0, WAY, []) == (0.0, 0.0)
    assert on_way(0.0005, 0.0, 185, WAY, []) == (0.0, 5.0)


@pytest.mark.parametrize("lat, lon, heading, reason", [
    (0.0005, 0.0001, 0, "11 m off the way"),
    (0.00005, 0.0, 0, "at the junction end"),
    (0.0005, 0.0, 90, "looking across the way"),
])
def test_photo_left_out(lat, lon, heading, reason):
    assert on_way(lat, lon, heading, WAY, []) is None, reason


def test_photo_as_close_to_another_highway_is_left_out():
    parallel = [(0.0, 0.00003), (0.001, 0.00003)]
    assert on_way(0.0005, 0.000015, 0, WAY, [parallel]) is None
    far = [(0.0, 0.001), (0.001, 0.001)]
    assert on_way(0.0005, 0.000015, 0, WAY, [far]) is not None


def test_pick_caps_photos_per_sequence_and_way():
    photos = [{"way_id": "1", "image_id": str(i), "sequence": "a" if i < 6 else "b", "dist_m": "1", "heading_off": str(i)}
              for i in range(10)]
    got = pick(photos, per_way=4, per_sequence=3)
    assert [p["image_id"] for p in got] == ["0", "1", "2", "6"]


def test_split_is_fixed_per_way():
    assert split(123) == split("123")
    assert {split(i) for i in range(20)} == {"dev", "test"}


def test_score_uses_median_frame_width_per_way_and_skips_ways_without_one():
    photos = [
        {"way_id": "1", "osm_class": "one_car", "split": "test", "image_id": "a"},
        {"way_id": "1", "osm_class": "one_car", "split": "test", "image_id": "b"},
        {"way_id": "1", "osm_class": "one_car", "split": "test", "image_id": "c"},
        {"way_id": "2", "osm_class": "motorbike", "split": "test", "image_id": "d"},
        {"way_id": "3", "osm_class": "two_cars", "split": "dev", "image_id": "e"},
    ]
    widths = [{"filename": "a.jpg", "width_m": "3.0"}, {"filename": "b.jpg", "width_m": "9.0"},
              {"filename": "c.jpg", "width_m": "3.5"}, {"filename": "d.jpg", "width_m": ""},
              {"filename": "e.jpg", "width_m": "3.0"}]
    result = score(photos, widths)
    assert result["test"] == {"ways": 2, "classed": 1, "right": 1,
                              "confusion": {"motorbike": [0, 0, 0], "one_car": [0, 1, 0], "two_cars": [0, 0, 0]}}
    assert result["dev"]["right"] == 0 and result["dev"]["confusion"]["two_cars"] == [0, 1, 0]
    baseline = score(photos, widths, lambda way, ws: "two_cars")
    assert baseline["all"] == {**baseline["all"], "classed": 3, "right": 1}


def photo(lat, lon, computed, compass=90):
    return {"id": f"{lat}", "captured_at": 0, "camera_type": "perspective", "computed_compass_angle": computed,
            "compass_angle": compass, "geometry": {"coordinates": [lon, lat]}, "sequence": "s"}


TAGGED = {"way_id": 1, "width": 3.0, "coords": json.dumps(WAY)}


def test_find_photos_keeps_a_north_facing_photo():
    got = find_photos([TAGGED], [], search=lambda bbox: [photo(0.0005, 0.0, 0)])
    assert len(got) == 1 and got[0]["heading_off"] == 0.0


def test_find_photos_sees_a_long_neighbour_with_no_vertex_nearby():
    # Parallel road 3 m away whose only vertices are 5 km to either side.
    neighbour = {"way_id": 2, "coords": json.dumps([(-0.045, 0.00003), (0.045, 0.00003)])}
    got = find_photos([TAGGED], [neighbour], search=lambda bbox: [photo(0.0005, 0.000015, 0)])
    assert got == []


def test_images_in_reads_every_page(monkeypatch):
    monkeypatch.setattr(mapillary, "graph", lambda path, **kw: {"data": [1, 2], "paging": {"next": "p2"}})
    pages = {"p2": {"data": [3], "paging": {"next": "p3"}}, "p3": {"data": [4]}}
    monkeypatch.setattr(mapillary, "read", lambda url: pages[url])
    assert images_in("0,0,1,1") == [1, 2, 3, 4]
