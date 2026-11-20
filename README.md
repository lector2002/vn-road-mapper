# vn-road-mapper

Mapping the rural roads in Vietnam that Google Maps cars never reach.

Phone video from a motorbike → AI tags road **surface, width and flood passability** → pushed to **OpenStreetMap**.
Goal: riders, ambulances and health stations know which roads are passable, especially in flood season.

> Status: **prototype.** All six stages run end to end on test data and on two public KartaView motorbike rides ([paved rides](docs/evaluation/2026-11-20-kartaview-thanh-hoa.md), [unpaved roads and OSM widths](docs/evaluation/2026-11-20-kartaview-can-tho.md), [HeiGIT data and a 20 m piece vote](docs/evaluation/2026-11-20-heigit-and-piece-vote.md)). No own ride recorded yet.

## Pipeline

```
capture (phone video + GPS/IMU)
  → frames        ffmpeg, ~2 fps, synced to GPS track
  → segmentation  SegFormer-B2 (ADE20K baseline) fine-tuned on VN frames
                  classes: paved / dirt / mud / water / vegetation
  → width         road mask + camera height → road width per frame
  → mapmatch      Valhalla map matching onto OSM ways
  → fusion        majority vote across multiple passes, foliage masked out
  → export        OSM surface tag proposals (osmChange) + review map
                  later: width / smoothness tags, flood layer (PostGIS)
```

## Run

```bash
py -3.12 -m venv .venv
.venv/Scripts/python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
.venv/Scripts/python -m pip install transformers gpxpy pillow numpy pytest

R=output/ride1
python -m pipeline.frames.extract ride.mp4 ride.gpx --out $R
python -m pipeline.segmentation.segment $R/frames --out $R
python -m pipeline.width.estimate $R/frames --out $R --camera-height 1.1
python -m pipeline.mapmatch.match $R/frames.csv --out $R
python -m pipeline.fusion.fuse $R --out $R
python -m pipeline.export.export $R/ways.csv --out $R
```

No ride of your own? `python -m tools.kartaview <sequence-id> --out $R` fetches a public KartaView sequence as frames + `frames.csv` (then skip `frames.extract`).

Needs `ffmpeg` on `PATH`. Each stage's README explains its output. Tests: `python -m pytest tests`.

## Repo layout

```
capture/            Android capture app (video + GPS/IMU logging)
pipeline/frames/    frame extraction + GPS sync
pipeline/segmentation/
pipeline/width/
pipeline/mapmatch/
pipeline/fusion/
pipeline/export/    OSM edit proposals + review map
tools/              KartaView importer (public imagery as test rides)
data/samples/       small sample clips (large raw video is gitignored)
docs/               decisions/, evaluation/
```

## Roadmap

- [ ] **Week 1–2:** capture first test ride, frame extraction + GPS sync working
- [ ] **Week 2:** baseline surface segmentation on sample frames
- [ ] **Week 3:** map matching + multi-pass fusion → first tagged road segments
- [ ] **Week 4:** flood passability layer for one district
- [ ] **Milestone:** 10 riders, 100 km mapped in one rural district

## How we get data

1. Recruit 10–20 delivery / ride-hailing riders in one district via Zalo & Facebook driver groups, paid per km of usable footage.
2. OSM Vietnam community validates and maintains the tags.
3. Take the flood passability map to commune health stations and the district Red Cross.

## License

MIT (code). Map data contributed to OSM under ODbL.
