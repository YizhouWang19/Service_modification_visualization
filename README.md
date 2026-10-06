# California Passenger Rail & Amtrak Thruway Timeline

Online page: <https://yizhouwang19.github.io/Service_modification_visualization/>

This is a static MapLibre visualization of California passenger rail service from February 2020 through August 2026, with Amtrak Thruway bus service added for the August 2026 snapshot.

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
