"""Dirt check: a logistic regression on CLIP image features of the road in front of the camera.

SegFormer's ADE20K labels call most Vietnamese dirt roads "road". For frames SegFormer calls paved,
the probe looks at the road crop and switches the label to dirt when it is sure enough. It never
switches dirt to paved (docs/evaluation/2026-11-21-phase2-dirt-probe.md).

Grassy dirt tracks come out "vegetation" or "other" instead, so they never vote. Those frames get the
same check with their own, stricter threshold (`grass_threshold`; 1.0 turns it off).

Narrow delta concrete lanes framed by greenery also come out "vegetation" (or a low-confidence label),
though SegFormer still marks some road pixels. The road check (`road_check`) crops the box around
those pixels and asks CLIP, zero-shot, whether it shows a paved or an unpaved road. The frame gets a
label only when CLIP and the road pixels agree (docs/evaluation/2026-11-22-delta-road-crop.md).
"""
import json
from pathlib import Path

import numpy as np

CLIP_MODEL = "openai/clip-vit-base-patch16"
DEFAULT_PROBE = Path(__file__).with_name("surface_probe.json")
CROP = (0.15, 0.45, 0.85, 1.0)
GRASS_LABELS = ("vegetation", "other")
PAVED_PROMPTS = ("a photo of a concrete road", "a photo of an asphalt road", "a photo of a paved road")
UNPAVED_PROMPTS = ("a photo of a dirt road", "a photo of a gravel road", "a photo of a muddy track")
ROAD_TOP = 0.45
MIN_ROAD_SHARE = 0.02
MIN_CONFIDENCE = 0.5


def road_crop(image):
    w, h = image.size
    return image.crop((int(w * CROP[0]), int(h * CROP[1]), int(w * CROP[2]), int(h * CROP[3])))


def road_box(class_map, top=ROAD_TOP, min_share=MIN_ROAD_SHARE):
    """Box around the paved and dirt pixels below `top`, and the class with more of them.

    None when they cover less than `min_share` of that part of the frame.
    """
    from pipeline.segmentation.segment import CLASSES

    paved, dirt = CLASSES.index("paved"), CLASSES.index("dirt")
    y_top = int(class_map.shape[0] * top)
    lower = class_map[y_top:]
    road = (lower == paved) | (lower == dirt)
    if road.mean() < min_share:
        return None
    ys, xs = np.nonzero(road)
    box = (int(xs.min()), y_top + int(ys.min()), int(xs.max()) + 1, y_top + int(ys.max()) + 1)
    return box, "paved" if (lower == paved).sum() >= (lower == dirt).sum() else "dirt"


class Embedder:
    def __init__(self, model_id=CLIP_MODEL):
        from transformers import CLIPModel, CLIPProcessor

        self.model = CLIPModel.from_pretrained(model_id).eval()
        self.processor = CLIPProcessor.from_pretrained(model_id)

    def __call__(self, images):
        return self.embed([road_crop(i) for i in images])

    def embed(self, images):
        import torch

        with torch.no_grad():
            out = self.model.get_image_features(**self.processor(images=images, return_tensors="pt"))
        out = getattr(out, "pooler_output", out)
        return (out / out.norm(dim=-1, keepdim=True)).numpy()

    def text(self, prompts):
        import torch

        with torch.no_grad():
            out = self.model.get_text_features(**self.processor(text=list(prompts), return_tensors="pt", padding=True))
        out = getattr(out, "pooler_output", out)
        return (out / out.norm(dim=-1, keepdim=True)).numpy()

    def p_unpaved(self, image):
        """Zero-shot P(unpaved road) for an image, from CLIP's paved and unpaved road prompts."""
        if not hasattr(self, "_prompts"):
            self._prompts = self.text(PAVED_PROMPTS + UNPAVED_PROMPTS)
        z = float(self.model.logit_scale.exp()) * (self._prompts @ self.embed([image])[0])
        e = np.exp(z - z.max())
        return float(e[len(PAVED_PROMPTS):].sum() / e.sum())


def sigmoid(z):
    return 1 / (1 + np.exp(-np.clip(z, -30, 30)))


