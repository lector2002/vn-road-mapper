import io
import json
from collections import Counter

from PIL import Image

from tools import labelpage


def jpeg(width, height):
    buf = io.BytesIO()
    Image.new("RGB", (width, height), "gray").save(buf, "JPEG")
    return buf.getvalue()


def rows(n_paved, n_unpaved):
    return ([{"kartaview_sequence": "7", "photo": f"{i:05d}", "surface_by_eye": "paved"} for i in range(n_paved)]
            + [{"kartaview_sequence": "7", "photo": f"{100 + i:05d}", "surface_by_eye": "unpaved"}
               for i in range(n_unpaved)])


def test_sample_keeps_the_share_of_each_existing_label_and_is_repeatable():
    picked = labelpage.sample(rows(30, 70), 10, seed=3)
    assert Counter(r["surface_by_eye"] for r in picked) == {"paved": 3, "unpaved": 7}
    assert picked == labelpage.sample(rows(30, 70), 10, seed=3)


def test_sample_returns_everything_when_asked_for_more():
    assert len(labelpage.sample(rows(2, 2), 10)) == 4


def test_page_embeds_photos_without_the_existing_label():
    photos = [{"sequenceIndex": "1", "imageLthUrl": "cdn/1"}, {"sequenceIndex": "2", "imageLthUrl": "cdn/2"}]
    labels = [{"kartaview_sequence": "7", "photo": "00001", "surface_by_eye": "unpaved"},
              {"kartaview_sequence": "7", "photo": "00003", "surface_by_eye": "paved"}]
    items, missing = labelpage.items(labels, photos_of=lambda s: photos, download=lambda url: jpeg(1600, 900))
    assert missing == ["7/00003"]
    assert items[0]["key"] == "7_1" and items[0]["fields"] == ["7", "00001"]
    assert items[0]["src"].startswith("data:image/jpeg;base64,")
    html = labelpage.render("t", "Test", items)
    page = json.loads(html.split("const PAGE = ")[1].split(";\nconst CHOICES")[0])
    assert page["columns"] == ["kartaview_sequence", "photo"]
    assert "unpaved" not in json.dumps(page["items"])


def test_embedded_photos_are_shrunk_and_portrait_shots_turned():
    src = labelpage.embed(jpeg(900, 1600))
    import base64
    image = Image.open(io.BytesIO(base64.b64decode(src.split(",")[1])))
    assert image.width > image.height and image.width == 960


def test_link_mode_points_at_the_cdn_without_downloading():
    photos = [{"sequenceIndex": "1", "imageLthUrl": "https://cdn/1"}]
    labels = [{"kartaview_sequence": "7", "photo": "1"}]
    items, _ = labelpage.items(labels, photos_of=lambda s: photos, download=None, link=True)
    assert items[0]["src"] == "https://cdn/1"
