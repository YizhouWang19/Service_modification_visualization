#!/usr/bin/env python3
"""Build browser-ready service and stop GeoJSON from the supplied research files.

This script deliberately uses only the Python standard library plus openpyxl, which is
already used to read the source workbook.  It converts the point shapefile directly
because the uploaded layer is a simple WGS84 Point shapefile.
"""

from __future__ import annotations

import argparse
import json
import math
import re
import struct
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from openpyxl import load_workbook


METRIC_COLUMNS = {
    "weekday_roundtrip": "weekday roundtrip",
    "weekend_roundtrip": "weekend roundtrip",
    "weekday_northbound": "weekday trip (North)",
    "weekday_southbound": "weekday trip (South)",
    "weekend_northbound": "weekend trip (North)",
    "weekend_southbound": "weekend trip (South)",
}

SEGMENT_METRIC_COLUMNS = {
    "weekday_roundtrip": "weekday roundtrip",
    "weekend_roundtrip": "weekend roundtrip",
    "weekday_northbound": "weekday trip (North to South)",
    "weekday_southbound": "weekday trip (South to North)",
    "weekend_northbound": "weekend trip  (North to South)",
    "weekend_southbound": "weekend trip (South to North)",
}


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def as_number(value: Any) -> int | float | None:
    if value is None or value == "":
        return None
    number = float(value)
    return int(number) if number.is_integer() else number


