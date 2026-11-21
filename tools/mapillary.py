"""Read public Mapillary photos, to cover regions and dirt roads KartaView lacks.

Needs a free client token from a Mapillary account in MAPILLARY_ACCESS_TOKEN. Mapillary imagery is CC BY-SA 4.0.
Keep downloaded photos out of the repo. Photo download links expire, so label files keep the image id and the link is
looked up again at download time.
"""
import json
import os
import urllib.parse
from datetime import datetime, timezone

from tools.kartaview import get

API = "https://graph.mapillary.com"
FIELDS = "id,captured_at,geometry,compass_angle,camera_type,width,height,creator"


def token():
    value = os.environ.get("MAPILLARY_ACCESS_TOKEN") or os.environ.get("MAPILLARY_TOKEN")
    if not value:
        raise ValueError("set MAPILLARY_ACCESS_TOKEN to a Mapillary client token (free account, mapillary.com/dashboard/developers)")
    return value


def graph(path, **params):
    query = urllib.parse.urlencode({**params, "access_token": token()})
    body = json.loads(get(f"{API}/{path}?{query}"))
    if "error" in body:
        raise ValueError(f"Mapillary: {body['error'].get('message', body['error'])}")
    return body


def photo(image):
    """One Mapillary image in the shape the KartaView tools use (lat, lng, shotDate), keyed by its image id."""
    lng, lat = image["geometry"]["coordinates"]
    shot = datetime.fromtimestamp(image["captured_at"] / 1000, timezone.utc)
    return {
        "id": image["id"],
        "lat": f"{lat:.6f}",
        "lng": f"{lng:.6f}",
        "shotDate": shot.strftime("%Y-%m-%d %H:%M:%S"),
        "heading": image.get("compass_angle", ""),
        "camera_type": image.get("camera_type", ""),
        "creator": (image.get("creator") or {}).get("username", ""),
    }


def list_photos(sequence_id):
    images = graph("images", sequence_ids=sequence_id, fields=FIELDS, limit=2000)["data"]
    return [photo(i) for i in sorted(images, key=lambda i: (i["captured_at"], i["id"]))]


def photo_url(image_id, size=1024):
    return graph(str(image_id), fields=f"thumb_{size}_url")[f"thumb_{size}_url"]
