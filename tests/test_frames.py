import csv
import json
import shutil
import subprocess
from datetime import datetime, timedelta, timezone

import pytest

from pipeline.frames.extract import main, parse_start
from pipeline.frames.gps import TrackPoint, bearing, load_track, position_at

T0 = datetime(2026, 3, 1, 2, 0, 0, tzinfo=timezone.utc)


def write_gpx(path, points):
    trkpts = "\n".join(
        f'<trkpt lat="{lat}" lon="{lon}"><time>{t.strftime("%Y-%m-%dT%H:%M:%S.%fZ")}</time></trkpt>'
        for t, lat, lon in points
    )
    path.write_text(
        '<?xml version="1.0"?><gpx version="1.1" creator="test" xmlns="http://www.topografix.com/GPX/1/1">'
        f"<trk><trkseg>{trkpts}</trkseg></trk></gpx>",
        encoding="utf-8",
    )
    return path


def make_video(path, seconds, creation_time=T0):
    cmd = ["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", f"testsrc=duration={seconds}:size=320x240:rate=30",
           "-pix_fmt", "yuv420p"]
    if creation_time:
        cmd += ["-metadata", f"creation_time={creation_time.strftime('%Y-%m-%dT%H:%M:%S.%fZ')}"]
    subprocess.run(cmd + [str(path)], check=True)
    return path


def duration(path):
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)],
                         capture_output=True, text=True, check=True).stdout
    return float(json.loads(out)["format"]["duration"])


def track(*points):
    return [TrackPoint(T0 + timedelta(seconds=s), lat, lon) for s, lat, lon in points]


def test_bearing_points_north_east_south_west():
    assert bearing(21.0, 105.0, 21.001, 105.0) == pytest.approx(0.0, abs=0.01)
    assert bearing(21.0, 105.0, 21.0, 105.001) == pytest.approx(90.0, abs=0.01)
    assert bearing(21.0, 105.0, 20.999, 105.0) == pytest.approx(180.0, abs=0.01)
    assert bearing(21.0, 105.0, 21.0, 104.999) == pytest.approx(270.0, abs=0.01)


def test_bearing_slightly_west_of_north_stays_near_360_not_negative():
    h = bearing(21.0, 105.0, 21.001, 104.99999)
    assert 359.0 < h < 360.0


def test_position_interpolates_linearly_between_points():
    pos = position_at(track((0, 21.0, 105.0), (10, 21.01, 105.02)), T0 + timedelta(seconds=2.5))
    assert pos.lat == pytest.approx(21.0025)
    assert pos.lon == pytest.approx(105.005)


def test_position_is_none_outside_track_time_range():
    tr = track((0, 21.0, 105.0), (10, 21.01, 105.0))
    assert position_at(tr, T0 - timedelta(seconds=1)) is None
    assert position_at(tr, T0 + timedelta(seconds=11)) is None


def test_heading_is_none_when_rider_is_stopped():
    pos = position_at(track((0, 21.0, 105.0), (10, 21.0, 105.0)), T0 + timedelta(seconds=5))
    assert pos.heading is None


def test_position_accepts_naive_time_as_utc():
    pos = position_at(track((0, 21.0, 105.0), (10, 21.01, 105.0)), (T0 + timedelta(seconds=5)).replace(tzinfo=None))
    assert pos.lat == pytest.approx(21.005)


def test_load_track_rejects_gpx_with_fewer_than_two_points(tmp_path):
    gpx = write_gpx(tmp_path / "one.gpx", [(T0, 21.0, 105.0)])
    with pytest.raises(ValueError):
        load_track(gpx)


def test_parse_start_converts_vietnam_time_to_utc():
    assert parse_start("2026-03-01T09:00:00+07:00") == T0


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_cli_writes_one_tagged_row_per_frame_and_blanks_outside_gpx(tmp_path):
    video = make_video(tmp_path / "ride.mp4", 5.3)
    fps = 2.0
    gpx_start, gpx_end = 1.0, 4.0
    gpx = write_gpx(tmp_path / "ride.gpx", [
        (T0 + timedelta(seconds=gpx_start), 21.0, 105.0),
        (T0 + timedelta(seconds=gpx_end), 21.003, 105.0),
    ])

    main([str(video), str(gpx), "--out", str(tmp_path / "out"), "--fps", str(fps)])

    with open(tmp_path / "out" / "frames.csv", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    jpgs = sorted(p.name for p in (tmp_path / "out" / "frames").glob("*.jpg"))
    assert [r["filename"] for r in rows] == jpgs
    assert abs(len(rows) - duration(video) * fps) <= 1
    for i, row in enumerate(rows):
        t = i / fps
        assert row["timestamp"] == (T0 + timedelta(seconds=t)).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        inside = gpx_start <= t <= gpx_end
        assert bool(row["lat"]) == inside
        if inside:
            expected_lat = 21.0 + (t - gpx_start) / (gpx_end - gpx_start) * 0.003
            assert float(row["lat"]) == pytest.approx(expected_lat, abs=1e-6)
            assert float(row["heading"]) == pytest.approx(0.0, abs=0.1)


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_cli_refuses_folder_with_frames_from_an_earlier_run(tmp_path):
    video = make_video(tmp_path / "ride.mp4", 1)
    gpx = write_gpx(tmp_path / "ride.gpx", [(T0, 21.0, 105.0), (T0 + timedelta(seconds=10), 21.01, 105.0)])
    (tmp_path / "out" / "frames").mkdir(parents=True)
    (tmp_path / "out" / "frames" / "000099.jpg").write_bytes(b"old")

    with pytest.raises(SystemExit, match="already has frames"):
        main([str(video), str(gpx), "--out", str(tmp_path / "out")])


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg not installed")
def test_cli_start_flag_overrides_missing_creation_time(tmp_path):
    video = make_video(tmp_path / "ride.mp4", 2, creation_time=None)
    gpx = write_gpx(tmp_path / "ride.gpx", [(T0, 21.0, 105.0), (T0 + timedelta(seconds=10), 21.01, 105.0)])

    with pytest.raises(SystemExit, match="creation_time"):
        main([str(video), str(gpx), "--out", str(tmp_path / "a")])

    main([str(video), str(gpx), "--out", str(tmp_path / "b"), "--start", "2026-03-01T09:00:00+07:00"])
    with open(tmp_path / "b" / "frames.csv", encoding="utf-8") as f:
        assert all(r["lat"] for r in csv.DictReader(f))
