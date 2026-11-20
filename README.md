# vn-road-mapper

Mapping the rural roads in Vietnam that Google Maps cars never reach.

Phone video from a motorbike → AI tags road **surface, width and flood passability** → pushed to **OpenStreetMap**.
Goal: riders, ambulances and health stations know which roads are passable, especially in flood season.

> Status: **prototype.** `frames` and `segmentation` stages work on test data; no real ride yet.

## Pipeline

```
capture (phone video + GPS/IMU)
  → frames        ffmpeg, ~2 fps, synced to GPS track
  → segmentation  SegFormer-B2 (ADE20K baseline) fine-tuned on VN frames
                  classes: paved / dirt / mud / water / vegetation
  → depth         Depth Anything V2 → road width per segment
  → mapmatch      OSRM / Valhalla map matching onto OSM ways
  → fusion        majority vote across multiple passes, foliage masked out
  → export        OSM surface / width / smoothness tags + flood layer (PostGIS)
```

## Repo layout

```
capture/            Android capture app (video + GPS/IMU logging)
pipeline/frames/    frame extraction + GPS sync
pipeline/segmentation/
pipeline/depth/
pipeline/mapmatch/
pipeline/fusion/
pipeline/export/    OSM changeset + PostGIS flood layer
data/samples/       small sample clips (large raw video is gitignored)
docs/
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