def fit(X, y, c=1.0, steps=50):
    """L2 logistic regression (sklearn's C convention), standardised features, Newton steps."""
    X, y = np.asarray(X, np.float64), np.asarray(y, np.float64)
    mean, scale = X.mean(axis=0), X.std(axis=0) + 1e-6
    Z = np.hstack([(X - mean) / scale, np.ones((len(X), 1))])
    reg = np.eye(Z.shape[1]) / c
    reg[-1, -1] = 0
    w = np.zeros(Z.shape[1])
    for _ in range(steps):
        p = sigmoid(Z @ w)
        step = np.linalg.solve((Z * (p * (1 - p))[:, None]).T @ Z + reg, Z.T @ (p - y) + reg @ w)
        w -= step
        if np.abs(step).max() < 1e-6:
            break
    return Probe(mean, scale, w[:-1], w[-1])


class Probe:
    def __init__(self, mean, scale, coef, intercept, threshold=0.5, info=None, embedder=None, grass_threshold=1.0,
                 road_check=False):
        self.mean, self.scale, self.coef = (np.asarray(a, np.float64) for a in (mean, scale, coef))
        self.intercept, self.threshold, self.info = float(intercept), float(threshold), info or {}
        self.grass_threshold = float(grass_threshold)
        self.road_check = bool(road_check)
        self.embedder = embedder

    def checks(self, label):
        return label == "paved" or (label in GRASS_LABELS and self.grass_threshold < 1)

    def p_unpaved(self, X):
        return sigmoid(((np.atleast_2d(X) - self.mean) / self.scale) @ self.coef + self.intercept)

    def relabel(self, summary, features):
        """A paved frame becomes dirt at `threshold`, a vegetation or other frame at `grass_threshold`.

        A grass frame switched to dirt gets p_unpaved as its confidence, since its pixel share describes the grass.
        """
        label = summary["label"]
        if not self.checks(label):
            return summary
        p = float(self.p_unpaved(features)[0])
        if label == "paved":
            return {**summary, "label": "dirt" if p >= self.threshold else "paved", "p_unpaved": round(p, 3)}
        if p >= self.grass_threshold:
            return {**summary, "label": "dirt", "confidence": round(p, 3), "p_unpaved": round(p, 3)}
        return {**summary, "p_unpaved": round(p, 3)}

    def road_checks(self, summary):
        return self.road_check and (summary["label"] in GRASS_LABELS or float(summary["confidence"]) < MIN_CONFIDENCE)

    def check_road(self, summary, pixel_label, p):
        """Label a frame from its road box when CLIP (P(unpaved) = p) agrees with the road pixels."""
        clip_label = "dirt" if p >= 0.5 else "paved"
        if clip_label != pixel_label:
            return summary
        return {**summary, "label": clip_label, "confidence": round(max(p, 1 - p), 3), "p_unpaved": round(p, 3)}

    def get_embedder(self):
        if self.embedder is None:
            self.embedder = Embedder(self.info.get("clip_model", CLIP_MODEL))
        return self.embedder

    def check(self, summary, image, class_map=None):
        if class_map is not None and self.road_checks(summary):
            found = road_box(class_map)
            if found:
                box, pixel_label = found
                return self.check_road(summary, pixel_label, self.get_embedder().p_unpaved(image.crop(box)))
            return summary
        if not self.checks(summary["label"]):
            return summary
        return self.relabel(summary, self.get_embedder()([image])[0])

    def save(self, path):
        data = {"info": self.info, "threshold": self.threshold, "grass_threshold": self.grass_threshold,
                "road_check": self.road_check,                 "intercept": self.intercept,
                **{k: [float(f"{v:.6g}") for v in getattr(self, k)] for k in ("mean", "scale", "coef")}}
        Path(path).write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path=DEFAULT_PROBE):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["mean"], d["scale"], d["coef"], d["intercept"], d["threshold"], d.get("info"),
                   grass_threshold=d.get("grass_threshold", 1.0), road_check=d.get("road_check", False))


def load_default(path=DEFAULT_PROBE):
    """The shipped probe, or None when there is no probe file."""
    return Probe.load(path) if Path(path).exists() else None
