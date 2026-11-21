"""Score the surface stage against hand labels on public KartaView photos, in one command.

Downloads only the labelled photos (into --out, never the repo), runs segmentation on them and prints the
confusion table, frame accuracy and per-way agreement used in docs/evaluation/.
"""
import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

from PIL import Image

from pipeline.fusion.fuse import SURFACES
from pipeline.segmentation.segment import DEFAULT_MODEL, summarize
from tools.kartaview import get, list_photos, photo_url, save_frame

EYE = ["paved", "unpaved"]
FAMILY = {"paved": "paved", "dirt": "unpaved", "mud": "unpaved"}
CSV_FIELDS = ["kartaview_sequence", "photo", "osm_way_id", "surface_by_eye", "filename", "label", "confidence", "p_unpaved"]


def load_labels(path):
    with open(path, encoding="utf-8") as f:
        return list(csv.DictReader(f))


def apply_prefer(labels, prefer):
    """Labels in `prefer` (e.g. an owner spot check) win for the same photo."""
    better = {(r["kartaview_sequence"], int(r["photo"])): r["surface_by_eye"] for r in prefer}
    return [{**r, "surface_by_eye": better.get((r["kartaview_sequence"], int(r["photo"])), r["surface_by_eye"])}
            for r in labels]


def frame_name(label):
    return f"{label['kartaview_sequence']}_{int(label['photo']):05d}.jpg"


def fetch_frames(labels, frames_dir, photos_of=list_photos, download=get):
    """Download the labelled photos; `photo` in the label file is KartaView's sequenceIndex."""
    frames_dir = Path(frames_dir)
    frames_dir.mkdir(parents=True, exist_ok=True)
    by_sequence = defaultdict(list)
    for label in labels:
        by_sequence[label["kartaview_sequence"]].append(label)
    missing = []
    for sequence, group in by_sequence.items():
        todo = [lab for lab in group if not (frames_dir / frame_name(lab)).exists()]
        if not todo:
            continue
        photos = {int(p["sequenceIndex"]): p for p in photos_of(sequence)}
        for lab in todo:
            photo = photos.get(int(lab["photo"]))
            if photo is None:
                missing.append(frame_name(lab))
                continue
            save_frame(download(photo_url(photo)), frames_dir / frame_name(lab))
    return missing


def voted(row, min_confidence):
    return row["label"] in SURFACES and float(row["confidence"]) >= min_confidence


def score(rows, min_confidence=0.5):
    clear = [r for r in rows if r["surface_by_eye"] in EYE]
    votes = [r for r in clear if voted(r, min_confidence)]
    confusion = {model: Counter(r["surface_by_eye"] for r in votes if r["label"] == model) for model in SURFACES}
    right = sum(FAMILY[r["label"]] == r["surface_by_eye"] for r in votes)
    ways = defaultdict(list)
    for r in clear:
        ways[r.get("osm_way_id") or r["kartaview_sequence"]].append(r)
    per_way = []
    for way_id, group in sorted(ways.items()):
        eye = Counter(r["surface_by_eye"] for r in group).most_common()
        model = Counter(FAMILY[r["label"]] for r in group if voted(r, min_confidence)).most_common()
        eye_majority = eye[0][0] if len(eye) == 1 or eye[0][1] > eye[1][1] else ""
        model_majority = model[0][0] if model and (len(model) == 1 or model[0][1] > model[1][1]) else ""
        per_way.append({"way_id": way_id, "eye": eye_majority, "model": model_majority,
                        "frames": len(group), "votes": sum(n for _, n in model)})
    decided = [w for w in per_way if w["eye"]]
    return {
        "labels": len(rows),
        "clear": len(clear),
        "voted": len(votes),
        "right": right,
        "unpaved_called_paved": confusion["paved"]["unpaved"],
        "paved_called_unpaved": sum(confusion[m]["paved"] for m in SURFACES if FAMILY[m] == "unpaved"),
        "confusion": {m: dict(c) for m, c in confusion.items()},
        "ways_with_eye_majority": len(decided),
        "ways_right": sum(w["eye"] == w["model"] for w in decided),
        "per_way": per_way,
    }


