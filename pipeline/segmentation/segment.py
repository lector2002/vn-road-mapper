import argparse
import csv
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

DEFAULT_MODEL = "nvidia/segformer-b2-finetuned-ade-512-512"
CLASSES = ["paved", "dirt", "mud", "water", "vegetation", "other"]
COLORS = {
    "paved": (90, 90, 90), "dirt": (205, 133, 63), "mud": (110, 70, 30),
    "water": (30, 110, 255), "vegetation": (40, 180, 60), "other": (0, 0, 0),
}
# ADE20K label -> our class. Chosen from a probe on 12 Vietnamese road photos (docs/decisions/).
# No ADE20K label means mud; "mud" stays empty until the model is fine-tuned on VN frames.
ADE20K_TO_CLASS = {
    "road": "paved", "sidewalk": "paved", "runway": "paved",
    "dirt track": "dirt", "earth": "dirt", "land": "dirt", "sand": "dirt", "path": "dirt",
    "water": "water", "river": "water", "lake": "water", "sea": "water",
    "tree": "vegetation", "grass": "vegetation", "plant": "vegetation", "field": "vegetation",
    "flower": "vegetation", "palm": "vegetation",
}
CSV_FIELDS = ["filename", "label", "confidence", *CLASSES, "p_unpaved"]
# The road in front of a bike-mounted phone: bottom 40% of the frame, middle 60% of the width.
ROI_TOP, ROI_LEFT, ROI_RIGHT = 0.6, 0.2, 0.8
# Vehicles, people and bike parts in the box are "other"; they hide the surface rather than describe it.
MIN_GROUND = 0.4


def build_lookup(id2label, mapping=ADE20K_TO_CLASS):
    other = CLASSES.index("other")
    lookup = np.full(max(id2label) + 1, other, dtype=np.int64)
    for i, name in id2label.items():
        lookup[i] = CLASSES.index(mapping.get(name.strip(), "other"))
    return lookup


def road_roi(height, width):
    return slice(int(height * ROI_TOP), height), slice(int(width * ROI_LEFT), int(width * ROI_RIGHT))


def summarize(class_map):
    region = class_map[road_roi(*class_map.shape)]
    shares = np.bincount(region.ravel(), minlength=len(CLASSES)) / region.size
    other = CLASSES.index("other")
    ground = 1 - shares[other]
    if ground < MIN_GROUND:
        best, confidence = other, shares[other]
    else:
        best = int(np.where(np.arange(len(CLASSES)) == other, -1, shares).argmax())
        confidence = shares[best] / ground
    return {
        "label": CLASSES[best],
        "confidence": round(float(confidence), 3),
        **{c: round(float(s), 3) for c, s in zip(CLASSES, shares)},
    }


def overlay(image, class_map, summary):
    palette = np.array([COLORS[c] for c in CLASSES], dtype=np.uint8)
    blended = (0.55 * np.asarray(image) + 0.45 * palette[class_map]).astype(np.uint8)
    out = Image.fromarray(blended)
    draw = ImageDraw.Draw(out)
    rows, cols = road_roi(*class_map.shape)
    draw.rectangle([cols.start, rows.start, cols.stop - 1, rows.stop - 1], outline=(255, 255, 0), width=4)
    draw.text((cols.start + 8, rows.start + 8), f"{summary['label']} {summary['confidence']:.0%}",
              fill=(255, 255, 0), font_size=max(16, class_map.shape[0] // 20))
    return out


class Segmenter:
    def __init__(self, model_id=DEFAULT_MODEL):
        import torch
        from transformers import AutoImageProcessor, AutoModelForSemanticSegmentation

        torch.set_grad_enabled(False)
        self.processor = AutoImageProcessor.from_pretrained(model_id)
        self.model = AutoModelForSemanticSegmentation.from_pretrained(model_id).eval()
        self.lookup = build_lookup(self.model.config.id2label)

    def class_map(self, image):
        outputs = self.model(**self.processor(images=image, return_tensors="pt"))
        raw = self.processor.post_process_semantic_segmentation(outputs, target_sizes=[image.size[::-1]])[0]
        return self.lookup[raw.numpy()]


def run(frames_dir, out_dir, overlays=5, model_id=DEFAULT_MODEL, probe=None, segmenter=None):
    frames = sorted(Path(frames_dir).glob("*.jpg"))
    if not frames:
        raise ValueError(f"no .jpg frames in {frames_dir}")
    out_dir = Path(out_dir)
    (out_dir / "overlays").mkdir(parents=True, exist_ok=True)
    keep = set(np.linspace(0, len(frames) - 1, min(overlays, len(frames)), dtype=int).tolist()) if overlays else set()
    segmenter = segmenter or Segmenter(model_id)
    rows = []
    started = time.perf_counter()
    for i, path in enumerate(frames):
        image = Image.open(path).convert("RGB")
        class_map = segmenter.class_map(image)
        summary = summarize(class_map)
        if probe:
            summary = probe.check(summary, image)
        rows.append({"filename": path.name, **summary})
        if i in keep:
            overlay(image, class_map, summary).save(out_dir / "overlays" / path.name, quality=85)
    seconds_per_frame = (time.perf_counter() - started) / len(frames)
    csv_path = out_dir / "segmentation.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, restval="")
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, rows, seconds_per_frame


def main(argv=None):
    p = argparse.ArgumentParser(description="Label the road surface in each frame.")
    p.add_argument("frames", type=Path, help="folder of .jpg frames (output of pipeline.frames)")
    p.add_argument("--out", type=Path, required=True, help="output folder (gets segmentation.csv and overlays/)")
    p.add_argument("--overlays", type=int, default=5, help="number of overlay images to save, spread over the clip")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model id (ADE20K label set)")
    p.add_argument("--no-probe", action="store_true", help="skip the dirt probe; keep SegFormer's own paved calls")
    args = p.parse_args(argv)
    from pipeline.segmentation.probe import load_default

    try:
        csv_path, rows, spf = run(args.frames, args.out, args.overlays, args.model,
                                  None if args.no_probe else load_default())
    except ValueError as e:
        sys.exit(f"error: {e}")
    print(f"{len(rows)} frames -> {csv_path} ({spf:.1f} s/frame)")


if __name__ == "__main__":
    main()
