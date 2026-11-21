"""Dirt check: a logistic regression on CLIP image features of the road in front of the camera.

SegFormer's ADE20K labels call most Vietnamese dirt roads "road". For frames SegFormer calls paved,
the probe looks at the road crop and switches the label to dirt when it is sure enough. It never
switches dirt to paved (docs/evaluation/2026-11-21-phase2-dirt-probe.md).
"""
import json
from pathlib import Path

import numpy as np

CLIP_MODEL = "openai/clip-vit-base-patch16"
DEFAULT_PROBE = Path(__file__).with_name("surface_probe.json")
CROP = (0.15, 0.45, 0.85, 1.0)


def road_crop(image):
    w, h = image.size
    return image.crop((int(w * CROP[0]), int(h * CROP[1]), int(w * CROP[2]), int(h * CROP[3])))


class Embedder:
    def __init__(self, model_id=CLIP_MODEL):
        from transformers import CLIPModel, CLIPProcessor

        self.model = CLIPModel.from_pretrained(model_id).eval()
        self.processor = CLIPProcessor.from_pretrained(model_id)

    def __call__(self, images):
        import torch

        with torch.no_grad():
            out = self.model.get_image_features(**self.processor(images=[road_crop(i) for i in images], return_tensors="pt"))
        out = getattr(out, "pooler_output", out)
        return (out / out.norm(dim=-1, keepdim=True)).numpy()


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
    def __init__(self, mean, scale, coef, intercept, threshold=0.5, info=None, embedder=None):
        self.mean, self.scale, self.coef = (np.asarray(a, np.float64) for a in (mean, scale, coef))
        self.intercept, self.threshold, self.info = float(intercept), float(threshold), info or {}
        self.embedder = embedder

    def p_unpaved(self, X):
        return sigmoid(((np.atleast_2d(X) - self.mean) / self.scale) @ self.coef + self.intercept)

    def relabel(self, summary, features):
        """A paved frame becomes dirt when p_unpaved reaches the threshold; other labels stay."""
        if summary["label"] != "paved":
            return summary
        p = float(self.p_unpaved(features)[0])
        return {**summary, "label": "dirt" if p >= self.threshold else "paved", "p_unpaved": round(p, 3)}

    def check(self, summary, image):
        if summary["label"] != "paved":
            return summary
        if self.embedder is None:
            self.embedder = Embedder(self.info.get("clip_model", CLIP_MODEL))
        return self.relabel(summary, self.embedder([image])[0])

    def save(self, path):
        data = {"info": self.info, "threshold": self.threshold, "intercept": self.intercept,
                **{k: [float(f"{v:.6g}") for v in getattr(self, k)] for k in ("mean", "scale", "coef")}}
        Path(path).write_text(json.dumps(data, ensure_ascii=False) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path=DEFAULT_PROBE):
        d = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(d["mean"], d["scale"], d["coef"], d["intercept"], d["threshold"], d.get("info"))


def load_default(path=DEFAULT_PROBE):
    """The shipped probe, or None when there is no probe file."""
    return Probe.load(path) if Path(path).exists() else None
