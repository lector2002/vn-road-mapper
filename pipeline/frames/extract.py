import argparse
import csv
import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

from pipeline.frames.gps import load_track, position_at

CSV_FIELDS = ["filename", "timestamp", "lat", "lon", "heading"]


def video_start_time(video_path):
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format_tags=creation_time", "-of", "json", str(video_path)],
        capture_output=True, text=True, check=True,
    ).stdout
    value = json.loads(out).get("format", {}).get("tags", {}).get("creation_time")
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def extract_frames(video_path, out_dir, fps):
    out_dir.mkdir(parents=True, exist_ok=True)
    if any(out_dir.glob("*.jpg")):
        raise ValueError(f"{out_dir} already has frames; use an empty --out folder")
    subprocess.run(
        ["ffmpeg", "-v", "error", "-y", "-i", str(video_path), "-vf", f"fps={fps}", "-q:v", "2",
         str(out_dir / "%06d.jpg")],
        check=True,
    )
    return sorted(out_dir.glob("*.jpg"))


def build_rows(frame_paths, start, fps, track):
    rows = []
    for i, path in enumerate(frame_paths):
        # ffmpeg's fps filter puts output frame i at i / fps seconds from the start of the video.
        t = start + timedelta(seconds=i / fps)
        pos = position_at(track, t)
        rows.append({
            "filename": path.name,
            "timestamp": t.isoformat(timespec="milliseconds").replace("+00:00", "Z"),
            "lat": f"{pos.lat:.7f}" if pos else "",
            "lon": f"{pos.lon:.7f}" if pos else "",
            "heading": f"{pos.heading:.1f}" if pos and pos.heading is not None else "",
        })
    return rows


def run(video, gpx, out, fps=2.0, start=None):
    start = start or video_start_time(video)
    if start is None:
        raise ValueError(f"{video} has no creation_time tag; pass --start")
    track = load_track(gpx)
    frames_dir = Path(out) / "frames"
    rows = build_rows(extract_frames(video, frames_dir, fps), start, fps, track)
    csv_path = Path(out) / "frames.csv"
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        writer.writeheader()
        writer.writerows(rows)
    return csv_path, rows


def parse_start(value):
    t = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if t.tzinfo is None:
        raise argparse.ArgumentTypeError("--start needs a timezone, e.g. 2026-03-01T09:00:00+07:00")
    return t.astimezone(timezone.utc)


def main(argv=None):
    p = argparse.ArgumentParser(description="Extract frames from a ride video and tag each with GPS position.")
    p.add_argument("video", type=Path)
    p.add_argument("gpx", type=Path)
    p.add_argument("--out", type=Path, required=True, help="output folder (gets frames/ and frames.csv)")
    p.add_argument("--fps", type=float, default=2.0)
    p.add_argument("--start", type=parse_start,
                   help="video start time with timezone; overrides the video's creation_time tag")
    args = p.parse_args(argv)
    try:
        csv_path, rows = run(args.video, args.gpx, args.out, args.fps, args.start)
    except (ValueError, subprocess.CalledProcessError) as e:
        sys.exit(f"error: {e}")
    missing = sum(1 for r in rows if not r["lat"])
    print(f"{len(rows)} frames -> {csv_path}" + (f" ({missing} outside the GPX time range)" if missing else ""))


if __name__ == "__main__":
    main()