def report(result):
    lines = [
        f"{result['labels']} labels, {result['clear']} clear, {result['voted']} voted",
        f"frames right: {result['right']} of {result['voted']}",
        f"unpaved called paved: {result['unpaved_called_paved']}",
        f"paved called unpaved: {result['paved_called_unpaved']}",
        f"ways right (where the eye has a majority): {result['ways_right']} of {result['ways_with_eye_majority']}",
        "",
        "| model | by eye paved | by eye unpaved |",
        "|---|---|---|",
    ]
    lines += [f"| {m} | {c.get('paved', 0)} | {c.get('unpaved', 0)} |" for m, c in result["confusion"].items()]
    return "\n".join(lines)


def run(labels_csv, out_dir, model_id=DEFAULT_MODEL, min_confidence=0.5, segmenter=None, probe=None,
        split=None, prefer=()):
    from pipeline.segmentation.segment import Segmenter

    labels = load_labels(labels_csv)
    if split:
        labels = [r for r in labels if r.get("split") == split]
    for path in prefer:
        labels = apply_prefer(labels, load_labels(path))
    out_dir = Path(out_dir)
    missing = fetch_frames(labels, out_dir / "frames")
    if missing:
        print(f"warning: {len(missing)} labelled photos are no longer on KartaView: {missing[:5]}", file=sys.stderr)
    segmenter = segmenter or Segmenter(model_id)
    rows = []
    for label in labels:
        path = out_dir / "frames" / frame_name(label)
        if not path.exists():
            continue
        image = Image.open(path).convert("RGB")
        summary = summarize(segmenter.class_map(image))
        if probe:
            summary = probe.check(summary, image)
        rows.append({**label, "filename": path.name, "label": summary["label"], "confidence": summary["confidence"],
                     "p_unpaved": summary.get("p_unpaved", "")})
    with open(out_dir / "benchmark.csv", "w", newline="", encoding="utf-8") as f:
        extra = [k for k in (labels[0] if labels else {}) if k not in CSV_FIELDS]
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS + extra, restval="")
        writer.writeheader()
        writer.writerows(rows)
    result = score(rows, min_confidence)
    (out_dir / "benchmark.json").write_text(json.dumps({"model": model_id, **result}, indent=2), encoding="utf-8")
    return result


def main(argv=None):
    p = argparse.ArgumentParser(description="Score surface labels against hand labels on KartaView photos.")
    p.add_argument("labels", type=Path, help="label CSV: kartaview_sequence, photo (sequenceIndex), surface_by_eye, optional osm_way_id (else each ride counts as one way)")
    p.add_argument("--out", type=Path, required=True, help="output folder (gets frames/, benchmark.csv, benchmark.json)")
    p.add_argument("--model", default=DEFAULT_MODEL, help="Hugging Face model id (ADE20K label set)")
    p.add_argument("--min-confidence", type=float, default=0.5, help="frames below this confidence do not vote")
    p.add_argument("--no-probe", action="store_true", help="score SegFormer alone, without the dirt probe")
    p.add_argument("--split", help="score only rows whose split column has this value, e.g. test")
    p.add_argument("--prefer", type=Path, action="append", default=[],
                   help="label CSV whose labels win for the same photo, e.g. an owner spot check (repeatable)")
    args = p.parse_args(argv)
    from pipeline.segmentation.probe import load_default

    try:
        result = run(args.labels, args.out, args.model, args.min_confidence,
                     probe=None if args.no_probe else load_default(), split=args.split, prefer=args.prefer)
    except (ValueError, OSError) as e:
        sys.exit(f"error: {e}")
    print(report(result))


if __name__ == "__main__":
    main()
