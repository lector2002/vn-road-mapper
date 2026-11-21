import csv

import pytest

from pipeline import run as pipeline_run


@pytest.fixture
def stages(monkeypatch, tmp_path):
    calls = []

    def frames(out):
        out.mkdir(parents=True, exist_ok=True)
        with open(out / "frames.csv", "w", newline="") as f:
            csv.writer(f).writerows([["filename", "timestamp", "lat", "lon", "heading"], ["000001.jpg", "", "1", "2", ""]])

    def segmentation(frames_dir, out, overlays, model):
        calls.append("segmentation")
        with open(out / "segmentation.csv", "w", newline="") as f:
            csv.writer(f).writerows([["filename", "label", "confidence"], ["000001.jpg", "dirt", "0.9"]])

    def mapmatch(frames_csv, out, url):
        calls.append(("mapmatch", url))
        with open(out / "matches.csv", "w", newline="") as f:
            csv.writer(f).writerows([["filename", "way_id"], ["000001.jpg", "42"]])

    monkeypatch.setattr(pipeline_run.kartaview, "run", lambda seq, out, every: calls.append(("kartaview", seq, every)) or frames(out))
    monkeypatch.setattr(pipeline_run.extract, "run", lambda video, gpx, out: calls.append(("video", video.name)) or frames(out))
    monkeypatch.setattr(pipeline_run.segment, "run", segmentation)
    monkeypatch.setattr(pipeline_run.estimate, "run", lambda *a: calls.append(("width", a[2])))
    monkeypatch.setattr(pipeline_run.match, "run", mapmatch)
    monkeypatch.setattr(pipeline_run.export, "run", lambda ways_csv, out: calls.append("export"))
    return calls


def test_kartaview_ride_runs_every_stage_but_width_without_camera_height(stages, tmp_path):
    ways = pipeline_run.run(tmp_path / "r", kartaview_sequence="99", every=2, valhalla="http://local", log=lambda m: None)
    assert stages == [("kartaview", "99", 2), "segmentation", ("mapmatch", "http://local"), "export"]
    assert [w["way_id"] for w in ways] == ["42"]
    assert (tmp_path / "r" / "ways.csv").exists()


def test_video_ride_with_camera_height_runs_width_and_can_skip_export(stages, tmp_path):
    pipeline_run.run(tmp_path / "r", video=tmp_path / "ride.mp4", gpx=tmp_path / "ride.gpx", camera_height=1.1,
                     do_export=False, log=lambda m: None)
    assert stages[0] == ("video", "ride.mp4")
    assert ("width", 1.1) in stages
    assert "export" not in stages


def test_cli_needs_a_video_or_kartaview(tmp_path):
    with pytest.raises(SystemExit):
        pipeline_run.main(["--out", str(tmp_path)])
    with pytest.raises(SystemExit):
        pipeline_run.main(["ride.mp4", "--out", str(tmp_path)])
