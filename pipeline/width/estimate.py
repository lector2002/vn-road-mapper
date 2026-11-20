import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

from pipeline.segmentation.segment import CLASSES, DEFAULT_MODEL as SEG_MODEL

ROAD = [CLASSES.index(c) for c in ("paved", "dirt", "mud", "water")]
CSV_FIELDS = ["filename", "width_m", "horizon", "rows", "residual"]
SAMPLE_ROWS = np.linspace(0.3, 0.97, 15)
MIN_ROWS = 4
MAX_RESIDUAL = 0.1


def road_span(road_row):
    """Left and right edge of the road run nearest the image center in one row, or None."""
    cols = np.flatnonzero(road_row)
    if cols.size == 0:
        return None
    start = cols[np.abs(cols - road_row.size // 2).argmin()]
    left = right = start
    while left > 0 and road_row[left - 1]:
        left -= 1
    while right < road_row.size - 1 and road_row[right + 1]:
        right += 1
    return left, right


def clean_spans(class_map):
    """(row, span_px) for sampled rows where the road run does not touch the image edge."""
    road = np.isin(class_map, ROAD)
    height, width = road.shape
    spans = []
    for frac in SAMPLE_ROWS:
        y = int(height * frac)
        span = road_span(road[y])
        if span and span[0] > 0 and span[1] < width - 1:
            spans.append((y, span[1] - span[0] + 1))
    return spans


def estimate_width(class_map, camera_height_m):
    # On flat ground the road's pixel width grows linearly with the row: span = W * (y - horizon) / h.
    # Fitting that line gives the horizon and W without knowing the lens focal length.
    spans = clean_spans(class_map)
    blank = {"width_m": "", "horizon": "", "rows": len(spans), "residual": ""}
    if len(spans) < MIN_ROWS:
        return blank
    ys, px = np.array(spans, dtype=float).T
    slope, intercept = np.polyfit(ys, px, 1)
    if slope <= 0:
        return blank
    horizon = -intercept / slope
    residual = float(np.sqrt(np.mean((px - (slope * ys + intercept)) ** 2)) / px.mean())
    result = {"horizon": round(horizon / class_map.shape[0], 3), "rows": len(spans), "residual": round(residual, 3)}
    # The top sampled road row sits just under the vanishing point, so allow fit noise of a few rows.
    if residual > MAX_RESIDUAL or horizon > ys.min() + 0.05 * class_map.shape[0]:
        return {**result, "width_m": ""}
    return {**result, "width_m": round(float(slope * camera_height_m), 2)}


def draw(image, class_map, result):
    out = image.copy()
    d = ImageDraw.Draw(out)
    road = np.isin(class_map, ROAD)
    for frac in SAMPLE_ROWS:
        y = int(class_map.shape[0] * frac)
        span = road_span(road[y])
        if span:
            clipped = span[0] == 0 or span[1] == class_map.shape[1] - 1
            d.line([(span[0], y), (span[1], y)], fill=(255, 80, 80) if clipped else (255, 255, 0), width=4)
    if result["horizon"] != "":
        y = int(result["horizon"] * class_map.shape[0])
        d.line([(0, y), (class_map.shape[1], y)], fill=(80, 200, 255), width=2)
    label = f"{result['width_m']} m" if result["width_m"] != "" else "no width"
    d.text((16, 16), label, fill=(255, 255, 0), font_size=max(16, class_map.shape[0] // 18))
    return out


def run(frames_dir, out_dir, camera_height_m, overlays=5, seg_model_id=SEG_MODEL):
    from pipeline.segmentation.segment import Segmenter

    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if not frames:
        raise ValueError(f"no .jpg frames in {frames_dir}")
    out_dir = Path(out_dir)
    (out_dir / "width_overlays").mkdir(parents=True, exist_ok=True)
    keep = set(np.linspace(0, len(frames) - 1, min(overlays, len(frames)), dtype=int).tolist()) if overlays else set()
    segmenter = Segmenter(seg_model_id)
    rows = []
    started = time.perf_counter()
    for i, path in enumerate(frames):
        image = Image.open(path).convert("RGB")
        class_map = segmenter.class_map(image)
        result = estimate_width(class_map, camera_height_m)
        rows.append({"filename": path.name, **result})
        if i in keep:
            draw(image, class_map, result).save(out_dir / "width_overlays" / path.name, quality=85)
    seconds_per_frame = (time.perf_counter() - started) / len(frames)
    csv_path = out_dir / "widths.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, rows, seconds_per_frame


def main(argv=None):
    p = argparse.ArgumentParser(description="Estimate road width in each frame from the road mask and camera height.")
    p.add_argument("frames", type=Path, help="folder of .jpg frames (output of pipeline.frames)")
    p.add_argument("--out", type=Path, required=True, help="output folder (gets widths.csv and width_overlays/)")
    p.add_argument("--camera-height", type=float, required=True, help="height of the phone lens above the road, in m")
    p.add_argument("--overlays", type=int, default=5)
    args = p.parse_args(argv)
    if args.camera_height <= 0:
        sys.exit("error: --camera-height must be positive")
    try:
        csv_path, rows, spf = run(args.frames, args.out, args.camera_height, args.overlays)
    except ValueError as e:
        sys.exit(f"error: {e}")
    measured = sum(1 for r in rows if r["width_m"] != "")
    print(f"{len(rows)} frames -> {csv_path} ({measured} with a width, {spf:.1f} s/frame)")


if __name__ == "__main__":
    main()
