#!/usr/bin/env python3
"""
One-off: adds real NYC community school district geometry to geometry.json
(district_paths, district_labels, district_bounds, district_borough) using
NYC Open Data's "School Districts" dataset (8ugf-3d8u), projected with the
SAME fixed projection already stored in geometry.json so everything lines
up with the existing borough shapes and school pins.

Uses shapely for robust polygon ops (multipolygon union, representative
point, containment) instead of hand-rolled ray casting.

Re-run this only if you want to change simplification tolerance etc. The
raw geojson files are not committed (regenerate on demand, like the
borough boundaries).
"""
import json
import os
import urllib.request

from shapely.geometry import shape
from shapely.ops import unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
DISTRICTS_URL = "https://data.cityofnewyork.us/resource/8ugf-3d8u.geojson?$limit=50"
BOROUGHS_URL = "https://data.cityofnewyork.us/resource/gthc-hcne.geojson"
DISTRICTS_RAW = os.path.join(HERE, "nyc_school_districts.geojson")
BOROUGHS_RAW = os.path.join(HERE, "nyc_borough_boundaries.geojson")

SIMPLIFY_TOL_DEG = 0.0015
DISTRICT_PAD_FRAC = 0.18


def largest_polygon(geom):
    """geom may be Polygon or MultiPolygon; return the largest-area Polygon."""
    if geom.geom_type == 'Polygon':
        return geom
    return max(geom.geoms, key=lambda g: g.area)


def poly_centroid_svg(d_str):
    body = d_str[2:-2]
    pts = [tuple(map(float, p.split(','))) for p in body.split(' L ')]
    A = Cx = Cy = 0.0
    n = len(pts)
    for i in range(n):
        x0, y0 = pts[i]
        x1, y1 = pts[(i + 1) % n]
        cross = x0 * y1 - x1 * y0
        A += cross
        Cx += (x0 + x1) * cross
        Cy += (y0 + y1) * cross
    A *= 0.5
    return round(Cx / (6 * A), 1), round(Cy / (6 * A), 1)


def bounds_from_d(d_str, pad_frac):
    body = d_str[2:-2]
    pts = [tuple(map(float, p.split(','))) for p in body.split(' L ')]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    minx, maxx = min(xs), max(xs)
    miny, maxy = min(ys), max(ys)
    w, h = maxx - minx, maxy - miny
    padx, pady = w * pad_frac, h * pad_frac
    minx, maxx, miny, maxy = minx - padx, maxx + padx, miny - pady, maxy + pady
    w, h = maxx - minx, maxy - miny
    if w > h:
        diff = (w - h) / 2
        miny -= diff
        maxy += diff
    else:
        diff = (h - w) / 2
        minx -= diff
        maxx += diff
    return [round(minx, 1), round(miny, 1), round(maxx - minx, 1), round(maxy - miny, 1)]


def ring_of(polygon):
    return list(polygon.exterior.coords)


def main():
    if not os.path.exists(DISTRICTS_RAW):
        print(f"Downloading {DISTRICTS_URL} ...")
        urllib.request.urlretrieve(DISTRICTS_URL, DISTRICTS_RAW)
    if not os.path.exists(BOROUGHS_RAW):
        print(f"Downloading {BOROUGHS_URL} ...")
        urllib.request.urlretrieve(BOROUGHS_URL, BOROUGHS_RAW)

    geometry = json.load(open(os.path.join(HERE, 'geometry.json')))
    proj = geometry['projection']
    cos_lat0, min_x, min_y = proj['cos_lat0'], proj['min_x'], proj['min_y']
    scale, pad, canvas_h = proj['scale'], proj['pad'], proj['canvas_h']

    def to_svg(lon, lat):
        x = lon * cos_lat0
        y = lat
        sx = (x - min_x) * scale + pad
        sy = canvas_h - ((y - min_y) * scale + pad)
        return round(sx, 2), round(sy, 2)

    bdata = json.load(open(BOROUGHS_RAW))
    borough_polys = {}
    for f in bdata['features']:
        geom = shape(f['geometry'])
        borough_polys[f['properties']['boroname']] = largest_polygon(geom)

    ddata = json.load(open(DISTRICTS_RAW))

    district_rings_simplified = {}
    district_paths = {}
    district_labels = {}
    district_bounds = {}
    district_borough = {}

    for f in ddata['features']:
        num = f['properties']['schooldist']
        geom = shape(f['geometry'])
        poly = largest_polygon(geom)
        simplified = poly.simplify(SIMPLIFY_TOL_DEG, preserve_topology=True)
        if simplified.geom_type != 'Polygon':
            simplified = largest_polygon(simplified)

        ring = ring_of(simplified)
        district_rings_simplified[num] = [[round(x, 6), round(y, 6)] for x, y in ring]

        pts = [to_svg(lo, la) for lo, la in ring]
        d_str = 'M ' + ' L '.join(f'{x},{y}' for x, y in pts) + ' Z'
        district_paths[num] = d_str
        district_labels[num] = poly_centroid_svg(d_str)
        district_bounds[num] = bounds_from_d(d_str, DISTRICT_PAD_FRAC)

        rep_point = poly.representative_point()
        parent = None
        for bname, bpoly in borough_polys.items():
            if bpoly.contains(rep_point):
                parent = bname
                break
        if parent is None:
            # fall back to nearest borough polygon (handles coastline/simplification gaps)
            parent = min(borough_polys.items(), key=lambda kv: kv[1].distance(rep_point))[0]
        district_borough[num] = parent

    geometry['district_rings'] = district_rings_simplified  # lon/lat, for point-in-polygon at build time
    geometry['district_paths'] = district_paths
    geometry['district_labels'] = district_labels
    geometry['district_bounds'] = district_bounds
    geometry['district_borough'] = district_borough

    json.dump(geometry, open(os.path.join(HERE, 'geometry.json'), 'w'))
    print(f'Added {len(district_paths)} districts to geometry.json')
    from collections import Counter
    print(Counter(district_borough.values()))


if __name__ == '__main__':
    main()
