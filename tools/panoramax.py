"""Read public Panoramax photos (api.panoramax.xyz, the federated instance search), for regions Mapillary and KartaView lack.

No token is needed. A Panoramax sequence is a STAC collection and a photo is an item, both keyed by UUID; photo links
are stable, so label files keep the item id. Panoramax imagery here is CC BY-SA 4.0 (check each item's license link).
"""
import json

from tools.kartaview import get

API = "https://api.panoramax.xyz/api"


def read(url):
    return json.loads(get(url))


def photo(item):
    """One Panoramax item in the shape the KartaView tools use (lat, lng, shotDate), keyed by its item id."""
    lng, lat = item["geometry"]["coordinates"]
    props = item["properties"]
    return {
        "id": item["id"],
        "lat": f"{lat:.6f}",
        "lng": f"{lng:.6f}",
        "shotDate": props.get("datetime", "")[:19].replace("T", " "),
        "heading": props.get("view:azimuth", ""),
        "creator": props.get("geovisio:producer", ""),
        "rank": props.get("geovisio:rank_in_collection", 0),
    }


def list_photos(collection_id):
    url, photos = f"{API}/collections/{collection_id}/items?limit=500", []
    while url:
        page = read(url)
        photos += [photo(f) for f in page["features"]]
        url = next((link["href"] for link in page.get("links", []) if link.get("rel") == "next"), None)
    return sorted(photos, key=lambda p: (p["shotDate"], p["rank"], p["id"]))


def photo_url(item_id, size="sd"):
    """`sd` is 2048 px wide, `thumb` 500 px, `hd` the original."""
    return f"{API}/pictures/{item_id}/{size}.jpg"
