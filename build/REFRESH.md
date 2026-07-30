# Nightly refresh — what the scheduled job should do

Source of truth: https://dashboard-site-dusky.vercel.app/ (Conquer Youth Programs dashboard)
Output: ../pickleball-site-map.html
Living dataset: schools.json — one entry per site (name, borough, address, lat,
lon, status, type, note, grades, district, and optionally programs — see
"Naming and district convention" below). `status` is still recorded for
internal bookkeeping but is **not shown** on the donor-facing site — don't
worry about getting Active/Upcoming/Finished perfectly right, just keep it
roughly current.

`schedules.json` still exists on disk but is no longer read by build.py (the
"live in session now" feature it powered was removed) — ignore it, don't
update it, and feel free to delete it if it's ever in the way.

This is a git repo. You have write access — commit and push your changes at
the end. If nothing changed, don't commit anything (no-op, no empty commit).

## Naming and district convention

Every school's `name` field must match the naming pattern used in Conquer's
Google Drive folders for that site, which `build.py` (via PUBLIC_FIELDS)
publishes as-is:

- **DOE-coded sites** (has a building code like `PS30X`, `IS61Q`, `MS366K`):
  `"<CODE> - <Name> - District <N>"`, e.g. `"PS9X - Ryer Avenue - District 10"`.
  Match the Drive folder name for the school if you can find it; otherwise use
  the DOE's own `location_name` from the Open Data lookup below.
- **Everything else** (private school, YMCA, community center, CBO site with
  no DOE code): `"<Name> - <Borough>"`, e.g. `"Horace Mann - Bronx"`.

Every entry also needs a `district` field (a string, e.g. `"9"`) — the NYC
community school district the site's lat/lon falls inside. Compute it with
shapely point-in-polygon against `nyc_school_districts.geojson` (same file
`add_districts.py` uses) rather than guessing from the DBN, since CBOs/private
schools have no DBN district digit and even DOE schools can sit just outside
their own numbered district's boundary. The one standing exception is
District 75 (citywide special education) — it has no real polygon, so a
75-coded site (e.g. `75X012`) keeps `"district": "75"` as a hardcoded value
and its name keeps the literal "District 75" suffix rather than whatever
geographic district it happens to sit in.

Each run:

1. Fetch the dashboard HTML (`curl`) and strip it to plain text the same way as
   the original build (strip <script>/<style>, strip tags, unescape entities).
   The season tables and the "Contacts" section near the bottom both list
   school names, boroughs, and often street addresses — read both.

2. Extract the current full list of site names + boroughs + statuses (Active /
   Upcoming / Finished / Completed / Pending / Discussion) and compare against
   the `name` field of every entry in schools.json.

3. For any name that's genuinely new (not just a reformatted/renamed existing
   entry — check addresses to avoid double-adding a school that got renamed):
   - Find its street address in the dashboard text (season table row or the
     Contacts directory).
   - Geocode it:
     - If it has an NYC DOE-style code (e.g. "24Q093"), query
       `https://data.cityofnewyork.us/resource/wg9x-4ke6.json` filtered by
       `system_code` for the exact lat/lon (see git history / prior session
       for the exact curl pattern).
     - Otherwise (private school, community center, CBO), geocode the street
       address with Nominatim (`https://nominatim.openstreetmap.org/search`,
       one request/second, set a real User-Agent).
   - Name the entry per the "Naming and district convention" section above,
     and compute its `district` field the same way.
   - Append a new object to schools.json with the same shape as existing
     entries: name, borough, address, lat, lon, status, type, note, grades,
     district.

4. For any *existing* schools.json entry whose status changed on the
   dashboard (e.g. Upcoming -> Active), update its `status` field (recorded
   but not publicly displayed, see above). Don't touch lat/lon/address/name
   on existing entries unless the dashboard shows a clearly different address
   for the same school — if a school's Drive folder name changed, that's a
   deliberate rename to flag in the summary, not something to silently apply.

5. Run `python3 build.py` from this directory to regenerate
   `../pickleball-site-map.html` from the updated schools.json.

6. `git add -A && git commit` with a short message describing what changed
   (e.g. "Add PS999X, mark 27Q106 active"), then `git push`. Report a
   one-line summary: how many sites added/updated, or "no changes". Only
   mention specifics if something actually changed — don't send a report,
   commit, or push for a no-op night.

Do not touch head.html, tail.html, geometry.json, or the projection math —
those are fixed; only schools.json should change from run to run.
