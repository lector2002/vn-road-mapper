import json
import os

import numpy as np
import pytest
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
    assert p.relabel({"label": "vegetation"}, [1]) == {"label": "vegetation"}


def test_relabel_switches_grass_to_dirt_at_the_grass_threshold():
    p = probe.Probe(mean=[0], scale=[1], coef=[10], intercept=0, grass_threshold=0.9)
    assert p.relabel({"label": "vegetation", "confidence": 0.8}, [1]) == {"label": "dirt", "confidence": 1.0, "p_unpaved": 1.0}
    assert p.relabel({"label": "other"}, [1])["label"] == "dirt"
    assert p.relabel({"label": "vegetation", "confidence": 0.8}, [0.1]) == {"label": "vegetation", "confidence": 0.8, "p_unpaved": 0.731}
    assert p.relabel({"label": "paved"}, [0.1])["label"] == "dirt"
    assert p.relabel({"label": "water"}, [1]) == {"label": "water"}


def test_check_embeds_only_paved_frames():
    seen = []
    p = probe.Probe(mean=[0], scale=[1], coef=[10], intercept=0, embedder=lambda ims: seen.extend(ims) or np.ones((1, 1)))
    image = Image.new("RGB", (10, 10))
    assert p.check({"label": "dirt"}, image) == {"label": "dirt"}
    assert seen == []
    assert p.check({"label": "paved"}, image)["label"] == "dirt"
    assert seen == [image]
    assert p.check({"label": "vegetation"}, image) == {"label": "vegetation"}
    assert seen == [image]
    p.grass_threshold = 0.9
    assert p.check({"label": "vegetation"}, image)["label"] == "dirt"
    assert seen == [image, image]


def test_grass_threshold_round_trips_and_defaults_to_off(tmp_path):
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, grass_threshold=0.8)
    p.save(tmp_path / "p.json")
    assert probe.Probe.load(tmp_path / "p.json").grass_threshold == 0.8
    d = json.loads((tmp_path / "p.json").read_text())
    del d["grass_threshold"]
    (tmp_path / "p.json").write_text(json.dumps(d))
    assert probe.Probe.load(tmp_path / "p.json").grass_threshold == 1.0


def test_road_crop_keeps_the_bottom_middle():
    assert probe.road_crop(Image.new("RGB", (100, 200))).size == (70, 110)


def test_load_default_is_none_without_a_file(tmp_path):
    assert probe.load_default(tmp_path / "missing.json") is None


def test_shipped_probe_loads():
    p = probe.load_default()
    assert p is not None and len(p.coef) == len(p.mean) == 512 and 0 < p.threshold < 1
    assert p.grass_threshold == 1.0 and p.road_check


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
    prefer.write_text("kartaview_sequence,photo,surface_by_eye\n0,0,paved\n0,1,mud\n")
    cache = tmp_path / "c.npz"
    write_cache(cache, names, ["paved"] * len(names), feats)

    result = probe_tool.frames(labels, probe_tool.load_cache(cache), "dev", probe_tool.read_labels(prefer), calibrate=False)
    assert [r["surface_by_eye"] for r in result if r["photo"] == "0" and r["kartaview_sequence"] == "0"] == ["paved"]
    assert [r["surface_by_eye"] for r in result if r["photo"] == "1" and r["kartaview_sequence"] == "0"] == ["unpaved"]
    assert sum(r["calibrate"] for r in result) == 2

    out = tmp_path / "probe.json"
    probe_tool.main(["train", "--train", str(labels), str(cache), "dev", "--test", str(labels), str(cache), "test",
                     "--check", str(cache), "--out", str(out)])
    text = capsys.readouterr().out
    assert "unpaved called paved: 4" in text and "unpaved called paved: 0" in text
    assert json.loads(out.read_text())["info"]["frames"] == 30
    assert json.loads(out.read_text())["grass_threshold"] == 1.0


