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


def main():
    schools = json.load(open(os.path.join(HERE, 'schools.json')))
    geometry = json.load(open(os.path.join(HERE, 'geometry.json')))
    schedules_path = os.path.join(HERE, 'schedules.json')
    schedules = json.load(open(schedules_path)) if os.path.exists(schedules_path) else {}

    schools = project_schools(schools, geometry['projection'])
    for s in schools:
        s['sessions'] = schedules.get(s['name'], [])

    map_data = {
        'paths': geometry['paths'],
        'labels': geometry['labels'],
        'bounds': geometry['bounds'],
        'canvas': geometry['canvas'],
        'schools': schools,
    }

    head = open(os.path.join(HERE, 'head.html')).read()
    tail = open(os.path.join(HERE, 'tail.html')).read()
    map_data_json = json.dumps(map_data, separators=(',', ':'))

    out_path = os.path.join(PROJECT, 'pickleball-site-map.html')
    with open(out_path, 'w') as f:
        f.write(head)
        f.write(map_data_json)
        f.write(tail)

    print(f'Wrote {out_path} ({len(schools)} sites)')


if __name__ == '__main__':
    main()
