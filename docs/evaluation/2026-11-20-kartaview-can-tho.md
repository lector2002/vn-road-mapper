# 2026-11-20: Unpaved roads and OSM width tags (KartaView, Cần Thơ)

The Thanh Hóa rides (`2026-11-20-kartaview-thanh-hoa.md`) were almost all paved. This test looks for public footage of unpaved roads, and for roads with a `width` tag in OSM.

## How the footage was found

1. Listed all KartaView sequences in Vietnam: 83,554 (`api.kartaview.org/2.0/sequence/?countryCode=VN`, 100 per page, about 15 minutes).
2. Listed OSM ways in Vietnam with an unpaved `surface` (`dirt`, `ground`, `unpaved`, `gravel`, `compacted` and similar) through Overpass: 133,316 ways. Also listed minor roads with a `width` tag: 1,415 ways.
3. Kept the sequences with at least 50 photos whose box contains such a way. Ranked them by ways per area. Read the photo list of the top 40, and counted the photos that KartaView matched to one of those ways.

Unpaved: 6 sequences had photos on unpaved ways: 5 in Cần Thơ, 1 in Lái Thiêu (Bình Dương), all uploaded in November 2023. Width: 6 more Cần Thơ sequences from the same weeks had photos on 5 width-tagged ways.

In the Cần Thơ sequences the camera is a 360° camera on a helmet, cut to a forward view. The rider's helmet and black curved masks sit in the bottom of every frame, which is where the surface box is. The Lái Thiêu sequence (8288905) is a camera that points at the ground from close up. This is not the footage the pipeline is built for, so the numbers below are a rough check only.

## Unpaved roads

360 frames on 9 OSM-unpaved ways (up to 60 per sequence). Sequences 8293273 and 8308153 look like one ride uploaded twice (the same frame gave the same result in both). 60 frames hand-labelled by eye, 10 per sequence: 16 paved, 31 unpaved, 13 unclear.

| check | result |
|---|---|
| OSM tag vs eye | 16 of the 47 clear frames on "unpaved" ways show paving: a tiled riverside path, concrete alleys. Either the OSM tags are out of date or KartaView matched the photos to the wrong way (not checked). |
| Frames that voted, before the change below | 18 right, 5 wrong, 24 no vote |
| Frames that voted, after the change below | 27 right (12 paved, 15 unpaved), 5 wrong, 15 no vote |
| Kind of error | All 5 wrong frames are dirt roads called `paved`: ADE20K labels compacted dirt as `road` (4 frames), and one close-up of gravel from the camera that points at the ground. No paved road was called `dirt`. A later set of 142 labelled frames found 3 (`2026-11-20-can-tho-labels-and-probe.md`). |
| Per way, where the hand labels have a clear majority | 4 of 5 agree (2 dirt, 2 paved; one paved way has only 1 hand-labelled frame). The miss is a dirt way with a single `paved` vote, from the camera that points at the ground; export would mark it `weak`. |
| Per way, mixed or unclear by eye | 3 ways; the model says `paved` on all 3. 1 more way (camera at the ground) got no surface. |

What changed: the helmet and masks are `other` pixels in the surface box, and they pushed many frames to `other` or below the confidence cut. Segmentation now leaves `other` pixels out when it picks the label and computes `confidence`. It still needs at least 40% ground in the box. The re-label changed no label on the 12 Wikimedia photos and no way on the Thanh Hóa rides.

## Width against OSM `width` tags

235 frames on 5 width-tagged ways, camera height guessed at 1.5 m (helmet).

| OSM way | `width` tag | frames | frames with a width | median |
|---|---|---|---|---|
| 543853030 (concrete service road) | 3 | 40 | 2 | 3.4 m |
| 533737466 | 3 | 40 | 2 | 3.2 m |
| 119275355 | 6 | 80 | 4 | 5.1 m (3.1–11.6) |
| 533313749 | 3 | 40 | 0 | – |
| 89626432 | 5 m | 35 | 0 | – |

Only 8 of 235 frames passed the width checks. The fisheye cut is not a pinhole view, so the flat-ground fit rarely holds. The two 3 m roads came out at 3.2–3.4 m, but 2 frames each and a guessed camera height do not confirm anything. Width stays unconfirmed.

## What this does not show

- Mud and floodwater: no frame in this set shows standing water across the road.
- Phone footage of unpaved roads: no public phone sequence on an unpaved way was found among the top 40.
- Width accuracy: needs phone footage on a road with a known width.

Imagery: KartaView, CC BY-SA 4.0, kept in `output/` and out of the repo.
