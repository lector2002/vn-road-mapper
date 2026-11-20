# tools

## kartaview.py

Downloads a public [KartaView](https://kartaview.org) photo sequence and writes it in the frames stage's format (`frames/*.jpg` at 1280×720 + `frames.csv`). This lets the later stages run on real street imagery before you have your own rides.

```bash
python -m tools.kartaview 3846125 --out output/kv-3846125 --every 2
```

- `--every 2` keeps every 2nd photo.
- Portrait-shaped photos are turned 90° to landscape. The capture app saved some landscape shots as portrait with the scene on its side; the model labeled many of those `water`.
- It also writes `kartaview.csv` with KartaView's own matched OSM way per photo, as a cross-check for the mapmatch stage.
- Find sequences with `https://api.kartaview.org/2.0/sequence/?countryCode=VN&itemsPerPage=100&page=1`.

KartaView imagery is CC BY-SA 4.0. Keep downloaded frames out of the repo (`output/` is ignored).
