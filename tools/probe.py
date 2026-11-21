"""Build features for, train and score the dirt probe (pipeline/segmentation/probe.py).

  python -m tools.probe features output/vn/frames --out output/probe/vn.npz
  python -m tools.probe train --train LABELS CACHE SPLIT [--extra LABELS CACHE SPLIT] [--prefer LABELS]
                              --test LABELS CACHE SPLIT [--check CACHE] [--out probe.json]

`features` runs SegFormer and CLIP once per frame. `train` fits on --train and --extra rows that
SegFormer calls paved or dirt. Each ride is held out in turn; the threshold is the lowest one at
which at most --max-paved-error of held-out paved frames in --train (and --prefer) rows flip to dirt.
--extra rows only train: use it for labels that failed a spot check.
"""
import argparse
import csv
import glob
from pathlib import Path

import numpy as np

from pipeline.segmentation.probe import CLIP_MODEL, fit
from tools.benchmark import frame_name, report, score

UNPAVED = {"unpaved", "mud"}
THRESHOLDS = np.r_[np.arange(0.01, 0.1, 0.005), np.arange(0.1, 0.951, 0.025)]


def features(frames_dir, out, segmenter=None, embedder=None, batch=16):
    from PIL import Image

    from pipeline.segmentation.probe import Embedder
    from pipeline.segmentation.segment import Segmenter, summarize

    segmenter, embedder = segmenter or Segmenter(), embedder or Embedder()
    files = sorted(glob.glob(f"{frames_dir}/*.jpg"))
    labels, conf, feats = [], [], []
    for i in range(0, len(files), batch):
        images = [Image.open(f).convert("RGB") for f in files[i:i + batch]]
        for image in images:
            s = summarize(segmenter.class_map(image))
            labels.append(s["label"])
            conf.append(s["confidence"])
        feats.append(embedder(images))
    np.savez(out, names=[Path(f).name for f in files], labels=labels, conf=np.array(conf, float),
             feats=np.vstack(feats) if feats else np.zeros((0, 0)))
    return len(files)


def load_cache(path):
    d = np.load(path)
    return {str(n): (f, str(lab), float(c)) for n, f, lab, c in zip(d["names"], d["feats"], d["labels"], d["conf"])}


def read_labels(path):
    with open(path, encoding="utf-8") as f:
        return {frame_name(r): r["surface_by_eye"] for r in csv.DictReader(f)}


def frames(labels_csv, cache, split="all", prefer=None, calibrate=True):
    """Labelled rows with SegFormer's call and the CLIP features; labels in `prefer` win for the same photo."""
    prefer = prefer or {}
    rows = []
    with open(labels_csv, encoding="utf-8") as f:
        for label in csv.DictReader(f):
            name = frame_name(label)
            if name not in cache or split not in ("all", label.get("split")):
                continue
            feats, model, conf = cache[name]
            rows.append({**label, "osm_way_id": label.get("osm_way_id") or label["kartaview_sequence"],
                         "surface_by_eye": prefer.get(name, label["surface_by_eye"]),
                         "label": model, "confidence": conf, "feats": feats,
                         "calibrate": calibrate or name in prefer})
    return rows


def trainable(rows):
    return [r for r in rows if r["surface_by_eye"] in UNPAVED | {"paved"} and r["label"] in ("paved", "dirt")]


def target(rows):
    return np.array([r["surface_by_eye"] in UNPAVED for r in rows], float)


def held_out_p(rows, c):
    """p_unpaved for every row from a probe that never saw its ride."""
    p = np.zeros(len(rows))
    for ride in sorted({r["kartaview_sequence"] for r in rows}):
        test = [i for i, r in enumerate(rows) if r["kartaview_sequence"] == ride]
        train = [r for r in rows if r["kartaview_sequence"] != ride]
        p[test] = fit([r["feats"] for r in train], target(train), c).p_unpaved([rows[i]["feats"] for i in test])
    return p


def pick_threshold(rows, p, max_paved_error):
    """Lowest threshold at which at most max_paved_error of calibration frames SegFormer calls paved flip."""
    paved = np.array([r["calibrate"] and r["surface_by_eye"] == "paved" and r["label"] == "paved" for r in rows])
    for t in THRESHOLDS:
        if not paved.any() or (p[paved] >= t).mean() <= max_paved_error:
            return round(float(t), 3)
    return float(THRESHOLDS[-1])


def relabel(probe, rows):
    return [probe.relabel(r, r["feats"]) for r in rows]


def train_main(args):
    prefer = {}
    for path in args.prefer:
        prefer.update(read_labels(path))
    train = []
    for specs, calibrate in ((args.train, True), (args.extra, False)):
        for labels_csv, cache, split in specs:
            train += trainable(frames(labels_csv, load_cache(cache), split, prefer, calibrate))
    y = target(train)
    threshold = pick_threshold(train, held_out_p(train, args.c), args.max_paved_error)
    probe = fit([r["feats"] for r in train], y, args.c)
    probe.threshold = threshold
    probe.info = {"clip_model": CLIP_MODEL, "rides": sorted({r["kartaview_sequence"] for r in train}),
                  "frames": len(train), "unpaved": int(y.sum()), "c": args.c, "max_paved_error": args.max_paved_error}
    print(f"trained on {len(train)} frames ({int(y.sum())} unpaved) from {len(probe.info['rides'])} rides, threshold {threshold}")
    test = frames(args.test[0], load_cache(args.test[1]), args.test[2])
    print("\nSegFormer:\n" + report(score(test)) + "\n\nWith the dirt probe:\n" + report(score(relabel(probe, test))))
    for cache in args.check:
        rows = [{"label": lab, "feats": f} for f, lab, _ in load_cache(cache).values()]
        flipped = sum(r["label"] == "paved" and s["label"] == "dirt" for r, s in zip(rows, relabel(probe, rows)))
        print(f"\n{cache}: {len(rows)} frames, {sum(r['label'] == 'paved' for r in rows)} paved, {flipped} switched to dirt")
    if args.out:
        probe.save(args.out)
    return probe


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("features", help="SegFormer label and CLIP features for every frame in a folder")
    f.add_argument("frames", type=Path)
    f.add_argument("--out", type=Path, required=True)
    t = sub.add_parser("train", help="fit the probe, pick its threshold, score it on a test split")
    spec = dict(nargs=3, action="append", default=[], metavar=("LABELS_CSV", "CACHE", "SPLIT"))
    t.add_argument("--train", **spec, help="labelled frames to train and calibrate on; SPLIT 'all' keeps every row")
    t.add_argument("--extra", **spec, help="labelled frames to train on only")
    t.add_argument("--prefer", action="append", default=[], metavar="LABELS_CSV",
                   help="checked labels that replace training labels for the same photo")
    t.add_argument("--test", nargs=3, required=True, metavar=("LABELS_CSV", "CACHE", "SPLIT"))
    t.add_argument("--check", nargs="*", default=[], metavar="CACHE", help="unlabelled paved rides: count frames switched to dirt")
    t.add_argument("--c", type=float, default=1.0, help="inverse L2 weight")
    t.add_argument("--max-paved-error", type=float, default=0.03)
    t.add_argument("--out", type=Path, help="write the probe JSON here")
    args = p.parse_args(argv)
    if args.cmd == "features":
        print(f"{features(args.frames, args.out)} frames -> {args.out}")
    else:
        if not args.train:
            p.error("train needs at least one --train")
        train_main(args)


if __name__ == "__main__":
    main()
