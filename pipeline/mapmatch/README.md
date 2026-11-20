# mapmatch stage

Snaps each GPS-tagged frame onto the OpenStreetMap way the rider was on.

## Usage

```bash
python -m pipeline.mapmatch.match output/ride1/frames.csv --out output/ride1
```

Output `matches.csv`: `filename,way_id,matched_lat,matched_lon,distance_m`. `distance_m` is how far the GPS point was from the road. Frames without a GPS position, or that the matcher could not place, get a blank `way_id`.

## How

It sends the frame positions and times to a [Valhalla](https://valhalla.github.io/valhalla/) server (`trace_attributes`), which returns the OSM way for each point.

- `--url` — Valhalla server. The default is the public FOSSGIS server (`valhalla1.openstreetmap.de`). It receives your ride's GPS track; for real riders' data, run your own Valhalla server and pass its URL.
- `--costing auto` — routing profile. On a test trace along an unpaved road near Hòa Bình, `auto` matched 36 of 36 points, `motor_scooter` 20 of 36 and `bicycle` 27 of 36 (2026-11-20). Try `motor_scooter` again if rides use paths that cars cannot.

Tests: `RUN_NETWORK_TESTS=1 python -m pytest tests` also calls the live server.
