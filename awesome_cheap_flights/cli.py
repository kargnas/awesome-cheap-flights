from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

import yaml

from .pipeline import (
    FilterSettings,
    LegDeparture,
    LegFilter,
    PlanConfig,
    PlanOptions,
    PlanOutput,
    RequestSettings,
    SearchConfig,
    OutputSettings,
    execute_search,
)

DEFAULT_CONFIG_FILE = Path("config.yaml")
CONFIG_ENV_VAR = "AWESOME_CHEAP_FLIGHTS_CONFIG"
DATE_FMT = "%Y-%m-%d"
COMMENT_MARKERS = ("#",)

DEFAULT_CURRENCY = "USD"
DEFAULT_PASSENGERS = 1
DEFAULT_REQUEST_DELAY = 1.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_LEG_RESULTS = 10
DEFAULT_MAX_STOPS: int | None = None
DEFAULT_INCLUDE_HIDDEN = True
DEFAULT_MAX_HIDDEN_HOPS = 1
DEFAULT_OUTPUT_DIR = Path("output")
DEFAULT_FILENAME_PATTERN = "{plan}_{timestamp}.csv"
DEFAULT_DEBUG = False
DEFAULT_CONCURRENCY = 1


def strip_comment(value: Any) -> str:
    result = str(value) if value is not None else ""
    for marker in COMMENT_MARKERS:
        if marker in result:
            result = result.split(marker, 1)[0]
    return result.strip()


