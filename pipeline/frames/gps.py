import bisect
import math
from dataclasses import dataclass
from datetime import datetime, timezone

import gpxpy


@dataclass(frozen=True)
class TrackPoint:
    time: datetime
    lat: float
    lon: float


@dataclass(frozen=True)
class Position:
    lat: float
    lon: float
    heading: float | None


def load_track(gpx_path):
    with open(gpx_path, encoding="utf-8") as f:
        gpx = gpxpy.parse(f)
    points = [
        TrackPoint(_as_utc(p.time), p.latitude, p.longitude)
        for track in gpx.tracks
        for segment in track.segments
        for p in segment.points
        if p.time is not None
    ]
    if len(points) < 2:
        raise ValueError(f"{gpx_path}: need at least 2 timed track points, found {len(points)}")
    return sorted(points, key=lambda p: p.time)


def bearing(lat1, lon1, lat2, lon2):
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dlon = math.radians(lon2 - lon1)
    x = math.sin(dlon) * math.cos(phi2)
    y = math.cos(phi1) * math.sin(phi2) - math.sin(phi1) * math.cos(phi2) * math.cos(dlon)
    return math.degrees(math.atan2(x, y)) % 360


def position_at(track, t):
    """Linear interpolation between the two track points around t; None outside the track."""
    t = _as_utc(t)
    if t < track[0].time or t > track[-1].time:
        return None
    times = [p.time for p in track]
    i = max(1, bisect.bisect_left(times, t))
    a, b = track[i - 1], track[i]
    span = (b.time - a.time).total_seconds()
    f = (t - a.time).total_seconds() / span if span else 0.0
    moved = (a.lat, a.lon) != (b.lat, b.lon)
    return Position(
        lat=a.lat + f * (b.lat - a.lat),
        lon=a.lon + f * (b.lon - a.lon),
        heading=bearing(a.lat, a.lon, b.lat, b.lon) if moved else None,
    )


def _as_utc(t):
    if t.tzinfo is None:
        return t.replace(tzinfo=timezone.utc)
    return t.astimezone(timezone.utc)
