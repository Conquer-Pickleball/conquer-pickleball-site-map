# Nightly refresh — what the scheduled job should do

Source of truth: https://dashboard-site-dusky.vercel.app/ (Conquer Youth Programs dashboard)
Output: ../pickleball-site-map.html
Living datasets:
  - schools.json — one entry per site (name, borough, address, lat, lon, status, type, note)
  - schedules.json — per site, an array of individual program-season sessions
    (season, status, date_start, date_end, days_of_week, start_time, end_time,
    raw_dates_text, raw_times_text) used to compute the "in session right now"
    indicator client-side. Keys must match schools.json `name` fields exactly.

This is a git repo. You have write access — commit and push your changes at
the end. If nothing changed, don't commit anything (no-op, no empty commit).

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
   - Also add an entry to schedules.json for it (see step 4a for the shape),
     by reading its Dates / Days-Times columns off the dashboard.

4. For any *existing* schools.json entry whose status changed on the
   dashboard (e.g. Upcoming -> Active), update its `status` field. Don't
   touch lat/lon/address on existing entries unless the dashboard shows a
   clearly different address for the same school.

   4a. Whenever a site has a new or changed program row on the dashboard
   (new season added, a Dates/Days-Times cell changed), update its entry in
   schedules.json — an array of session objects per site name:
   ```json
   {"season": "Summer '26", "status": "Upcoming", "date_start": "2026-07-07",
    "date_end": "2026-08-13", "days_of_week": ["mon","tue","thu"],
    "start_time": "13:00", "end_time": "15:00",
    "raw_dates_text": "7/6 – 8/13 (18) ...", "raw_times_text": "Mon / Tue / Thu 1-2pm & 2-3pm"}
   ```
   `days_of_week` uses lowercase 3-letter codes; times are 24-hour "HH:MM";
   leave fields null/[] when the dashboard shows TBD. Every schools.json name
   must have a key in schedules.json (an empty array is fine if there's truly
   no usable schedule, e.g. a lead still in Discussion).

5. Run `python3 build.py` from this directory to regenerate
   `../pickleball-site-map.html` from the updated schools.json + schedules.json.

6. `git add -A && git commit` with a short message describing what changed
   (e.g. "Add PS999X, mark 27Q106 active"), then `git push`. Report a
   one-line summary: how many sites added/updated, or "no changes". Only
   mention specifics if something actually changed — don't send a report,
   commit, or push for a no-op night.

Do not touch head.html, tail.html, geometry.json, or the projection math —
those are fixed; only schools.json should change from run to run.
