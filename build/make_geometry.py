#!/usr/bin/env python3
"""
One-off: builds geometry.json (simplified borough outlines, fixed map projection,
zoom bounds, label positions) from NYC's official borough boundaries dataset.

This never needs to change and geometry.json is already committed, so you
normally don't need to run this. Only re-run it if you want to change the
simplification tolerance, canvas size, or padding.

Downloads ~3MB from NYC Open Data (dataset wg9x-4ke6's sibling: gthc-hcne,
"Borough Boundaries") — not committed to the repo, regenerated on demand.
"""
import json
import math
import os
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
GEOJSON_URL = "https://data.cityofnewyork.us/resource/gthc-hcne.geojson"
RAW_PATH = os.path.join(HERE, "nyc_borough_boundaries.geojson")

CANVAS_W, CANVAS_H, PAD = 900, 900, 30
SIMPLIFY_TOL_DEG = 0.004
BOROUGH_PAD_FRAC = 0.14


def ring_area(ring):
    a = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[(i + 1) % n][0], ring[(i + 1) % n][1]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def simplify(ring, tol):
    out = [ring[0]]
    for pt in ring[1:]:
        last = out[-1]
        d2 = (pt[0] - last[0]) ** 2 + (pt[1] - last[1]) ** 2
        if d2 > tol * tol:
            out.append(pt)
    if out[-1] != ring[-1]:
        out.append(ring[-1])
    return out


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


def bounds_from_d(d_str, pad_frac=BOROUGH_PAD_FRAC):
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


def main():
    if not os.path.exists(RAW_PATH):
        print(f"Downloading {GEOJSON_URL} ...")
        urllib.request.urlretrieve(GEOJSON_URL, RAW_PATH)

    d = json.load(open(RAW_PATH))

    borough_rings = {}
    for f in d['features']:
        name = f['properties']['boroname']
        best, best_area = None, -1
        for poly in f['geometry']['coordinates']:
            outer = poly[0]
            a = ring_area(outer)
            if a > best_area:
                best_area, best = a, outer
        borough_rings[name] = best

    simplified = {name: simplify(ring, SIMPLIFY_TOL_DEG) for name, ring in borough_rings.items()}

    relevant = ['Bronx', 'Brooklyn', 'Manhattan', 'Queens']
    lons, lats = [], []
    for name in relevant:
        for lon, lat in simplified[name]:
            lons.append(lon)
            lats.append(lat)

    lat0 = (min(lats) + max(lats)) / 2
    cos_lat0 = math.cos(math.radians(lat0))

    def proj(lon, lat):
        return lon * cos_lat0, lat

    xs = [proj(lo, la)[0] for lo, la in zip(lons, lats)]
    ys = [proj(lo, la)[1] for lo, la in zip(lons, lats)]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)
    scale = min((CANVAS_W - 2 * PAD) / (max_x - min_x), (CANVAS_H - 2 * PAD) / (max_y - min_y))

    def to_svg(lon, lat):
        x, y = proj(lon, lat)
        sx = (x - min_x) * scale + PAD
        sy = CANVAS_H - ((y - min_y) * scale + PAD)
        return round(sx, 2), round(sy, 2)

    paths = {}
    for name in [*relevant, 'Staten Island']:
        pts = [to_svg(lo, la) for lo, la in simplified[name]]
        paths[name] = 'M ' + ' L '.join(f'{x},{y}' for x, y in pts) + ' Z'

    labels = {name: poly_centroid_svg(paths[name]) for name in relevant}
    bounds = {name: bounds_from_d(paths[name]) for name in relevant}

    geometry = {
        'paths': paths,
        'labels': labels,
        'bounds': bounds,
        'canvas': {'w': CANVAS_W, 'h': CANVAS_H},
        'projection': {
            'cos_lat0': cos_lat0, 'min_x': min_x, 'min_y': min_y,
            'scale': scale, 'pad': PAD, 'canvas_w': CANVAS_W, 'canvas_h': CANVAS_H,
        },
    }
    json.dump(geometry, open(os.path.join(HERE, 'geometry.json'), 'w'))
    print('geometry.json written.')


if __name__ == '__main__':
    main()