def canonical_route(value: Any) -> str:
    text = str(value).strip()
    text = re.sub(r"^route\s+", "", text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", text).casefold()


def display_route(value: Any) -> str:
    text = str(value).strip()
    if text.casefold() == "point southwest":
        return "POINT Southwest"
    return f"Route {text.upper()}"


def canonical_segment(value: Any) -> str:
    text = str(value).casefold().replace("–", "-").replace("—", "-").replace("↔", "-")
    text = re.sub(r"\s+", "", text)
    return text


def canonical_id(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip().casefold()


def workbook_rows(path: Path, sheet_name: str) -> list[dict[str, Any]]:
    workbook = load_workbook(path, read_only=True, data_only=True)
    sheet = workbook[sheet_name]
    rows = sheet.iter_rows(values_only=True)
    headers = [str(value).strip() if value is not None else "" for value in next(rows)]
    records: list[dict[str, Any]] = []
    for row in rows:
        if not row or not isinstance(row[0], datetime):
            continue
        records.append(dict(zip(headers, row)))
    return records


def service_metrics(record: dict[str, Any], columns: dict[str, str]) -> dict[str, int | float | None]:
    return {key: as_number(record.get(column)) for key, column in columns.items()}


def read_dbf(path: Path) -> list[dict[str, str]]:
    """Read the character fields in the supplied dBase III table."""
    data = path.read_bytes()
    record_count = struct.unpack_from("<I", data, 4)[0]
    header_length = struct.unpack_from("<H", data, 8)[0]
    record_length = struct.unpack_from("<H", data, 10)[0]
    fields: list[tuple[str, str, int, int]] = []
    offset = 32
    while offset < header_length and data[offset] != 0x0D:
        descriptor = data[offset : offset + 32]
        name = descriptor[:11].split(b"\0", 1)[0].decode("latin1")
        fields.append((name, chr(descriptor[11]), descriptor[16], descriptor[17]))
        offset += 32

    records: list[dict[str, str]] = []
    for index in range(record_count):
        row = data[header_length + index * record_length : header_length + (index + 1) * record_length]
        if not row or row[0:1] == b"*":
            continue
        position = 1
        record: dict[str, str] = {}
        for name, _field_type, length, _decimals in fields:
            record[name] = row[position : position + length].decode("latin1").strip()
            position += length
        records.append(record)
    return records


def read_point_shapefile(path: Path) -> list[tuple[float, float]]:
    """Read a standard Point (type 1) shapefile in WGS84 coordinate order."""
    data = path.read_bytes()
    shape_type = struct.unpack_from("<i", data, 32)[0]
    if shape_type != 1:
        raise ValueError(f"Expected Point shapefile type 1, found {shape_type}")
    points: list[tuple[float, float]] = []
    offset = 100
    while offset < len(data):
        _record_number, length_words = struct.unpack_from(">2i", data, offset)
        content_length = length_words * 2
        body = data[offset + 8 : offset + 8 + content_length]
        record_type = struct.unpack_from("<i", body, 0)[0]
        if record_type == 0:
            points.append((float("nan"), float("nan")))
        elif record_type == 1:
            points.append(struct.unpack_from("<2d", body, 4))
        else:
            raise ValueError(f"Expected Point record type 1, found {record_type}")
        offset += 8 + content_length
    return points


def web_mercator_to_wgs84(point: tuple[float, float]) -> list[float]:
    """Convert the supplied EPSG:3857 rail-station coordinates to EPSG:4326."""
    x, y = point
    radius = 6378137.0
    longitude = math.degrees(x / radius)
    latitude = math.degrees(2 * math.atan(math.exp(y / radius)) - math.pi / 2)
    return [round(longitude, 7), round(latitude, 7)]


def first_coordinate(geometry: dict[str, Any]) -> list[float]:
    coordinates = geometry["coordinates"]
    while coordinates and isinstance(coordinates[0], list) and coordinates and isinstance(coordinates[0][0], list):
        coordinates = coordinates[0]
    return coordinates[0]


def last_coordinate(geometry: dict[str, Any]) -> list[float]:
    coordinates = geometry["coordinates"]
    while coordinates and isinstance(coordinates[-1], list) and coordinates and isinstance(coordinates[-1][0], list):
        coordinates = coordinates[-1]
    return coordinates[-1]


def segment_station_names(segment: str) -> tuple[str, str] | None:
    cleaned = re.sub(r"\s*[–—↔]\s*", "-", segment)
    parts = [part.strip() for part in cleaned.split("-") if part.strip()]
    if len(parts) != 2:
        return None
    return parts[0], parts[1]


def average_coordinates(points: Iterable[list[float]]) -> list[float]:
    materialized = list(points)
    return [
        round(sum(point[0] for point in materialized) / len(materialized), 7),
        round(sum(point[1] for point in materialized) / len(materialized), 7),
    ]


def build(args: argparse.Namespace) -> None:
    source = args.source_dir
    output = args.output_dir
    rail = read_json(source / "passenger_rail_timeline(1).geojson")
    bus = read_json(source / "thruway_osm_routes(1).geojson")
    route_records = workbook_rows(source / "Amtrak_CA_Route_Frequencies_2020-2026_Long_Table(5).xlsx", "route frequency")
    segment_records = workbook_rows(source / "Amtrak_CA_Route_Frequencies_2020-2026_Long_Table(5).xlsx", "segment frequency")

    route_by_id = {canonical_route(record["route"]): record for record in route_records}
    segment_by_key = {
        (canonical_route(record["route"]), canonical_segment(record["segment (North to South)"])): record
        for record in segment_records
    }

    for feature in rail["features"]:
        properties = feature["properties"]
        properties["mode"] = "passenger_rail"
        properties["service_key"] = f"rail:{properties['route']}"
        properties["weekday_roundtrip"] = as_number(properties.get("roundtrip"))
        properties["route_total_weekday_roundtrip"] = as_number(properties.get("route_total_rt"))
        properties["metrics_available"] = "weekday_roundtrip"

    bus_features: list[dict[str, Any]] = []
    for source_feature in bus["features"]:
        feature = {"type": "Feature", "geometry": source_feature["geometry"], "properties": dict(source_feature["properties"])}
        properties = feature["properties"]
        route_id = canonical_route(properties["route"])
        route_record = route_by_id.get(route_id)
        segment_record = segment_by_key.get((route_id, canonical_segment(properties["segment"])))
        if route_record is None:
            raise KeyError(f"No route-level frequency row for Thruway route {properties['route']!r}")
        segment_metrics = service_metrics(segment_record, SEGMENT_METRIC_COLUMNS) if segment_record else service_metrics(route_record, METRIC_COLUMNS)
        route_metrics = service_metrics(route_record, METRIC_COLUMNS)
        route_label = display_route(properties["route"])
        properties.update(segment_metrics)
        properties.update({f"route_total_{key}": value for key, value in route_metrics.items()})
        properties.update(
            {
                "date": "2026-08-01",
                "mode": "thruway_bus",
                "route": route_label,
                "route_id": str(source_feature["properties"]["route"]),
                "service_key": f"bus:{route_id}",
                "roundtrip": segment_metrics["weekday_roundtrip"],
                "route_total_rt": route_metrics["weekday_roundtrip"],
                "metrics_available": ",".join(METRIC_COLUMNS),
                "frequency_match": "segment" if segment_record else "route summary",
                "frequency_note": (
                    "Segment geometry matched the frequency workbook."
                    if segment_record
                    else "This map geometry spans multiple scheduled subsegments; route-level frequency is used."
                ),
                "operator": "Amtrak Thruway Bus",
                "source": "OpenStreetMap via OSRM; service frequency from Amtrak_CA_Route_Frequencies_2020-2026_Long_Table.xlsx",
            }
        )
        bus_features.append(feature)

    rail["name"] = "California passenger rail and Amtrak Thruway service timeline"
    rail["metadata"] = {
        **rail.get("metadata", {}),
        "bus_data_availability": "2026-08-01 only",
        "modes": ["passenger_rail", "thruway_bus"],
        "metric_fields": list(METRIC_COLUMNS),
        "station_layers": ["rail_stations.geojson", "thruway_bus_stops.geojson"],
    }
    rail["features"].extend(bus_features)
    write_json(output / "passenger_rail_timeline.geojson", rail)

    dbf_records = read_dbf(source / "stops.dbf")
    stop_points = read_point_shapefile(source / "stops.shp")
    if len(dbf_records) != len(stop_points):
        raise ValueError(f"Stop records ({len(dbf_records)}) do not match point count ({len(stop_points)})")
    stop_features = []
    for record, point in zip(dbf_records, stop_points):
        if any(value != value for value in point):
            continue
        stop_features.append(
            {
                "type": "Feature",
                "geometry": {"type": "Point", "coordinates": list(point)},
                "properties": {**record, "mode": "thruway_stop", "source": "Uploaded stops.shp"},
            }
        )
    write_json(
        output / "thruway_bus_stops.geojson",
        {
            "type": "FeatureCollection",
            "name": "Amtrak Thruway bus stops",
            "metadata": {"source": "Uploaded stops.shp", "crs": "EPSG:4326"},
            "features": stop_features,
        },
    )

    rail_station_records = read_dbf(source / "California_Rail_Stations(1).dbf")
    rail_station_points = read_point_shapefile(source / "California_Rail_Stations(1).shp")
    if len(rail_station_records) != len(rail_station_points):
        raise ValueError(
            f"Rail-station records ({len(rail_station_records)}) do not match point count ({len(rail_station_points)})"
        )
    station_features = [
        {
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": web_mercator_to_wgs84(point)},
            "properties": {
                "station_name": record["STATION"].title(),
                "code": record["CODE"],
                "routes": record["PASS_NETWO"],
                "location": record["LOCATION"],
                "address": record["ADDRESS"],
                "mode": "intercity_rail_station",
                "source": "California_Rail_Stations.shp; PASS_OP = Amtrak",
            },
        }
        for record, point in zip(rail_station_records, rail_station_points)
        if record["PASS_OP"].casefold() == "amtrak"
    ]
    write_json(
        output / "rail_stations.geojson",
        {
            "type": "FeatureCollection",
            "name": "California intercity rail stations",
            "metadata": {
                "source": "California_Rail_Stations(1).shp",
                "source_crs": "EPSG:3857",
                "output_crs": "EPSG:4326",
                "filter": "PASS_OP = Amtrak",
            },
            "features": station_features,
        },
    )

    print(
        json.dumps(
            {
                "combined_features": len(rail["features"]),
                "bus_features": len(bus_features),
                "bus_stops": len(stop_features),
                "intercity_rail_stations": len(station_features),
                "bus_weekday_route_total": sum(
                    int(record["weekday roundtrip"] or 0) for record in route_records
                ),
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-dir", type=Path, default=Path("upload"))
    parser.add_argument("--output-dir", type=Path, default=Path("staging/data"))
    build(parser.parse_args())
