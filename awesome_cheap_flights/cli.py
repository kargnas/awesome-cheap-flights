from __future__ import annotations

import argparse
import os
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence, Tuple

import yaml

from .pipeline import SearchConfig, execute_search

DEFAULT_CONFIG_FILE = Path("config.yaml")
DEFAULT_REQUEST_DELAY = 1.0
DEFAULT_MAX_RETRIES = 2
DEFAULT_MAX_LEG_RESULTS = 10
DEFAULT_CURRENCY = "USD"
DEFAULT_PASSENGERS = 1
DEFAULT_MAX_STOPS = 2
DEFAULT_CONCURRENCY = 1
CONFIG_ENV_VAR = "AWESOME_CHEAP_FLIGHTS_CONFIG"
DATE_FMT = "%Y-%m-%d"
COMMENT_MARKERS = ("#",)
DEFAULT_OUTPUT_DIR = Path("output")


def strip_comment(value: Any) -> str:
    result = str(value)
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


def _explode_tokens(value: str) -> List[str]:
    return [token.strip() for token in value.split(",") if token.strip()]


def _collect_tokens(raw: Any, *, label: str) -> List[str]:
    if raw is None:
        return []
    if isinstance(raw, str):
        return _explode_tokens(strip_comment(raw))
    if isinstance(raw, (list, tuple)):
        tokens: List[str] = []
        for item in raw:
            if not isinstance(item, str):
                raise ValueError(f"{label} entries must be strings (found {item!r})")
            tokens.extend(_explode_tokens(strip_comment(item)))
        return tokens
    raise ValueError(f"Unsupported {label} type: {type(raw).__name__}")


