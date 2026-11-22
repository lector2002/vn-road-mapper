import io
import json

from PIL import Image

from tools import agreement, benchmark, candidates, labelpage, panoramax, sources

API = panoramax.API


def item(i, t, rank):
    return {"id": f"uuid-{i}", "geometry": {"type": "Point", "coordinates": [106.2, 10.0]},
            "properties": {"datetime": t, "view:azimuth": 90, "geovisio:producer": "rider",
                           "geovisio:rank_in_collection": rank}}


def jpeg(width=40, height=30):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "grey").save(buf, "JPEG")
    return buf.getvalue()


def test_list_photos_follows_next_links_and_sorts_by_time(monkeypatch):
    first = f"{API}/collections/col/items?limit=500"
    pages = {
        first: {"features": [item(2, "2025-02-15T06:42:00+00:00", 2)],
                "links": [{"rel": "next", "href": "https://next"}, {"rel": "self", "href": first}]},
        "https://next": {"features": [item(1, "2025-02-15T06:41:00+00:00", 1)], "links": []},
    }
    monkeypatch.setattr(panoramax, "get", lambda url: json.dumps(pages[url]).encode())
    photos = panoramax.list_photos("col")
    assert [p["id"] for p in photos] == ["uuid-1", "uuid-2"]
    assert photos[0]["lat"] == "10.000000" and photos[0]["lng"] == "106.200000"
    assert photos[0]["shotDate"] == "2025-02-15 06:41:00" and photos[0]["creator"] == "rider"


def test_photo_url_needs_no_token():
    assert panoramax.photo_url("uuid-1") == f"{API}/pictures/uuid-1/sd.jpg"


def pmx(photo, eye="unpaved"):
    return {"panoramax_sequence": "col", "photo": photo, "surface_by_eye": eye}


def test_rows_with_a_panoramax_sequence_are_panoramax():
    row = pmx("uuid-1")
    assert sources.source(row) == "panoramax" and sources.sequence(row) == "col"
    assert sources.key(row) == ("panoramax", "uuid-1") and sources.frame_name(row) == "pmx_uuid-1.jpg"
    assert "Panoramax" in sources.credit(row) and "license on its Panoramax page" in sources.credit(row)
    assert sources.credit({**row, "creator": "Dodko", "license": "CC BY-SA 4.0"}).endswith("by Dodko, sequence col, CC BY-SA 4.0")
    assert sources.key_columns([row]) == ["panoramax_sequence", "photo"]


def test_candidates_key_panoramax_photos_by_item_id():
    seqs = [{"panoramax_sequence": "col", "region": "mekong", "split": "test"}]
    photos = [panoramax.photo(item(i, f"2025-02-15T06:{i:02d}:00+00:00", i)) for i in range(10)]
    rows = candidates.candidates(seqs, 2, photos_of=lambda s: photos)
    assert rows[0]["panoramax_sequence"] == "col" and rows[0]["photo"].startswith("uuid-")
    assert rows[0]["shot_date"] == "2025-02-15"


def test_fetch_frames_saves_panoramax_photos_without_turning(tmp_path):
    downloaded = []

    def download(url):
        downloaded.append(url)
        return jpeg(30, 40)

    missing = benchmark.fetch_frames([pmx("uuid-1")], tmp_path, photos_of=lambda s: 1 / 0, download=download,
                                     panoramax_url=lambda i: f"https://pmx/{i}")
    assert missing == [] and downloaded == ["https://pmx/uuid-1"]
    assert Image.open(tmp_path / "pmx_uuid-1.jpg").size == (30, 40)


def test_label_page_embeds_panoramax_photos():
    items, missing = labelpage.items([pmx("uuid-1")], photos_of=lambda s: 1 / 0, download=lambda url: jpeg(),
                                     panoramax_url=lambda i: f"https://pmx/{i}", link=True)
    assert missing == [] and items[0]["fields"] == ["col", "uuid-1"]
    assert items[0]["src"].startswith("data:image/jpeg;base64,") and "Panoramax" in items[0]["credit"]


def test_agreement_reports_panoramax_disagreements_by_sequence():
    result = agreement.compare([pmx("uuid-1"), pmx("uuid-2", "paved")], [pmx("uuid-1"), pmx("uuid-2")])
    assert (result["compared"], result["agree"]) == (2, 1)
    assert "col/uuid-2" in agreement.report(result)