def test_train_picks_a_grass_threshold_from_vegetation_frames(tmp_path, capsys):
    labels = tmp_path / "labels.csv"
    rows, names, feats, segformer = ["kartaview_sequence,photo,split,surface_by_eye"], [], [], []
    for ride in range(4):
        for i in range(10):
            unpaved = i < 4
            rows.append(f"{ride},{i},{'test' if ride == 3 else 'dev'},{'unpaved' if unpaved else 'paved'}")
            names.append(f"{ride}_{i:05d}.jpg")
            feats.append([1.0 + 0.1 * i if unpaved else -1.0 - 0.1 * i, 0.0])
            segformer.append("vegetation" if i in (0, 9) else "paved")
    labels.write_text("\n".join(rows) + "\n")
    cache = tmp_path / "c.npz"
    write_cache(cache, names, segformer, feats)
    args = ["train", "--train", str(labels), str(cache), "dev", "--test", str(labels), str(cache), "test",
            "--check", str(cache), "--out", str(tmp_path / "p.json")]

    probe_tool.main(args)
    p = probe.Probe.load(tmp_path / "p.json")
    assert p.grass_threshold < 1 and p.info["grass_frames"] == 6 and p.info["grass_unpaved"] == 3
    assert "8 vegetation or other, 4 switched to dirt" in capsys.readouterr().out
    probe_tool.main(args + ["--no-grass"])
    assert probe.Probe.load(tmp_path / "p.json").grass_threshold == 1.0


class FakeRoadEmbedder:
    def __init__(self, p):
        self.p, self.crops = p, []

    def p_unpaved(self, image):
        self.crops.append(image.size)
        return self.p

    def __call__(self, images):
        return np.ones((len(images), 1))


def lane_map(pixel_class="paved", width=40, height=100):
    from pipeline.segmentation.segment import CLASSES

    class_map = np.full((height, width), CLASSES.index("vegetation"))
    class_map[60:100, 15:25] = CLASSES.index(pixel_class)
    class_map[10:20, 0:40] = CLASSES.index("paved")
    return class_map


def test_road_box_covers_road_pixels_below_the_top_only():
    assert probe.road_box(lane_map()) == ((15, 60, 25, 100), "paved")
    assert probe.road_box(lane_map("dirt"))[1] == "dirt"
    assert probe.road_box(lane_map(), min_share=0.2) is None


def test_road_check_labels_a_vegetation_frame_when_clip_and_pixels_agree():
    embedder = FakeRoadEmbedder(0.1)
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    image = Image.new("RGB", (40, 100))
    assert p.check({"label": "vegetation", "confidence": 0.9}, image, lane_map()) == {
        "label": "paved", "confidence": 0.9, "p_unpaved": 0.1
    }
    assert embedder.crops == [(10, 40)]
    embedder.p = 0.8
    assert p.check({"label": "vegetation", "confidence": 0.9}, image, lane_map()) == {"label": "vegetation", "confidence": 0.9}
    assert p.check({"label": "other", "confidence": 0.0}, image, lane_map("dirt"))["label"] == "dirt"


def test_road_check_runs_only_on_frames_that_do_not_vote():
    embedder = FakeRoadEmbedder(0.9)
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    image = Image.new("RGB", (40, 100))
    assert p.check({"label": "dirt", "confidence": 0.8}, image, lane_map("dirt")) == {"label": "dirt", "confidence": 0.8}
    assert p.check({"label": "paved", "confidence": 0.4}, image, lane_map("dirt"))["label"] == "dirt"
    assert len(embedder.crops) == 1
    p.road_check = False
    assert p.check({"label": "vegetation", "confidence": 0.9}, image, lane_map("dirt"))["label"] == "vegetation"
    assert p.check({"label": "vegetation", "confidence": 0.9}, image)["label"] == "vegetation"
    assert len(embedder.crops) == 1


def test_road_check_round_trips_and_defaults_to_off(tmp_path):
    probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, road_check=True).save(tmp_path / "p.json")
    assert probe.Probe.load(tmp_path / "p.json").road_check
    d = json.loads((tmp_path / "p.json").read_text())
    del d["road_check"]
    (tmp_path / "p.json").write_text(json.dumps(d))
    assert not probe.Probe.load(tmp_path / "p.json").road_check


@pytest.mark.skipif(os.environ.get("RUN_MODEL_TESTS") != "1", reason="downloads CLIP; set RUN_MODEL_TESTS=1")
def test_real_clip_gives_a_zero_shot_unpaved_probability():
    p = probe.Embedder().p_unpaved(Image.new("RGB", (64, 64), (128, 120, 110)))
    assert 0 <= p <= 1


