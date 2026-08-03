# California Passenger Rail Timeline 
Online Page: https://yizhouwang19.github.io/Service_modification_visualization/


Run Localy:

Files:
- `index.html`
- `data/passenger_rail_timeline.geojson`

Changes:
- Segment line widths and labels continue to use `roundtrip`.
- The headline total now sums one `route_total_rt` value per route, preventing overlapping segment double-counting.
- Route-mode trend charts use `route_total_rt`.
- Segment-mode trend charts use `roundtrip`.
- Popups show both segment RT and route-total RT.

Run locally:

```bash
cd rail_timeline_updated
python -m http.server 8000
```

Then open `http://localhost:8000`.

The California mask is optional. To restore it, place `ca_state.geojson` in the `data` folder.
