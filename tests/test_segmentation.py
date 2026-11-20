import csv
import os

import numpy as np
import pytest
from PIL import Image

from pipeline.segmentation.segment import CLASSES, build_lookup, overlay, road_roi, run, summarize, tilt

FAKE_ID2LABEL = {0: "wall", 1: "road", 2: "dirt track", 3: "water", 4: "tree", 5: "bed "}


def frame_with_road(road_class, background_class="vegetation", height=100, width=100):
    class_map = np.full((height, width), CLASSES.index(background_class))
    rows, cols = road_roi(height, width)
    class_map[rows, cols] = CLASSES.index(road_class)
    return class_map


def test_lookup_maps_known_labels_and_sends_unknown_to_other():
    lookup = build_lookup(FAKE_ID2LABEL)
    assert [CLASSES[i] for i in lookup] == ["other", "paved", "dirt", "water", "vegetation", "other"]


def test_lookup_ignores_trailing_spaces_in_model_labels():
    lookup = build_lookup({0: "road "})
    assert CLASSES[lookup[0]] == "paved"


def test_every_class_except_mud_has_a_source_label():
    from pipeline.segmentation.segment import ADE20K_TO_CLASS
    covered = set(ADE20K_TO_CLASS.values())
    assert covered == set(CLASSES) - {"mud", "other"}


def test_summary_reads_only_the_road_region_in_front_of_the_bike():
    summary = summarize(frame_with_road("dirt", background_class="water"))
    assert summary["label"] == "dirt"
    assert summary["confidence"] == 1.0
    assert summary["water"] == 0.0


def test_summary_shares_add_up_to_one_and_confidence_is_winning_share():
    class_map = frame_with_road("paved")
    rows, cols = road_roi(*class_map.shape)
    region = class_map[rows, cols]
    region[: region.shape[0] // 4] = CLASSES.index("water")
    summary = summarize(class_map)
    assert summary["label"] == "paved"
    assert summary["confidence"] == summary["paved"] == pytest.approx(0.75, abs=0.01)
    assert sum(summary[c] for c in CLASSES) == pytest.approx(1.0, abs=0.01)


def bottom_half_road():
    class_map = np.full((100, 100), CLASSES.index("vegetation"))
    class_map[50:] = CLASSES.index("paved")
    return class_map


def test_tilt_is_near_zero_when_road_is_at_the_bottom():
    assert abs(tilt(bottom_half_road())) <= 5


@pytest.mark.parametrize("side, expected", [("left", -90), ("right", 90)])
def test_tilt_is_near_90_when_phone_turned_sideways(side, expected):
    class_map = np.full((100, 100), CLASSES.index("vegetation"))
    cols = slice(0, 50) if side == "left" else slice(50, 100)
    class_map[:, cols] = CLASSES.index("paved")
    assert tilt(class_map) == pytest.approx(expected, abs=5)


def test_tilt_is_near_180_when_frame_is_upside_down():
    assert abs(tilt(np.flipud(bottom_half_road()))) >= 175


@pytest.mark.parametrize("road_class", ["paved", "vegetation"])
def test_tilt_is_unknown_when_road_fills_or_misses_the_frame(road_class):
    assert tilt(np.full((100, 100), CLASSES.index(road_class))) is None


def test_tilt_is_unknown_when_little_road_is_seen():
    class_map = np.full((100, 100), CLASSES.index("vegetation"))
    class_map[:, :30] = CLASSES.index("dirt")
    assert tilt(class_map) is None


def test_overlay_keeps_image_size():
    class_map = frame_with_road("water")
    image = Image.new("RGB", (100, 100), "white")
    assert overlay(image, class_map, summarize(class_map)).size == (100, 100)


@pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="downloads a 110 MB model; set RUN_MODEL_TESTS=1")
def test_real_model_writes_one_row_per_frame_and_overlays(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(3):
        Image.new("RGB", (320, 240), (120 + i * 20, 120, 120)).save(frames / f"{i + 1:06d}.jpg")

    csv_path, rows, _ = run(frames, tmp_path / "out", overlays=2)

    with open(csv_path, encoding="utf-8") as f:
        assert [r["filename"] for r in csv.DictReader(f)] == ["000001.jpg", "000002.jpg", "000003.jpg"]
    assert all(r["label"] in CLASSES for r in rows)
    assert len(list((tmp_path / "out" / "overlays").glob("*.jpg"))) == 2
