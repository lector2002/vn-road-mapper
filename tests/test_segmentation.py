import csv
import os

import numpy as np
import pytest
from PIL import Image

from pipeline.segmentation.segment import CLASSES, build_lookup, overlay, road_roi, run, summarize

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


def test_vehicles_in_the_box_do_not_lower_confidence_in_the_surface():
    class_map = frame_with_road("dirt")
    rows, cols = road_roi(*class_map.shape)
    region = class_map[rows, cols]
    region[:, : region.shape[1] // 3] = CLASSES.index("other")
    summary = summarize(class_map)
    assert summary["label"] == "dirt"
    assert summary["confidence"] == 1.0
    assert summary["other"] == pytest.approx(0.33, abs=0.02)


def test_box_mostly_covered_by_non_ground_is_labeled_other():
    class_map = frame_with_road("other")
    rows, cols = road_roi(*class_map.shape)
    class_map[rows, cols][: 10] = CLASSES.index("paved")
    summary = summarize(class_map)
    assert summary["label"] == "other"
    assert summary["confidence"] == summary["other"]


def test_overlay_keeps_image_size():
    class_map = frame_with_road("water")
    image = Image.new("RGB", (100, 100), "white")
    assert overlay(image, class_map, summarize(class_map)).size == (100, 100)


def test_run_keeps_completed_rows_when_a_frame_fails(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(3):
        Image.new("RGB", (20, 20), "white").save(frames / f"{i}.jpg")

    class CrashSegmenter:
        def __init__(self):
            self.count = 0

        def class_map(self, image):
            self.count += 1
            if self.count == 2:
                raise ValueError("bad frame")
            return frame_with_road("paved", height=10, width=10)

    with pytest.raises(ValueError, match="bad frame"):
        run(frames, tmp_path / "out", overlays=0, segmenter=CrashSegmenter())

    with open(tmp_path / "out" / "segmentation.csv", encoding="utf-8") as f:
        assert [r["filename"] for r in csv.DictReader(f)] == ["0.jpg"]


def test_run_resumes_after_completed_frames(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for i in range(3):
        Image.new("RGB", (20, 20), "white").save(frames / f"{i}.jpg")
    out = tmp_path / "out"
    (out / "overlays").mkdir(parents=True)
    with open(out / "segmentation.csv", "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["filename", "label", "confidence", *CLASSES, "p_unpaved"])
        writer.writeheader()
        writer.writerow({"filename": "0.jpg", "label": "paved", "confidence": 1,
                         **{c: 0 for c in CLASSES}, "p_unpaved": ""})

    class FakeSegmenter:
        def __init__(self):
            self.count = 0

        def class_map(self, image):
            self.count += 1
            return frame_with_road("dirt", height=10, width=10)

    fake = FakeSegmenter()
    _, rows, _ = run(frames, out, overlays=0, segmenter=fake)

    assert fake.count == 2
    assert [r["filename"] for r in rows] == ["0.jpg", "1.jpg", "2.jpg"]
    with open(out / "segmentation.csv", encoding="utf-8") as f:
        assert [r["filename"] for r in csv.DictReader(f)] == ["0.jpg", "1.jpg", "2.jpg"]


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
