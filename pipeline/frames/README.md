# frames stage

Cuts a ride video into still frames (2 per second by default) and tags each frame with the GPS position at that moment.

## Usage

```bash
python -m pipeline.frames.extract ride.mp4 ride.gpx --out output/ride1
```

Output:

```
output/ride1/frames/000001.jpg ...
output/ride1/frames.csv      filename,timestamp,lat,lon,heading
```

| column | meaning |
|---|---|
| `timestamp` | UTC time of the frame = video start + frame index / fps |
| `lat`, `lon` | linear interpolation between the two GPX points around that time |
| `heading` | compass bearing (0 = north, 90 = east) of the GPX segment the frame falls in |

A frame outside the GPX time range gets blank `lat`/`lon`/`heading`. A frame where the rider stood still (two identical GPX points) gets a blank `heading`.

## Options

- `--fps 2` — frames per second to keep.
- `--start 2026-03-01T09:00:00+07:00` — video start time. Use it when the video has no `creation_time` tag, or when that tag is wrong. Some Android phones write the time the recording stopped, not started; compare the first frame with the GPX track if positions look shifted.

The `--out` folder must not already contain frames.

## Needs

`ffmpeg` and `ffprobe` on `PATH`.
