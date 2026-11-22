from collections import namedtuple

import numpy as np
import pytest

from pipeline.flood.risk import Grid, at, auc, relative_height, risk, samples, way_features

T = namedtuple("T", "a c e f")
RULES = {"history": 0.2, "rel": -1.0, "z": 5.0, "water": 50}


def grid(array, nodata=None):
    # 0.001 degree pixels, north-west corner at (10.01 N, 105.0 E)
    return Grid(np.asarray(array, float), T(0.001, 105.0, -0.001, 10.01), nodata)


def test_samples_every_25_m_with_both_ends():
    pts = samples([(10.0, 105.0), (10.0, 105.0 + 100 / (111_320 * np.cos(np.radians(10))))])
    assert len(pts) == 5
    assert tuple(pts[0]) == (10.0, 105.0) and pts[-1][1] > pts[-2][1]


def test_at_reads_pixel_and_gives_nan_outside_or_nodata():
    g = grid([[1, 2], [3, 255]], nodata=255)
    v = at(g, np.array([[10.0095, 105.0005], [10.0085, 105.0005], [10.0085, 105.0015], [9.0, 105.0]]))
    assert v[0] == 1 and v[1] == 3 and np.isnan(v[2]) and np.isnan(v[3])


def test_relative_height_negative_in_a_hollow():
    dem = np.full((9, 9), 10.0)
    dem[4, 4] = 1.0
    rel = relative_height(dem, 2)
    assert rel[4, 4] < -8 and rel[0, 0] == pytest.approx(0)


def test_way_features_and_blank_without_layer():
    way = [(10.0095, 105.0002), (10.0095, 105.0008)]
    f = way_features(way, history=grid([[1, 0]]), water=grid([[60, 0]]), dem=grid([[3, 9]]), rel=grid([[-2, 0]]))
    assert f["history"] == 1.0 and f["water"] == 60 and f["z_min"] == 3 and f["rel_min"] == -2
    assert way_features(way)["z_min"] == ""


@pytest.mark.parametrize("f, expected", [
    ({"history": 0.5, "water": 0, "z_min": 30, "rel_min": 5}, "high"),
    ({"history": 0.0, "water": 0, "z_min": 3, "rel_min": -2}, "high"),
    ({"history": 0.0, "water": 0, "z_min": 3, "rel_min": 1}, "medium"),
    ({"history": 0.0, "water": 80, "z_min": 30, "rel_min": 1}, "medium"),
    ({"history": 0.0, "water": 0, "z_min": 30, "rel_min": -3}, "low"),
    ({"history": "", "water": "", "z_min": "", "rel_min": ""}, ""),
])
def test_risk_classes(f, expected):
    assert risk(f, RULES) == expected


def test_auc():
    assert auc([1, 2, 3, 4], [0, 0, 1, 1]) == 1.0
    assert auc([1, 1, 1, 1], [0, 1, 0, 1]) == 0.5
    assert np.isnan(auc([1, 2], [1, 1]))


def row(flooded, z, rel=0.0, history=0.0, water=0.0, split="dev"):
    return {"split": split, "flooded": flooded, "history": history, "water": water, "z_min": z, "rel_min": rel}


def test_score_counts_flooded_roads_per_class():
    from tools.floodcheck import score
    rows = [row(1, 2, -2), row(1, 2, 0), row(0, 2, 0), row(0, 30), row(0, 30), row(0, "", "")]
    result = score(rows, RULES)
    assert result["classes"]["high"] == {"roads": 1, "flooded": 1}
    assert result["classes"]["medium"] == {"roads": 2, "flooded": 1}
    assert result["classes"][""] == {"roads": 1, "flooded": 0}
    assert result["caught"] == 0.5 and result["auc"] > 0.8


def test_fit_keeps_rules_whose_high_class_catches_enough():
    from tools.floodcheck import fit
    rows = [row(1, 7, -2), row(1, 4, -0.7), row(0, 30, 0), row(0, 25, -3), row(0, 7, 1)]
    rules = fit(rows, min_caught=1.0)
    assert rules["z"] >= 7 and rules["rel"] >= -0.7


def test_burn_marks_polygon_pixels():
    pytest.importorskip("rasterio")
    pytest.importorskip("shapely")
    from shapely.geometry import box

    from tools.floodcheck import burn
    g = burn([box(105.0, 10.0, 105.001, 10.001), box(110, 20, 111, 21)], (105.0, 10.0, 105.002, 10.002))
    assert g.array.shape == (20, 20) and g.array.sum() == 100
    v = at(g, np.array([[10.0005, 105.0005], [10.0015, 105.0015]]))
    assert v.tolist() == [1, 0]


def test_samples_ignore_dense_vertices():
    m = 1 / (111_320 * np.cos(np.radians(10)))
    dense = [(10.0, 105.0 + i * m) for i in range(10)] + [(10.0, 105.0 + 100 * m)]
    assert len(samples(dense)) == 5
    assert len(samples([(10.0, 105.0), (10.0, 105.0)])) == 1


def test_samples_do_not_bunch_at_the_end():
    m = 1 / (111_320 * np.cos(np.radians(10)))
    pts = samples([(10.0, 105.0), (10.0, 105.0 + 101 * m)])
    assert len(pts) == 6
    assert np.diff(pts[:, 1]).min() > 20 * m


def test_short_roads_get_a_middle_point():
    m = 1 / (111_320 * np.cos(np.radians(10)))
    assert len(samples([(10.0, 105.0), (10.0, 105.0 + 35 * m)])) == 3
