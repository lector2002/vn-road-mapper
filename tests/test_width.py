import numpy as np
import pytest
from PIL import Image

from pipeline.segmentation.segment import CLASSES
from pipeline.width.estimate import draw, estimate_width, road_span

PAVED, DIRT, VEG = CLASSES.index("paved"), CLASSES.index("dirt"), CLASSES.index("vegetation")


def straight_road(road_m, camera_m, horizon_frac, height=720, width=1280, surface=PAVED):
    """Class map of a flat straight road seen head-on: pixel width = road_m * (y - horizon) / camera_m."""
    class_map = np.full((height, width), VEG)
    horizon = horizon_frac * height
    for y in range(height):
        half = road_m * (y - horizon) / camera_m / 2
        if half > 0:
            left, right = max(0, int(width / 2 - half)), min(width, int(width / 2 + half))
            class_map[y, left:right] = surface
    return class_map


@pytest.mark.parametrize("road_m, camera_m, horizon", [(3.0, 1.1, 0.5), (5.0, 1.2, 0.42), (2.5, 1.0, 0.58)])
def test_width_of_straight_road_is_recovered_with_unknown_horizon(road_m, camera_m, horizon):
    result = estimate_width(straight_road(road_m, camera_m, horizon), camera_m)
    assert result["width_m"] == pytest.approx(road_m, rel=0.03)
    assert result["horizon"] == pytest.approx(horizon, abs=0.01)


def test_rows_where_road_fills_the_frame_are_left_out():
    class_map = straight_road(4.0, 1.1, 0.5)
    class_map[650:, :] = PAVED
    result = estimate_width(class_map, 1.1)
    assert result["width_m"] == pytest.approx(4.0, rel=0.03)


def test_width_scales_with_camera_height():
    class_map = straight_road(3.0, 1.0, 0.5)
    assert estimate_width(class_map, 2.0)["width_m"] == pytest.approx(6.0, rel=0.03)


def test_dirt_and_paved_both_count_as_road():
    class_map = straight_road(3.0, 1.1, 0.5)
    class_map[500:600][class_map[500:600] == PAVED] = DIRT
    assert estimate_width(class_map, 1.1)["width_m"] == pytest.approx(3.0, rel=0.03)


def test_no_width_when_road_is_not_visible():
    result = estimate_width(np.full((720, 1280), VEG), 1.1)
    assert result["width_m"] == ""
    assert result["rows"] == 0


def test_no_width_when_road_mask_is_fragments():
    rng = np.random.default_rng(0)
    class_map = np.full((720, 1280), VEG)
    for y in range(360, 720):
        left = int(rng.integers(300, 600))
        class_map[y, left:left + int(rng.integers(5, 400))] = PAVED
    assert estimate_width(class_map, 1.1)["width_m"] == ""


def test_road_span_picks_the_run_nearest_the_center():
    row = np.zeros(100, dtype=bool)
    row[5:15] = True
    row[45:70] = True
    assert road_span(row) == (45, 69)


def test_overlay_keeps_image_size():
    class_map = straight_road(3.0, 1.1, 0.5)
    result = estimate_width(class_map, 1.1)
    assert draw(Image.new("RGB", (1280, 720)), class_map, result).size == (1280, 720)
