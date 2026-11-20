# 2026-11-20: HeiGIT road surface data, and a 20 m piece vote

Two ideas from similar projects, checked against our runs.

## HeiGIT Viet Nam road surface data

Source: HeiGIT, "Viet Nam road surface data" on HDX, `heigit_vnm_roadsurface_lines.gpkg` (1.5 GB, file date 2024-11-19, ODbL). One row per OSM way, some ways listed twice. A deep-learning model labelled Mapillary photos `paved` or `unpaved` (`pred_class`).

| check | result |
|---|---|
| Rows with a prediction, all of Viet Nam | 117,615 of 3,564,761 (100,111 paved, 17,504 unpaved); 45,000 of 844,000 km of road length (5.3%) |
| Our fused ways (Thanh Hóa 39 + 29, Cần Thơ 9, a test route 6) | 73 of 83 are in the file; the other 10 are not (probably made after the snapshot). 0 have a prediction. |
| All roads around the two Thanh Hóa rides | 0 predictions (6,337 and 8,299 rows) |
| All roads around the Cần Thơ rides | 55 of 1,260 km have a prediction (4.4%), none on our 9 ways |
| OSM tag in their snapshot, Cần Thơ ways | 8 of 9 `unpaved`, the same tags we tested against |

So the file cannot check our results: it has no prediction where we have footage. It does show the gap the project is for: around both Thanh Hóa rides no road has a machine prediction, and around Cần Thơ 4.4% of road length has one. It may serve as a second source of labels on other roads in the Mekong delta (not tried).

## Vote per 20 m piece of road

SurfaceAI votes per 20 m piece of road first, then across the pieces, so many frames from one spot (a long stop) cannot outvote the rest of the road. It also drops images more than 10 m from the road. Simulated on our runs (`frames per piece` uses a 20 m grid on the matched points):

| run | frames per 20 m piece | ways that change surface or `weak` status |
|---|---|---|
| Thanh Hóa ride 1 (559 frames) | median 1, max 2 | 0 of 39 |
| Thanh Hóa ride 2 (475 frames) | median 1, max 1 | 0 of 29 |
| Cần Thơ (360 frames) | median 2, max 6 | 1 of 9: way 167961113 goes from `weak` (0.63) to 0.70, a way that is mixed by eye |
| test route (168 frames) | median 1, max 3 | 0 of 6 |

KartaView photos are not bunched, so the piece vote changes nothing that matters here, and its one change is in the wrong direction. A 10 m cut on `distance_m` makes 5 of 29 ways on ride 2 `weak`; on one of them it removes 44 of 45 votes (distance up to 21.7 m on a wide road). Neither change was made.

Own phone video is cut at a fixed time step (2 frames per second), so a stop does give many frames of one spot. Check the piece vote again on the first phone video with stops.

Imagery: KartaView, CC BY-SA 4.0, in `output/` only. HeiGIT data in `output/heigit/` only.
