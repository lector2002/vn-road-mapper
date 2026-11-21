# vn-road-mapper

Mapping the rural roads in Vietnam that Google Maps cars never reach.

Phone video from a motorbike → AI tags road **surface, width and flood passability** → pushed to **OpenStreetMap**.
Goal: riders, ambulances and health stations know which roads are passable, especially in flood season.

> Status: **prototype.** All six stages run end to end on test data and on public KartaView motorbike rides ([paved rides](docs/evaluation/2026-11-20-kartaview-thanh-hoa.md), [unpaved roads and OSM widths](docs/evaluation/2026-11-20-kartaview-can-tho.md), [HeiGIT data and a 20 m piece vote](docs/evaluation/2026-11-20-heigit-and-piece-vote.md), [Cần Thơ labels and a dirt/paved probe](docs/evaluation/2026-11-20-can-tho-labels-and-probe.md)). Paved roads come out right; dirt roads are often called paved (112 of 142 labelled frames right). Mud, flood and width are untested or unconfirmed. Test data comes from public street imagery; no own rides.

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

Python 3.12 and `ffmpeg` on `PATH`.

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu
pip install -r requirements-model.txt -r requirements-dev.txt
```

All stages on one ride:

```bash
python -m pipeline.run ride.mp4 ride.gpx --out output/ride1 --camera-height 1.1
python -m pipeline.run --kartaview <sequence-id> --every 2 --out output/kv1   # public KartaView sequence instead of a video
```

`--camera-height` turns on the width stage; `--start` gives the video start time when the file has no `creation_time` tag; `--no-export` stops before the OSM API calls. Each stage also runs on its own (`python -m pipeline.frames.extract`, `pipeline.segmentation.segment`, `pipeline.width.estimate`, `pipeline.mapmatch.match`, `pipeline.fusion.fuse`, `pipeline.export.export`); each stage's README explains its output.

Score the surface stage against the Cần Thơ hand labels (downloads the 177 labelled KartaView photos into `--out`):

```bash
python -m tools.benchmark docs/evaluation/data/2026-11-20-can-tho-hand-labels.csv --out output/bench-can-tho
```

Tests: `python -m pytest tests` (`RUN_MODEL_TESTS=1` adds the real model, `RUN_NETWORK_TESTS=1` the Valhalla and OSM API calls). The default tests need only `requirements-dev.txt`.

## Repo layout

```
capture/            Android capture app (parked: test data comes from public imagery)
pipeline/frames/    frame extraction + GPS sync
pipeline/segmentation/
pipeline/width/
pipeline/mapmatch/
pipeline/fusion/
pipeline/export/    OSM edit proposals + review map
tools/              KartaView importer, surface benchmark, label page
data/samples/       small sample clips (large raw video is gitignored)
docs/               decisions/, evaluation/
```

## Roadmap

Public imagery first; nothing depends on hiring riders or labellers. Details and what to expect from each phase: [docs/roadmap.md](docs/roadmap.md).

- [x] **Phase 0:** one-command run and surface benchmark, split requirements, weekly model check in CI
- [ ] **Phase 1:** trusted Vietnamese test set from public imagery. Done: label page, agreement check, 585 candidate frames from 13 sequences in 4 regions. Left: the owner's 50-photo spot check, then labels for the candidates
- [ ] **Phase 2:** fix dirt roads called paved
- [ ] **Phase 3:** OSM Vietnam community review, then a small human-reviewed pilot
- [ ] **Phase 4:** width as classes (motorbike only / one car / two cars)
- [ ] **Phase 5:** flood-risk layer from satellite flood maps and elevation
- [ ] **Phase 6:** one province, self-hosted Valhalla, PostGIS

## Where the data comes from

1. Public street imagery: KartaView and Mapillary sequences in Vietnam (CC BY-SA 4.0, downloaded into `output/` only).
2. OSM Vietnam community validates and maintains the tags.
3. Later, with partners: commune health stations and the district Red Cross for flood ground truth, and riders if a partner offers footage.

## License

MIT (code). Map data contributed to OSM under ODbL.
