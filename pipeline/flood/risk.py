"""Flood risk of OSM ways from public layers: past flood maps, surface water and elevation.

Every layer is a north-up grid (array, transform) in WGS84; `transform` is a rasterio `Affine` or anything
with its `a`, `c`, `e`, `f` (pixel width, west edge, pixel height (negative), north edge).
"""
import math
from collections import namedtuple

import numpy as np

ROADS = {"trunk", "primary", "secondary", "tertiary", "unclassified", "residential", "track", "living_street",
         "road", "path", "trunk_link", "primary_link", "secondary_link", "tertiary_link"}
RISKS = ("high", "medium", "low")
SAMPLE_M = 25
FEATURES = ["samples", "history", "water", "z_min", "rel_min"]
Grid = namedtuple("Grid", "array transform nodata")


def samples(coords, step_m=SAMPLE_M):
    """Points every `step_m` along a way of (lat, lon) vertices, both ends included."""
    pts = [coords[0]]
    for (la0, lo0), (la1, lo1) in zip(coords, coords[1:]):
        k = math.cos(math.radians((la0 + la1) / 2))
        n = max(1, math.ceil(math.hypot((la1 - la0) * 111_320, (lo1 - lo0) * 111_320 * k) / step_m))
        pts += [(la0 + (la1 - la0) * i / n, lo0 + (lo1 - lo0) * i / n) for i in range(1, n + 1)]
    return np.array(pts, dtype=float)


def at(grid, pts):
    """Grid values at (lat, lon) points; NaN outside the grid or on nodata."""
    a, t = grid.array, grid.transform
    rows = np.floor((pts[:, 0] - t.f) / t.e).astype(int)
    cols = np.floor((pts[:, 1] - t.c) / t.a).astype(int)
    inside = (rows >= 0) & (rows < a.shape[0]) & (cols >= 0) & (cols < a.shape[1])
    out = np.full(len(pts), np.nan)
    out[inside] = a[rows[inside], cols[inside]]
    if grid.nodata is not None:
        out[out == grid.nodata] = np.nan
    return out


def relative_height(dem, radius_px):
    """Height above the mean of the ground within `radius_px` pixels: below zero is lower than its surroundings."""
    z = np.where(np.isnan(dem), np.nanmean(dem), dem).astype(np.float64)
    s = np.pad(z, ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    r, (h, w) = radius_px, z.shape
    y0, y1 = np.clip(np.arange(h) - r, 0, h), np.clip(np.arange(h) + r + 1, 0, h)
    x0, x1 = np.clip(np.arange(w) - r, 0, w), np.clip(np.arange(w) + r + 1, 0, w)
    total = s[y1][:, x1] - s[y0][:, x1] - s[y1][:, x0] + s[y0][:, x0]
    count = (y1 - y0)[:, None] * (x1 - x0)[None, :]
    return (z - total / count).astype(np.float32)


def way_features(coords, history=None, water=None, dem=None, rel=None):
    """Per-way layer values: share of points in a past flood, highest surface-water occurrence (%),
    lowest elevation (m) and lowest height above its surroundings (m). Blank where a layer is missing."""
    pts = samples(coords)
    out = {"samples": len(pts)}
    for name, grid, reduce in (("history", history, np.nanmean), ("water", water, np.nanmax),
                               ("z_min", dem, np.nanmin), ("rel_min", rel, np.nanmin)):
        values = at(grid, pts) if grid is not None else np.array([np.nan])
        if name == "history":
            values = (values > 0).astype(float) if grid is not None else values
        out[name] = round(float(reduce(values)), 3) if not np.all(np.isnan(values)) else ""
    return out


def risk(features, rules):
    """`high`, `medium` or `low` from the way's features, or blank when the layers do not cover it.

    rules: {"history": share of points flooded before that makes a way high,
            "rel": height above surroundings (m) at or under which a low-lying way is high,
            "z": elevation (m) at or under which a way counts as low-lying,
            "water": surface-water occurrence (%) at or over which a way is at least medium}
    """
    f = features
    if f["z_min"] == "" or f["rel_min"] == "":
        return ""
    if f["history"] != "" and f["history"] >= rules["history"]:
        return "high"
    low_lying = f["z_min"] <= rules["z"]
    if low_lying and f["rel_min"] <= rules["rel"]:
        return "high"
    if low_lying or (f["water"] != "" and f["water"] >= rules["water"]):
        return "medium"
    return "low"


def auc(scores, labels):
    """Chance that a flooded way scores above a dry one (ties count half); 0.5 is no better than a coin."""
    scores, labels = np.asarray(scores, float), np.asarray(labels, bool)
    pos, neg = labels.sum(), (~labels).sum()
    if not pos or not neg:
        return float("nan")
    order = scores.argsort(kind="mergesort")
    ranks = np.empty(len(scores))
    s = scores[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and s[j + 1] == s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    return float((ranks[labels].sum() - pos * (pos + 1) / 2) / (pos * neg))
