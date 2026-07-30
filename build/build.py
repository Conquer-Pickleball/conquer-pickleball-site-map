#!/usr/bin/env python3
"""
Rebuilds pickleball-site-map.html from build/schools.json + build/geometry.json.

Run this any time schools.json changes:
    python3 build/build.py

It does NOT fetch the source dashboard or geocode anything itself — that step
(checking the dashboard for new/changed sites, geocoding new addresses, and
updating schools.json) is meant to be done by a Claude agent run (see
build/REFRESH.md), because it requires reading and judgment, not just a fixed
transform. This script is the deterministic last mile: schools.json -> the
published HTML.
"""
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECT = os.path.dirname(HERE)


def project_schools(schools, projection):
    cos_lat0 = projection['cos_lat0']
    min_x, min_y = projection['min_x'], projection['min_y']
    scale = projection['scale']
    pad = projection['pad']
    canvas_h = projection['canvas_h']

    def to_svg(lon, lat):
        x = lon * cos_lat0
        y = lat
        sx = (x - min_x) * scale + pad
        sy = canvas_h - ((y - min_y) * scale + pad)
        return round(sx, 2), round(sy, 2)

    for s in schools:
        s['x'], s['y'] = to_svg(s['lon'], s['lat'])

    # nudge exact-duplicate coordinates apart so co-located sites don't overlap
    from collections import defaultdict
    groups = defaultdict(list)
    for i, s in enumerate(schools):
        groups[(s['x'], s['y'])].append(i)
    for (x, y), idxs in groups.items():
        n = len(idxs)
        if n < 2:
            continue
        r = 9
        for k, i in enumerate(idxs):
            angle = (2 * math.pi / n) * k - math.pi / 2
            schools[i]['x'] = round(x + r * math.cos(angle), 2)
            schools[i]['y'] = round(y + r * math.sin(angle), 2)

    return schools


PUBLIC_FIELDS = ('name', 'borough', 'district', 'grades', 'x', 'y')


def to_public(schools):
    # Donor-facing site: no exact street addresses, no internal contract/
    # financial/contact notes, no program status. Only what's safe to show
    # publicly. `programs` is only present on the rare co-located site that
    # merges two program names into one pin, so it's added conditionally
    # rather than living in PUBLIC_FIELDS.
    out = []
    for s in schools:
        rec = {k: s.get(k) for k in PUBLIC_FIELDS}
        if s.get('programs'):
            rec['programs'] = s['programs']
        out.append(rec)
    return out


def main():
    schools = json.load(open(os.path.join(HERE, 'schools.json')))
    geometry = json.load(open(os.path.join(HERE, 'geometry.json')))

    schools = project_schools(schools, geometry['projection'])

    used_districts = sorted(set(s['district'] for s in schools), key=lambda x: (len(x), x))
    # District 75 (citywide special education) has no real geographic
    # polygon in the NYC "School Districts" dataset — it's filterable but
    # has no boundary to draw or zoom to.
    geo_districts = [d for d in used_districts if d in geometry['district_paths']]

    schools = to_public(schools)

    map_data = {
        'paths': geometry['paths'],
        'labels': geometry['labels'],
        'bounds': geometry['bounds'],
        'canvas': geometry['canvas'],
        'schools': schools,
        'districts': {
            'paths': {d: geometry['district_paths'][d] for d in geo_districts},
            'labels': {d: geometry['district_labels'][d] for d in geo_districts},
            'bounds': {d: geometry['district_bounds'][d] for d in geo_districts},
            'borough': {d: geometry['district_borough'][d] for d in geo_districts},
        },
        'allDistricts': used_districts,
    }

    head = open(os.path.join(HERE, 'head.html')).read()
    tail = open(os.path.join(HERE, 'tail.html')).read()
    map_data_json = json.dumps(map_data, indent=1)

    out_path = os.path.join(PROJECT, 'pickleball-site-map.html')
    with open(out_path, 'w') as f:
        f.write(head)
        f.write(map_data_json)
        f.write(tail)

    print(f'Wrote {out_path} ({len(schools)} sites)')


if __name__ == '__main__':
    main()
