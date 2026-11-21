# MapRoulette challenge draft

Create this at [maproulette.org](https://maproulette.org) only after the community discussion (step 4 of the [kit](README.md)). Rebuild `data/challenge.geojson` first so it skips ways tagged since.

## Settings

| Field | Value |
|---|---|
| Name | Vietnam: add surface to small roads in Ô Môn, Cần Thơ (vn-road-mapper pilot) |
| Project | a new project of your own, e.g. "vn-road-mapper" |
| Data source | Upload GeoJSON file → `docs/pilot/data/challenge.geojson` (one task per line; each task is a tag fix that sets only `surface`) |
| Difficulty | Easy |
| Changeset comment | `Add surface from KartaView photos (vn-road-mapper pilot) #vnroadmapper` |
| Changeset source | `KartaView` |
| Default zoom | 17 |
| Basemap | Esri World Imagery (or any imagery the community recommends) |
| Discoverable | off until the community thread agrees, then on |

## Description

> Add a surface tag to small roads in and around Ô Môn, Cần Thơ. Each suggestion comes from public KartaView photos taken along the road in May 2023 and is a guess by the open-source tool vn-road-mapper. Please check the photos before you accept. About the project and the community discussion: <WIKI PAGE>

## Instructions

> 1. Look at the KartaView photos taken on this road: [photo 1]({{photo_1}}), [photo 2]({{photo_2}}), [photo 3]({{photo_3}}).
> 2. Decide whether the road is **paved** (asphalt, concrete, paving stones, including the narrow concrete lanes common in the Mekong delta) or **unpaved** (dirt, gravel, sand, grass).
> 3. If the suggestion `{{proposed_surface}}` is right, approve the tag change.
> 4. If it is wrong, reject the change, tag the right value yourself if you are sure, and mark the task **Not an issue** with a short comment ("concrete lane", "photos are of a different road", ...).
> 5. If the photos don't show this road or you can't tell, mark the task **Too hard / can't verify** and skip.
> 6. Don't change any other tag in these tasks.
>
> Suggestion: `surface={{proposed_surface}}` from {{votes}} photos, {{agreement}} of them agreeing.

## Scoring when done

On the challenge page, export the task CSV, then:

```bash
python -m tools.pilot score export.csv
```

Fixed counts as accepted; Not an issue and False positive count as rejected; Too hard, Skipped, Already fixed and Created don't count. Already fixed means someone tagged the way in the meantime. 90% or more accepted passes. To score a review done without MapRoulette, fill the `decision` column of `data/pilot.csv` with `accept` or `reject` and run `python -m tools.pilot score docs/pilot/data/pilot.csv`.
