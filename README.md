# California Passenger Rail & Amtrak Thruway Timeline

Online page: <https://yizhouwang19.github.io/Service_modification_visualization/>

This is a static MapLibre visualization of California passenger rail service from February 2020 through August 2026, with Amtrak Thruway bus service added for the August 2026 snapshot. Its basemap uses OpenFreeMap, so the deployed site does not need a CARTO/API key.

## Map data

- `data/passenger_rail_timeline.geojson` — combined passenger-rail and Thruway route geometry and service fields.
- `data/thruway_bus_stops.geojson` — 146 supplied Thruway stops, converted from `stops.shp`.
- `data/rail_stations.geojson` — 72 supplied California rail stations filtered to `PASS_OP = Amtrak` (intercity stations only), converted from EPSG:3857 to WGS84.

## Service fields

The default map measure is weekday round trips. For August 2026 it sums route-level totals once per route: 35 passenger-rail RT plus 86 Thruway-bus RT, for a combined 121 RT with both layers enabled.

The controls also expose Thruway weekday/weekend round trips and northbound/southbound trips. Those detailed measures are currently only available for the August 2026 bus snapshot; passenger rail remains shown only for its stored weekday-round-trip measure.

Route totals drive the headline metric and route chart, preventing overlapping segments from being double-counted. Segment values drive line width, labels, and segment charts.

## Run locally

```bash
python -m http.server 8000
```

Open <http://localhost:8000>.

## Thruway geometry update
Bus map lines now use `data/thruway_routes.geojson`: 19 features from the uploaded WGS84 shapefile, with original coordinates and attributes preserved. Old bus segment geometry is no longer rendered. The existing frequency dataset remains the source for charts and totals; its segment frequencies are not assigned to the merged uploaded geometries. Bus map lines use a fixed width and route-name popups. Stops remain unchanged.

## Segment frequency alignment
`data/thruway_frequency_geometry.geojson` provides uploaded linework split by projected frequency boundaries, joined by route and segment. Existing frequency values, charts, totals, and rail data remain unchanged. Line widths, labels, and popups use the selected frequency measure. 30 of 35 frequency segments have uploaded geometry; Routes 18, 21 (two segments), 68, and incompatible Route 19 are excluded from the bus map but retained in charts/totals. Route 10b lacks a frequency record. See `data/thruway_alignment_report.json` for corridor coverage diagnostics. Boundary projection and nearest same-route corridor assignment are spatial estimates, not verified stop boundaries. Coordinates rounded to six decimals; original upload retained. Rebuild with `python scripts/align_thruway.py` (NumPy/SciPy).
