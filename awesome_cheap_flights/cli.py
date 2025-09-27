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
CONFIG_ENV_VAR = "AWESOME_CHEAP_FLIGHTS_CONFIG"
DATE_FMT = "%Y-%m-%d"
COMMENT_MARKERS = ("#",)


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


def normalize_departures(raw: Any) -> Dict[str, str]:
    if raw is None:
        return {}
    if isinstance(raw, dict):
        return {
            strip_comment(name): strip_comment(code).upper()
            for name, code in raw.items()
            if strip_comment(name) and strip_comment(code)
        }

    items: Iterable[Any] = raw if isinstance(raw, (list, tuple)) else [raw]
    result: Dict[str, str] = {}
    for item in items:
        if isinstance(item, str):
            token = strip_comment(item)
            if not token:
                continue
            if ":" in token:
                name, code = (part.strip() for part in token.split(":", 1))
            else:
                name = code = token
            if name and code:
                result[name] = code.upper()
        elif isinstance(item, dict):
            for name, code in item.items():
                name_token = strip_comment(name)
                code_token = strip_comment(code)
                if name_token and code_token:
                    result[name_token] = code_token.upper()
        else:
            raise ValueError(f"Invalid departure entry: {item}")
    return result


def normalize_destinations(raw: Any) -> List[Dict[str, str]]:
    if raw is None:
        return []
    items: Iterable[Any] = raw if isinstance(raw, (list, tuple)) else [raw]
    destinations: List[Dict[str, str]] = []
    for item in items:
        if isinstance(item, str):
            token = strip_comment(item)
            if not token:
                continue
            destinations.append({"city": token, "country": "", "iata": token.upper()})
        elif isinstance(item, dict):
            city = strip_comment(item.get("city", item.get("iata", "")))
            country = strip_comment(item.get("country", ""))
            iata = strip_comment(item.get("iata", "")).upper()
            if not city or not iata:
                raise ValueError(f"Destination requires at least city/iata: {item}")
            destinations.append({"city": city, "country": country, "iata": iata})
        else:
            raise ValueError(f"Invalid destination entry: {item}")
    return destinations


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
            if outbound_field is None and "departure" in item:
                outbound_field = item["departure"]
            if inbound_field is None and "return" in item:
                inbound_field = item["return"]
            if outbound_field is None or inbound_field is None:
                raise ValueError("Itinerary dict requires 'outbound' and 'inbound' (or 'departure'/'return')")
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

    output_path_value = config_data.get("output_path")
    if args.output:
        output_path_value = args.output
    if not output_path_value:
        raise ValueError("Output path must be supplied via --output or YAML 'output_path'")
    output_path = Path(strip_comment(output_path_value))

    request_delay = float(config_data.get("request_delay", DEFAULT_REQUEST_DELAY))
    max_retries = int(config_data.get("max_retries", DEFAULT_MAX_RETRIES))
    max_leg_results = int(config_data.get("max_leg_results", DEFAULT_MAX_LEG_RESULTS))

    currency_value = strip_comment(config_data.get("currency", DEFAULT_CURRENCY))
    if args.currency:
        currency_value = strip_comment(args.currency)
    currency_value = currency_value.upper() if currency_value else DEFAULT_CURRENCY

    return SearchConfig(
        origins=departures,
        destinations=destinations,
        itineraries=itineraries,
        output_path=output_path,
        request_delay=request_delay,
        max_retries=max_retries,
        max_leg_results=max_leg_results,
        currency_code=currency_value,
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
        help="Departure codes (repeatable). Accepts 'Name:CODE' or 'CODE'",
    )
    parser.add_argument(
        "--destination",
        action="append",
        help="Destination codes (repeatable). Accepts 'City:Country:CODE' or 'CODE'",
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
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    config = build_config(args)
    execute_search(config)
    return 0


__all__ = ["main", "parse_args", "build_config"]