def _normalize_codes(tokens: Iterable[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for token in tokens:
        code = token.strip().upper()
        if not code or code in seen:
            continue
        seen.add(code)
        ordered.append(code)
    return ordered


def normalize_departures(raw: Any) -> Dict[str, str]:
    codes = _normalize_codes(_collect_tokens(raw, label="departure"))
    return {code: code for code in codes}


def normalize_destinations(raw: Any) -> List[Dict[str, str]]:
    codes = _normalize_codes(_collect_tokens(raw, label="destination"))
    return [{"city": code, "country": "", "iata": code} for code in codes]


def expand_dates(field: Any) -> List[str]:
    if field is None:
        return []
    if isinstance(field, str):
        token = strip_comment(field)
        return [token] if token else []
    if isinstance(field, date):
        return [field.strftime(DATE_FMT)]
    if isinstance(field, (list, tuple)):
        dates: List[str] = []
        for entry in field:
            dates.extend(expand_dates(entry))
        return dates
    if isinstance(field, dict):
        if "step" in field:
            raise ValueError("Date range 'step' option is no longer supported")
        start_raw = strip_comment(field.get("start", ""))
        end_raw = strip_comment(field.get("end", start_raw))
        if not start_raw or not end_raw:
            raise ValueError(f"Date range requires 'start' and 'end': {field}")
        start_date = datetime.strptime(start_raw, DATE_FMT).date()
        end_date = datetime.strptime(end_raw, DATE_FMT).date()
        if end_date < start_date:
            raise ValueError("Date range end must be on or after start")
        current = start_date
        dates: List[str] = []
        while current <= end_date:
            dates.append(current.strftime(DATE_FMT))
            current += timedelta(days=1)
        return dates
    raise ValueError(f"Unsupported date format: {field}")


def normalize_itineraries(raw: Any) -> List[Tuple[str, str]]:
    if raw is None:
        return []
    items: Iterable[Any] = raw if isinstance(raw, (list, tuple)) else [raw]
    pairs: List[Tuple[str, str]] = []
    for item in items:
        if isinstance(item, str):
            token = strip_comment(item)
            if not token:
                continue
            if ":" not in token:
                raise ValueError("String itineraries must use 'outbound:inbound' format")
            outbound, inbound = (part.strip() for part in token.split(":", 1))
            if not outbound or not inbound:
                raise ValueError(f"Invalid itinerary entry: {item}")
            pairs.append((outbound, inbound))
            continue

        if isinstance(item, (list, tuple)) and len(item) == 2 and all(isinstance(value, str) for value in item):
            pairs.append((strip_comment(item[0]), strip_comment(item[1])))
            continue

        if isinstance(item, dict):
            outbound_field = item.get("outbound")
            inbound_field = item.get("inbound")
            if outbound_field is None or inbound_field is None:
                raise ValueError("Itinerary dict requires 'outbound' and 'inbound'")
            outbound_options = expand_dates(outbound_field)
            inbound_options = expand_dates(inbound_field)
            if not outbound_options or not inbound_options:
                raise ValueError(f"Itinerary produced empty dates: {item}")
            for outbound in outbound_options:
                for inbound in inbound_options:
                    pairs.append((outbound, inbound))
            continue

        raise ValueError(f"Invalid itinerary entry: {item}")
    return [(outbound, inbound) for outbound, inbound in pairs if outbound and inbound]


def build_config(args: argparse.Namespace) -> SearchConfig:
    yaml_path: Path | None = None
    if args.config:
        yaml_path = Path(args.config)
    elif os.getenv(CONFIG_ENV_VAR):
        yaml_path = Path(os.environ[CONFIG_ENV_VAR])
    elif DEFAULT_CONFIG_FILE.exists():
        yaml_path = DEFAULT_CONFIG_FILE

    config_data: Dict[str, Any] = {}
    if yaml_path:
        config_data = load_yaml_config(yaml_path)

    departures_raw = config_data.get("departures")
    destinations_raw = config_data.get("destinations", config_data.get("arrivals"))
    itineraries_raw = config_data.get("itineraries")

    if args.departure:
        departures_raw = args.departure
    if args.destination:
        destinations_raw = args.destination
    if args.itinerary:
        itineraries_raw = args.itinerary

    departures = normalize_departures(departures_raw)
    destinations = normalize_destinations(destinations_raw)
    itineraries = normalize_itineraries(itineraries_raw)

    if not departures:
        raise ValueError("At least one departure code must be provided")
    if not destinations:
        raise ValueError("At least one destination code must be provided")
    if not itineraries:
        raise ValueError("At least one itinerary must be provided")

    output_path: Path | None = None
    if args.output:
        output_path = Path(strip_comment(args.output))
    elif config_data.get("output_path"):
        output_path = Path(strip_comment(config_data["output_path"]))
    if output_path is None:
        local_time = datetime.now().astimezone()
        tz_name = local_time.tzname() or local_time.strftime("UTC%z")
        safe_tz = "".join(ch for ch in tz_name if ch.isalnum() or ch in {"+", "-"}) or "LOCAL"
        timestamp = local_time.strftime("%Y%m%d_%H%M%S")
        output_path = DEFAULT_OUTPUT_DIR / f"{timestamp}_{safe_tz}.csv"

    request_delay = float(config_data.get("request_delay", DEFAULT_REQUEST_DELAY))
    max_retries = int(config_data.get("max_retries", DEFAULT_MAX_RETRIES))
    max_leg_results = int(config_data.get("max_leg_results", DEFAULT_MAX_LEG_RESULTS))

    currency_value = strip_comment(config_data.get("currency", DEFAULT_CURRENCY))
    if args.currency:
        currency_value = strip_comment(args.currency)
    currency_value = currency_value.upper() if currency_value else DEFAULT_CURRENCY

    passengers_value = config_data.get("passengers", DEFAULT_PASSENGERS)
    if args.passengers is not None:
        passengers_value = args.passengers
    passengers_raw = strip_comment(passengers_value)
    if not passengers_raw:
        raise ValueError("Passenger count must be provided")
    try:
        passenger_count = int(passengers_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid passenger count: {passengers_value}") from exc
    if passenger_count < 1:
        raise ValueError("Passenger count must be at least 1")

    max_stops_value = config_data.get("max_stops", DEFAULT_MAX_STOPS)
    if args.max_stops is not None:
        max_stops_value = args.max_stops
    max_stops_raw = strip_comment(max_stops_value)
    if max_stops_raw == "":
        raise ValueError("Max stops must be provided")
    try:
        max_stops = int(max_stops_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid max stops: {max_stops_value}") from exc
    if max_stops < 0 or max_stops > 2:
        raise ValueError("Max stops must be between 0 and 2")

    proxy_value = config_data.get("http_proxy")
    if args.http_proxy:
        proxy_value = args.http_proxy
    http_proxy = strip_comment(proxy_value) if proxy_value else None

    concurrency_value = config_data.get("concurrency", DEFAULT_CONCURRENCY)
    if args.concurrency is not None:
        concurrency_value = args.concurrency
    concurrency_raw = strip_comment(concurrency_value)
    if concurrency_raw == "":
        raise ValueError("Concurrency must be provided")
    try:
        concurrency = int(concurrency_raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid concurrency: {concurrency_value}") from exc
    if concurrency < 1:
        raise ValueError("Concurrency must be at least 1")

    return SearchConfig(
        origins=departures,
        destinations=destinations,
        itineraries=itineraries,
        output_path=output_path,
        request_delay=request_delay,
        max_retries=max_retries,
        max_leg_results=max_leg_results,
        currency_code=currency_value,
        passenger_count=passenger_count,
        max_stops=max_stops,
        http_proxy=http_proxy,
        concurrency=concurrency,
    )


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Awesome Cheap Flights pipeline")
    parser.add_argument(
        "--config",
        help="Path to YAML config file (defaults to config.yaml or $AWESOME_CHEAP_FLIGHTS_CONFIG)",
    )
    parser.add_argument(
        "--departure",
        action="append",
        help="Departure codes (repeatable). Accepts comma-separated list",
    )
    parser.add_argument(
        "--destination",
        action="append",
        help="Destination codes (repeatable). Accepts comma-separated list",
    )
    parser.add_argument(
        "--itinerary",
        action="append",
        help="Travel date pair (repeatable). Accepts 'YYYY-MM-DD:YYYY-MM-DD' or YAML-style dict",
    )
    parser.add_argument(
        "--output",
        help="Output CSV path",
    )
    parser.add_argument(
        "--currency",
        help="ISO currency code for aggregated prices (default: USD)",
    )
    parser.add_argument(
        "--passengers",
        type=int,
        help="Number of adult passengers to include in the fare search",
    )
    parser.add_argument(
        "--max-stops",
        type=int,
        help="Maximum stops per leg (0=nonstop, 1=one stop, 2=two stops)",
    )
    parser.add_argument(
        "--http-proxy",
        help="HTTP(S) proxy URL to route requests through",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        help="Number of itinerary combinations to process in parallel",
    )
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_config(args)
    execute_search(config)
    return 0


__all__ = ["main", "parse_args", "build_config"]
