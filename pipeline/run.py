"""Run every stage on one ride: a video + GPX, or a public KartaView sequence."""
import argparse
import subprocess
import sys
import urllib.error
from pathlib import Path

from pipeline.export import export
from pipeline.frames import extract
from pipeline.fusion import fuse
from pipeline.mapmatch import match
from pipeline.segmentation import segment
from pipeline.width import estimate
from tools import kartaview


def run(out, video=None, gpx=None, kartaview_sequence=None, every=1, camera_height=None, model=segment.DEFAULT_MODEL,
        overlays=5, valhalla=match.DEFAULT_URL, do_export=True, log=print):
    out = Path(out)
    if kartaview_sequence:
        log(f"frames: KartaView sequence {kartaview_sequence}")
        kartaview.run(kartaview_sequence, out, every=every)
    else:
        log(f"frames: {video}")
        extract.run(video, gpx, out)
    log("segmentation")
    segment.run(out / "frames", out, overlays, model)
    if camera_height:
        log("width")
        estimate.run(out / "frames", out, camera_height, overlays, model)
    log("mapmatch")
    match.run(out / "frames.csv", out, valhalla)
    log("fusion")
    ways = fuse.fuse(fuse.load_run(out))
    fuse.write(ways, out)
    if do_export:
        log("export")
        export.run(out / "ways.csv", out)
    return ways


def main(argv=None):
    p = argparse.ArgumentParser(description="Run frames, segmentation, width, mapmatch, fusion and export on one ride.")
    p.add_argument("video", nargs="?", type=Path, help="ride video (with gpx), or leave out and use --kartaview")
    p.add_argument("gpx", nargs="?", type=Path)
    p.add_argument("--kartaview", metavar="SEQUENCE_ID", help="use a public KartaView sequence instead of a video")
    p.add_argument("--every", type=int, default=1, help="with --kartaview: keep every n-th photo")
    p.add_argument("--out", type=Path, required=True)
    p.add_argument("--camera-height", type=float, help="lens height above the road in m; leave out to skip width")
    p.add_argument("--model", default=segment.DEFAULT_MODEL)
    p.add_argument("--overlays", type=int, default=5)
    p.add_argument("--valhalla", default=match.DEFAULT_URL, help="Valhalla server; self-host for real riders' tracks")
    p.add_argument("--no-export", action="store_true", help="stop after fusion (export calls the OSM API)")
    args = p.parse_args(argv)
    if bool(args.kartaview) == bool(args.video):
        p.error("give either a video and a gpx file, or --kartaview")
    if args.video and not args.gpx:
        p.error("a video needs a gpx file")
    try:
        ways = run(args.out, args.video, args.gpx, args.kartaview, args.every, args.camera_height, args.model,
                   args.overlays, args.valhalla, not args.no_export)
    except (ValueError, OSError, subprocess.CalledProcessError, urllib.error.URLError) as e:
        sys.exit(f"error: {e}")
    print(f"{len(ways)} ways -> {args.out}")


if __name__ == "__main__":
    main()
