# Nightly refresh — what the scheduled job should do

Source of truth: https://dashboard-site-dusky.vercel.app/ (Conquer Youth Programs dashboard)
Output: ../pickleball-site-map.html
Living dataset: schools.json (one entry per site, with lat/lon already geocoded)

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
   - Append a new object to schools.json with the same shape as existing
     entries: name, borough, address, lat, lon, status, type, note.

4. For any *existing* schools.json entry whose status changed on the
   dashboard (e.g. Upcoming -> Active), update its `status` field. Don't
   touch lat/lon/address on existing entries unless the dashboard shows a
   clearly different address for the same school.

5. Run `python3 build.py` from this directory to regenerate
   `../pickleball-site-map.html` from the updated schools.json.

6. Report a one-line summary: how many sites added/updated, or "no changes".
   Only mention specifics if something actually changed — don't send a
   report for a no-op night.

Do not touch head.html, tail.html, geometry.json, or the projection math —
those are fixed; only schools.json should change from run to run.
