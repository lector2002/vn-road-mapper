import json

import numpy as np
from PIL import Image

from pipeline.segmentation import probe
from tools import probe as probe_tool


def test_fit_separates_and_round_trips(tmp_path):
    rng = np.random.default_rng(0)
    X = np.vstack([rng.normal(0, 1, (40, 5)), rng.normal(2, 1, (40, 5))])
    y = np.r_[np.zeros(40), np.ones(40)]
    p = probe.fit(X, y, c=1.0)
    assert ((p.p_unpaved(X) >= 0.5) == y).mean() > 0.9
    p.threshold = 0.7
    p.save(tmp_path / "p.json")
    q = probe.Probe.load(tmp_path / "p.json")
    assert q.threshold == 0.7
    assert np.allclose(q.p_unpaved(X), p.p_unpaved(X), atol=1e-4)


def test_relabel_only_switches_paved_to_dirt():
    p = probe.Probe(mean=[0], scale=[1], coef=[10], intercept=0)
    assert p.relabel({"label": "paved"}, [1]) == {"label": "dirt", "p_unpaved": 1.0}
    assert p.relabel({"label": "paved"}, [-1])["label"] == "paved"
    assert p.relabel({"label": "dirt"}, [-1]) == {"label": "dirt"}
    assert p.relabel({"label": "water"}, [1]) == {"label": "water"}


def test_check_embeds_only_paved_frames():
    seen = []
    p = probe.Probe(mean=[0], scale=[1], coef=[10], intercept=0, embedder=lambda ims: seen.extend(ims) or np.ones((1, 1)))
    image = Image.new("RGB", (10, 10))
    assert p.check({"label": "dirt"}, image) == {"label": "dirt"}
    assert seen == []
    assert p.check({"label": "paved"}, image)["label"] == "dirt"
    assert seen == [image]


def test_road_crop_keeps_the_bottom_middle():
    assert probe.road_crop(Image.new("RGB", (100, 200))).size == (70, 110)


def test_load_default_is_none_without_a_file(tmp_path):
    assert probe.load_default(tmp_path / "missing.json") is None


def test_shipped_probe_loads():
    p = probe.load_default()
    assert p is not None and len(p.coef) == len(p.mean) == 512 and 0 < p.threshold < 1


def test_pick_threshold_switches_nothing_when_no_threshold_is_safe():
    rows = [{"calibrate": True, "surface_by_eye": "paved", "label": "paved"}] * 2
    assert probe_tool.pick_threshold(rows, np.array([0.99, 0.99]), 0.03) == 1.0


def write_cache(path, names, labels, feats):
    np.savez(path, names=names, labels=labels, conf=np.full(len(names), 0.9), feats=np.array(feats, float))


def test_train_prefers_checked_labels_and_scores_the_test_split(tmp_path, capsys):
    labels = tmp_path / "labels.csv"
    rows, names, feats = ["kartaview_sequence,photo,split,surface_by_eye"], [], []
    for ride in range(4):
        for i in range(10):
            unpaved = i < 4
            rows.append(f"{ride},{i},{'test' if ride == 3 else 'dev'},{'unpaved' if unpaved else 'paved'}")
            names.append(f"{ride}_{i:05d}.jpg")
            feats.append([1.0 + 0.1 * i if unpaved else -1.0 - 0.1 * i, 0.0])
    labels.write_text("\n".join(rows) + "\n")
    prefer = tmp_path / "prefer.csv"
    prefer.write_text("kartaview_sequence,photo,surface_by_eye\n0,0,paved\n")
    cache = tmp_path / "c.npz"
    write_cache(cache, names, ["paved"] * len(names), feats)

    result = probe_tool.frames(labels, probe_tool.load_cache(cache), "dev", probe_tool.read_labels(prefer), calibrate=False)
    assert [r["surface_by_eye"] for r in result if r["photo"] == "0" and r["kartaview_sequence"] == "0"] == ["paved"]
    assert sum(r["calibrate"] for r in result) == 1

    out = tmp_path / "probe.json"
    probe_tool.main(["train", "--train", str(labels), str(cache), "dev", "--test", str(labels), str(cache), "test",
                     "--check", str(cache), "--out", str(out)])
    text = capsys.readouterr().out
    assert "unpaved called paved: 4" in text and "unpaved called paved: 0" in text
    assert json.loads(out.read_text())["info"]["frames"] == 30
