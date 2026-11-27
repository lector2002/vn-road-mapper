import io
import json

import numpy as np
from PIL import Image

from pipeline.segmentation.segment import CLASSES
from tools import benchmark


def label(seq, photo, way, eye):
    return {"kartaview_sequence": seq, "photo": photo, "osm_way_id": way, "surface_by_eye": eye}


def row(way, eye, model, confidence=0.9):
    return {**label("1", "0", way, eye), "label": model, "confidence": str(confidence)}


def test_score_counts_votes_errors_and_ways():
    rows = [row("a", "paved", "paved"), row("a", "paved", "paved"), row("a", "unpaved", "paved"),
            row("b", "unpaved", "dirt"), row("b", "unpaved", "paved"), row("b", "unpaved", "dirt"),
            row("b", "paved", "dirt"),
            row("c", "unclear", "paved"),
            row("d", "unpaved", "dirt", confidence=0.3), row("d", "paved", "vegetation")]
    result = benchmark.score(rows)
    assert (result["labels"], result["clear"], result["voted"]) == (10, 9, 7)
    assert result["right"] == 4
    assert result["unpaved_called_paved"] == 2
    assert result["paved_called_unpaved"] == 1
    assert result["confusion"]["paved"] == {"paved": 2, "unpaved": 2}
    # a: eye paved, model paved; b: eye unpaved, model unpaved; d: eye tie, left out.
    assert (result["ways_right"], result["ways_with_eye_majority"]) == (2, 2)


def test_zero_confidence_never_votes_even_at_a_zero_cutoff():
    rows = [row("a", "paved", "paved", confidence=0.0)]
    result = benchmark.score(rows, min_confidence=0)
    assert result["voted"] == 0 and result["right"] == 0


def test_way_with_a_model_tie_counts_as_wrong():
    rows = [row("a", "unpaved", "paved"), row("a", "unpaved", "dirt")]
    assert benchmark.score(rows)["ways_right"] == 0


def jpeg():
    buf = io.BytesIO()
    Image.new("RGB", (40, 30), "grey").save(buf, format="JPEG")
    return buf.getvalue()


def test_fetch_frames_downloads_only_labelled_photos_by_sequence_index(tmp_path):
    photos = [{"sequenceIndex": str(i), "imageLthUrl": f"https://cdn.test/{i}.jpg"} for i in range(5)]
    downloaded = []

    def download(url):
        downloaded.append(url)
        return jpeg()

    labels = [label("7", "03", "w", "paved"), label("7", "9", "w", "paved")]
    missing = benchmark.fetch_frames(labels, tmp_path, photos_of=lambda seq: photos, download=download)
    assert downloaded == ["https://cdn.test/3.jpg"]
    assert missing == ["7_00009.jpg"]
    assert (tmp_path / "7_00003.jpg").exists()
    assert benchmark.fetch_frames(labels[:1], tmp_path, photos_of=lambda seq: 1 / 0, download=download) == []


class FakeSegmenter:
    def class_map(self, image):
        class_map = np.full((image.height, image.width), CLASSES.index("dirt"))
        return class_map


def test_run_writes_csv_json_and_scores(tmp_path, monkeypatch):
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text("kartaview_sequence,photo,osm_way_id,surface_by_eye\n7,1,w,unpaved\n7,2,w,paved\n")
    monkeypatch.setattr(benchmark, "fetch_frames", lambda labels, frames_dir: [])
    (tmp_path / "out" / "frames").mkdir(parents=True)
    for name in ["7_00001.jpg", "7_00002.jpg"]:
        (tmp_path / "out" / "frames" / name).write_bytes(jpeg())

    result = benchmark.run(labels_csv, tmp_path / "out", segmenter=FakeSegmenter())

    assert (result["voted"], result["right"], result["paved_called_unpaved"]) == (2, 1, 1)
    saved = json.loads((tmp_path / "out" / "benchmark.json").read_text())
    assert saved["right"] == 1
    assert (tmp_path / "out" / "benchmark.csv").read_text().count("dirt") == 2
    assert "frames right: 1 of 2" in benchmark.report(result)


def test_run_keeps_extra_columns_and_uses_the_ride_without_a_way(tmp_path, monkeypatch):
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text("kartaview_sequence,photo,region,split,surface_by_eye\n7,1,mekong,test,unpaved\n")
    monkeypatch.setattr(benchmark, "fetch_frames", lambda labels, frames_dir: [])
    (tmp_path / "out" / "frames").mkdir(parents=True)
    (tmp_path / "out" / "frames" / "7_00001.jpg").write_bytes(jpeg())

    result = benchmark.run(labels_csv, tmp_path / "out", segmenter=FakeSegmenter())

    assert [w["way_id"] for w in result["per_way"]] == ["7"]
    assert "mekong,test" in (tmp_path / "out" / "benchmark.csv").read_text()


def test_run_scores_one_split_with_preferred_labels(tmp_path, monkeypatch):
    labels_csv = tmp_path / "labels.csv"
    labels_csv.write_text("kartaview_sequence,photo,split,surface_by_eye\n7,1,test,unclear\n7,2,dev,paved\n")
    prefer_csv = tmp_path / "owner.csv"
    prefer_csv.write_text("kartaview_sequence,photo,surface_by_eye\n7,00001,unpaved\n")
    monkeypatch.setattr(benchmark, "fetch_frames", lambda labels, frames_dir: [])
    (tmp_path / "out" / "frames").mkdir(parents=True)
    for name in ["7_00001.jpg", "7_00002.jpg"]:
        (tmp_path / "out" / "frames" / name).write_bytes(jpeg())

    result = benchmark.run(labels_csv, tmp_path / "out", segmenter=FakeSegmenter(), split="test", prefer=[prefer_csv])

    assert result["labels"] == 1
    assert result["clear"] == 1
    assert [r["surface_by_eye"] for r in benchmark.load_labels(tmp_path / "out" / "benchmark.csv")] == ["unpaved"]