def load_yaml_config(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    with path.open("r", encoding="utf-8") as stream:
        data = yaml.safe_load(stream) or {}
    if not isinstance(data, dict):
        raise ValueError("YAML root must be a mapping")
    return data


def _unique_preserve(values: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for value in values:
        token = value.strip().upper()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


def _parse_date_token(value: Any) -> str:
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.strftime(DATE_FMT)
    token = strip_comment(value)
    if not token:
        raise ValueError("Empty date value")
    try:
        datetime.strptime(token, DATE_FMT)
    except ValueError as exc:
        raise ValueError(f"Invalid date format: {token}") from exc
    return token


def _expand_date_selector(field: Any) -> List[str]:
    if field is None:
        return []
    if isinstance(field, (str, date)):
        return [_parse_date_token(field)]
    if isinstance(field, (list, tuple)):
        items: List[str] = []
        for item in field:
            items.extend(_expand_date_selector(item))
        return _unique_preserve(items)
    if isinstance(field, dict):
        if "dates" in field:
            return _unique_preserve(_parse_date_token(item) for item in field["dates"])
        if "window" in field:
            window = field["window"]
        else:
            window = field
        start_raw = window.get("start")
        end_raw = window.get("end", start_raw)
        start_token = _parse_date_token(start_raw)
        end_token = _parse_date_token(end_raw)
        start_date = datetime.strptime(start_token, DATE_FMT).date()
        end_date = datetime.strptime(end_token, DATE_FMT).date()
        if end_date < start_date:
            raise ValueError("Date range end must be on or after start")
        current = start_date
        results: List[str] = []
        while current <= end_date:
            results.append(current.strftime(DATE_FMT))
            current += timedelta(days=1)
        return results
    raise ValueError(f"Unsupported date selector: {field!r}")


def _parse_leg_key(raw_key: str) -> tuple[str, str]:
    parts = strip_comment(raw_key).split("->", 1)
    if len(parts) != 2:
        raise ValueError(f"Leg key must use 'from->to' format: {raw_key!r}")
    origin = parts[0].strip()
    destination = parts[1].strip()
    if not origin or not destination:
        raise ValueError(f"Invalid leg key: {raw_key!r}")
    return origin, destination


def _parse_place_codes(raw: Any) -> List[str]:
    if isinstance(raw, str):
        tokens = [strip_comment(token) for token in raw.split(",")]
        return _unique_preserve(tokens)
    if isinstance(raw, (list, tuple)):
        collected: List[str] = []
        for item in raw:
            collected.extend(_parse_place_codes(item))
        return _unique_preserve(collected)
    raise ValueError(f"Place codes must be string or list of strings (found {raw!r})")


def parse_places(raw: Any) -> Dict[str, List[str]]:
    if not isinstance(raw, dict):
        raise ValueError("Plan requires 'places' mapping")
    places: Dict[str, List[str]] = {}
    for place, codes in raw.items():
        place_id = strip_comment(place)
        if not place_id:
            raise ValueError("Place id must be a non-empty string")
        parsed_codes = _parse_place_codes(codes)
        if not parsed_codes:
            raise ValueError(f"Place '{place_id}' must provide at least one airport code")
        places[place_id] = parsed_codes
    return places


def parse_path(raw: Any) -> List[str]:
    if not isinstance(raw, (list, tuple)):
        raise ValueError("Plan requires 'path' list")
    path: List[str] = []
    for entry in raw:
        token = strip_comment(entry)
        if not token:
            raise ValueError("Path entries must be non-empty strings")
        path.append(token)
    if len(path) < 2:
        raise ValueError("Path must contain at least two points")
    return path


def parse_departures(raw: Any) -> Dict[tuple[str, str], LegDeparture]:
    if not isinstance(raw, dict):
        raise ValueError("Plan requires 'departures' mapping")
    departures: Dict[tuple[str, str], LegDeparture] = {}
    for key, value in raw.items():
        origin, destination = _parse_leg_key(key)
        selector = value
        max_stops = None
        if isinstance(value, dict) and "max_stops" in value:
            max_stops = value.get("max_stops")
            selector = {k: v for k, v in value.items() if k != "max_stops"}
            if not selector:
                raise ValueError(
                    f"Leg {origin}->{destination} must specify dates or window when using max_stops"
                )
        dates = _expand_date_selector(selector)
        if not dates:
            raise ValueError(f"Leg {origin}->{destination} produced no dates")
        departures[(origin, destination)] = LegDeparture(dates=dates, max_stops=max_stops)
    return departures


def parse_plan_filters(raw: Any) -> Dict[tuple[str, str], LegFilter]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError("Plan 'filters' must be a mapping")
    filters: Dict[tuple[str, str], LegFilter] = {}
    for key, value in raw.items():
        origin, destination = _parse_leg_key(key)
        max_stops_value = value.get("max_stops") if isinstance(value, dict) else value
        filters[(origin, destination)] = LegFilter(max_stops=max_stops_value)
    return filters


def parse_plan_options(raw: Any, defaults: FilterSettings) -> PlanOptions:
    if raw is None:
        return PlanOptions(
            include_hidden=defaults.include_hidden,
            max_hidden_hops=defaults.max_hidden_hops,
        )
    if not isinstance(raw, dict):
        raise ValueError("Plan 'options' must be a mapping")
    include_hidden = raw.get("include_hidden", defaults.include_hidden)
    max_hidden_hops = raw.get("max_hidden_hops", defaults.max_hidden_hops)
    return PlanOptions(include_hidden=include_hidden, max_hidden_hops=max_hidden_hops)


def parse_plan_output(raw: Any) -> PlanOutput:
    if raw is None:
        return PlanOutput()
    if not isinstance(raw, dict):
        raise ValueError("Plan 'output' must be a mapping")
    directory = raw.get("directory")
    filename_pattern = raw.get("filename_pattern")
    filename = raw.get("filename")
    if directory is not None:
        directory = strip_comment(directory)
    if filename_pattern is not None:
        filename_pattern = strip_comment(filename_pattern)
    if filename is not None:
        filename = strip_comment(filename)
    return PlanOutput(
        directory=directory,
        filename_pattern=filename_pattern,
        filename=filename,
    )


def parse_plan(raw: Any, defaults: FilterSettings) -> PlanConfig:
    if not isinstance(raw, dict):
        raise ValueError("Each plan must be a mapping")
    name = strip_comment(raw.get("name"))
    if not name:
        raise ValueError("Plan missing 'name'")
    places = parse_places(raw.get("places"))
    path = parse_path(raw.get("path"))
    departures = parse_departures(raw.get("departures"))
    options = parse_plan_options(raw.get("options"), defaults)
    filters = parse_plan_filters(raw.get("filters"))
    output = parse_plan_output(raw.get("output")) if raw.get("output") is not None else None
    for place in path:
        if place not in places:
            raise ValueError(f"Plan '{name}' path references undefined place '{place}'")
    return PlanConfig(
        name=name,
        places=places,
        path=path,
        departures=departures,
        options=options,
        filters=filters,
        output=output,
    )


def build_config(args: argparse.Namespace) -> SearchConfig:
    yaml_path: Path | None = None
    if args.config:
        yaml_path = Path(args.config)
    elif os.getenv(CONFIG_ENV_VAR):
        yaml_path = Path(os.environ[CONFIG_ENV_VAR])
    elif DEFAULT_CONFIG_FILE.exists():
        yaml_path = DEFAULT_CONFIG_FILE

    if yaml_path is None:
        raise ValueError("No config file provided")

    config_data = load_yaml_config(yaml_path)
    schema_version = strip_comment(config_data.get("schema_version"))
    if schema_version != "v2":
        raise ValueError("Config requires schema_version 'v2'")

    defaults_block = config_data.get("defaults", {})
    if not isinstance(defaults_block, dict):
        raise ValueError("'defaults' must be a mapping")

    currency_value = strip_comment(
        defaults_block.get("currency", DEFAULT_CURRENCY)
    ) or DEFAULT_CURRENCY
    if args.currency:
        currency_value = strip_comment(args.currency) or DEFAULT_CURRENCY

    passengers_raw = defaults_block.get("passengers", DEFAULT_PASSENGERS)
    if args.passengers is not None:
        passengers_raw = args.passengers
    passengers_token = strip_comment(passengers_raw)
    if not passengers_token:
        raise ValueError("Passenger count must be provided")
    try:
        passenger_count = int(passengers_token)
    except ValueError as exc:
        raise ValueError(f"Invalid passenger count: {passengers_raw}") from exc
    if passenger_count < 1:
        raise ValueError("Passenger count must be at least 1")

    request_block = defaults_block.get("request", {})
    if not isinstance(request_block, dict):
        raise ValueError("'defaults.request' must be a mapping")
    request_settings = RequestSettings(
        delay=request_block.get("delay", DEFAULT_REQUEST_DELAY),
        retries=request_block.get("retries", DEFAULT_MAX_RETRIES),
        max_leg_results=request_block.get("max_leg_results", DEFAULT_MAX_LEG_RESULTS),
    )

    filters_block = defaults_block.get("filters", {})
    if not isinstance(filters_block, dict):
        raise ValueError("'defaults.filters' must be a mapping")
    filter_settings = FilterSettings(
        max_stops=filters_block.get("max_stops", DEFAULT_MAX_STOPS),
        include_hidden=filters_block.get("include_hidden", DEFAULT_INCLUDE_HIDDEN),
        max_hidden_hops=filters_block.get("max_hidden_hops", DEFAULT_MAX_HIDDEN_HOPS),
    )

    output_block = defaults_block.get("output", {})
    if not isinstance(output_block, dict):
        raise ValueError("'defaults.output' must be a mapping")
    output_directory = strip_comment(output_block.get("directory", DEFAULT_OUTPUT_DIR)) or str(
        DEFAULT_OUTPUT_DIR
    )
    output_pattern = strip_comment(
        output_block.get("filename_pattern", DEFAULT_FILENAME_PATTERN)
    ) or DEFAULT_FILENAME_PATTERN
    output_settings = OutputSettings(directory=output_directory, filename_pattern=output_pattern)

    http_proxy = strip_comment(config_data.get("http_proxy", "")) or None
    if args.http_proxy:
        http_proxy = strip_comment(args.http_proxy) or None

    concurrency_value = config_data.get("concurrency", DEFAULT_CONCURRENCY)
    if args.concurrency is not None:
        concurrency_value = args.concurrency

    debug_value = config_data.get("debug", DEFAULT_DEBUG)
    debug_flag = bool(debug_value) or bool(args.debug)

    plans_raw = config_data.get("plans")
    if not isinstance(plans_raw, list) or not plans_raw:
        raise ValueError("Config must provide a non-empty 'plans' list")
    plans = [parse_plan(plan_raw, filter_settings) for plan_raw in plans_raw]

    if args.plan:
        allowed = {name.strip() for name in args.plan if name.strip()}
        plans = [plan for plan in plans if plan.name in allowed]
        if not plans:
            raise ValueError("No plans matched the provided --plan filters")

    config = SearchConfig(
        schema_version=schema_version,
        currency_code=currency_value,
        passenger_count=passenger_count,
        request=request_settings,
        filters=filter_settings,
        output=output_settings,
        http_proxy=http_proxy,
        concurrency=concurrency_value,
        debug=debug_flag,
        plans=plans,
    )
    return config


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Awesome Cheap Flights pipeline")
    parser.add_argument(
        "--config",
        help="Path to YAML config file (defaults to config.yaml or $AWESOME_CHEAP_FLIGHTS_CONFIG)",
    )
    parser.add_argument(
        "--plan",
        action="append",
        help="Plan name to execute (repeatable)",
    )
    parser.add_argument(
        "--currency",
        help="Override currency code",
    )
    parser.add_argument(
        "--passengers",
        type=int,
        help="Override passenger count",
    )
    parser.add_argument(
        "--http-proxy",
        help="HTTP(S) proxy URL to route requests through",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        help="Number of plan journeys to process in parallel",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_config(args)
    execute_search(config)
    return 0


__all__ = ["main", "parse_args", "build_config"]


if __name__ == "__main__":
    raise SystemExit(main())