def test_frames_the_road_check_leaves_alone_still_get_the_dirt_probe():
    embedder = FakeRoadEmbedder(0.8)
    p = probe.Probe(mean=[0], scale=[1], coef=[10], intercept=0, embedder=embedder, road_check=True, grass_threshold=0.9)
    image = Image.new("RGB", (40, 100))
    assert p.check({"label": "vegetation", "confidence": 0.9}, image, lane_map())["label"] == "dirt"
    assert p.check({"label": "paved", "confidence": 0.4}, image, lane_map())["label"] == "dirt"
    assert len(embedder.crops) == 2


def occluded_lane_map(width=40, height=100):
    from pipeline.segmentation.segment import CLASSES

    class_map = lane_map(width=width, height=height)
    class_map[85:100, 14:26] = CLASSES.index("other")
    return class_map


class FakeOcclusionEmbedder:
    def __init__(self, ps):
        self.ps, self.calls = list(ps), []

    def p_unpaved(self, image, *args, **kwargs):
        return self.p_unpaved_many([image], *args, **kwargs)[0]

    def p_unpaved_many(self, images, *args, **kwargs):
        self.calls += [image.size for image in images]
        return [self.ps.pop(0) for _ in images]

    def __call__(self, images):
        return np.ones((len(images), 1))


def test_occluded_road_read_labels_when_both_crops_agree():
    embedder = FakeOcclusionEmbedder([0.1, 0.15])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    out = p.check({"label": "vegetation", "confidence": 0.9}, Image.new("RGB", (40, 100)), occluded_lane_map())
    assert out["label"] == "paved" and out["confidence"] == 0.85 and out["p_unpaved"] == 0.125
    assert embedder.calls == [(23, 31), (28, 55)]


def test_occluded_road_read_preserves_a_direct_surface_vote():
    embedder = FakeOcclusionEmbedder([0.1, 0.9])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    out = p.check({"label": "dirt", "confidence": 0.9}, Image.new("RGB", (40, 100)), occluded_lane_map())
    assert out == {"label": "dirt", "confidence": 0.9}


def test_occluded_road_read_keeps_vegetation_as_nonwater_evidence_when_crops_disagree():
    embedder = FakeOcclusionEmbedder([0.1, 0.9])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    out = p.check({"label": "vegetation", "confidence": 0.9}, Image.new("RGB", (40, 100)), occluded_lane_map())
    assert out["label"] == "vegetation" and out["confidence"] == 0.9 and out["p_unpaved"] == 0.5


def test_occluded_road_read_forces_a_nonvote_after_an_unclear_probe_arbitration():
    embedder = FakeOcclusionEmbedder([0.1, 0.9])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    out = p.check({"label": "paved", "confidence": 0.9}, Image.new("RGB", (40, 100)), occluded_lane_map())
    assert out["label"] == "paved" and out["confidence"] == 0.0


def test_occluded_road_read_overrides_a_marginal_dirt_probe_flip():
    embedder = FakeOcclusionEmbedder([0.1, 0.15])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    out = p.check({"label": "paved", "confidence": 0.9}, Image.new("RGB", (40, 100)), occluded_lane_map())
    assert out["label"] == "paved" and out["confidence"] == 0.85


def test_occluded_road_read_preserves_a_strong_dirt_probe_flip():
    embedder = FakeOcclusionEmbedder([0.1, 0.15])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=1, embedder=embedder, road_check=True)
    out = p.check({"label": "paved", "confidence": 0.9}, Image.new("RGB", (40, 100)), occluded_lane_map())
    assert out["label"] == "dirt" and out["confidence"] == 0.9
    assert embedder.calls == []


def test_occluded_read_does_not_apply_without_bottom_centre_occlusion():
    embedder = FakeOcclusionEmbedder([0.1, 0.1, 0.1, 0.1])
    p = probe.Probe(mean=[0], scale=[1], coef=[1], intercept=0, embedder=embedder, road_check=True)
    out = p.check({"label": "water", "confidence": 0.8}, Image.new("RGB", (40, 100)), lane_map())
    assert out == {"label": "water", "confidence": 0.8}
    assert embedder.calls == []

