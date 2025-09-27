import csv
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from fast_flights import FlightData, Passengers, Result, get_flights
from fast_flights.core import fetch as core_fetch
from fast_flights.fallback_playwright import fallback_playwright_fetch
from fast_flights.flights_impl import TFSData
from selectolax.lexbor import LexborHTMLParser

TIME_PATTERN = re.compile(
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>AM|PM)\s*on\s*"
    r"(?P<weekday>[A-Za-z]{3}),\s*(?P<month>[A-Za-z]{3})\s*(?P<day>\d{1,2})"
    r"(?:\s*\+(?P<plus>\d+)\s*day[s]?)?"
)


@dataclass
class SearchConfig:
    origins: Dict[str, str]
    destinations: Sequence[Dict[str, str]]
    itineraries: Sequence[Tuple[str, str]]
    output_path: Path
    request_delay: float = 1.0
    max_retries: int = 2
    max_leg_results: int = 10
    currency_code: str = "USD"

    def __post_init__(self) -> None:
        self.output_path = Path(self.output_path)
        self.currency_code = self.currency_code.upper()


@dataclass
class LegFlight:
    airline_name: str
    departure_at: str
    stops: str
    stop_notes: str
    price: Optional[int]
    is_best: bool


@dataclass
class ItineraryRow:
    origin_code: str
    destination_code: str
    outbound_departure_at: str
    return_departure_at: str
    outbound_airline: str
    outbound_stops: str
    outbound_stop_notes: str
    outbound_price: Optional[int]
    outbound_is_best: bool
    return_airline: str
    return_stops: str
    return_stop_notes: str
    return_price: Optional[int]
    return_is_best: bool
    total_price: Optional[int]
    currency: str


def standardize_time(raw: str, year_hint: int) -> str:
    if not raw:
        return ""
    cleaned = raw.replace("\u202f", " ").replace("\xa0", " ").replace("\u2009", " ")
    match = TIME_PATTERN.search(cleaned)
    if not match:
        return ""
    hour = int(match.group("hour"))
    minute = int(match.group("minute"))
    ampm = match.group("ampm")
    month = match.group("month")
    day = int(match.group("day"))
    plus = int(match.group("plus")) if match.group("plus") else 0
    dt = datetime.strptime(
        f"{year_hint} {month} {day} {hour}:{minute:02d} {ampm}",
        "%Y %b %d %I:%M %p",
    )
    if plus:
        dt += timedelta(days=plus)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_price_to_int(price: str) -> Optional[int]:
    digits = "".join(ch for ch in price if ch.isdigit())
    return int(digits) if digits else None


def describe_stops(stop_value: object, stop_text: str) -> str:
    if stop_text:
        return stop_text
    if isinstance(stop_value, int):
        if stop_value == 0:
            return "Nonstop"
        suffix = "stop" if stop_value == 1 else "stops"
        return f"{stop_value} {suffix}"
    return str(stop_value)


def build_flight_data(origin_code: str, destination_code: str, departure_date: str) -> List[FlightData]:
    return [
        FlightData(
            date=departure_date,
            from_airport=origin_code,
            to_airport=destination_code,
        )
    ]


def safe_text(node) -> str:
    return node.text(strip=True) if node is not None else ""


def parse_layover_details(html: str) -> Dict[Tuple[str, str, str], Tuple[str, str]]:
    parser = LexborHTMLParser(html)
    details: Dict[Tuple[str, str, str], Tuple[str, str]] = {}

    for idx, container in enumerate(parser.css('div[jsname="IWWDBc"], div[jsname="YdtKid"]')):
        items = container.css("ul.Rk10dc li")
        if idx != 0:
            items = items[:-1]
        for item in items:
            name = safe_text(item.css_first("div.sSHqwe.tPgKwe.ogfYpf span"))
            dp_ar_node = item.css("span.mv1WYe div")
            try:
                departure_time = dp_ar_node[0].text(strip=True)
            except IndexError:
                departure_time = ""
            price_text = safe_text(item.css_first(".YMlIz.FpEdX")) or "0"
            price_clean = price_text.replace(",", "")
            stop_text = safe_text(item.css_first(".BbR8Ec .ogfYpf"))
            layover_values: List[str] = []
            for span in item.css("span.rGRiKd"):
                val = span.text(strip=True)
                if val and val not in layover_values:
                    layover_values.append(val)
            layover_str = "; ".join(layover_values)
            key = (name, " ".join(departure_time.split()), price_clean)
            details.setdefault(key, (stop_text, layover_str))

    return details


def fetch_leg_html(
    *,
    origin_code: str,
    destination_code: str,
    departure_date: str,
    max_stops: int,
) -> str:
    flight_data = build_flight_data(origin_code, destination_code, departure_date)
    filter_payload = TFSData.from_interface(
        flight_data=flight_data,
        trip="one-way",
        passengers=Passengers(adults=1),
        seat="economy",
        max_stops=max_stops,
    )
    params = {
        "tfs": filter_payload.as_b64().decode("utf-8"),
        "hl": "en",
        "tfu": "EgQIABABIgA",
        "curr": "",
    }
    try:
        response = core_fetch(params)
        return response.text
    except AssertionError:
        try:
            response = fallback_playwright_fetch(params)
            return response.text
        except Exception:  # noqa: BLE001
            return ""


def fetch_leg_flights(
    *,
    config: SearchConfig,
    origin_code: str,
    destination_code: str,
    departure_date: str,
    max_stops: int = 2,
) -> List[LegFlight]:
    last_exc: Optional[Exception] = None
    result: Optional[Result] = None
    layover_lookup: Dict[Tuple[str, str, str], Tuple[str, str]] = {}

    for attempt in range(1, config.max_retries + 1):
        try:
            flight_data = build_flight_data(origin_code, destination_code, departure_date)
            result = get_flights(
                flight_data=flight_data,
                trip="one-way",
                passengers=Passengers(adults=1),
                seat="economy",
                fetch_mode="common",
                max_stops=max_stops,
            )
            html = fetch_leg_html(
                origin_code=origin_code,
                destination_code=destination_code,
                departure_date=departure_date,
                max_stops=max_stops,
            )
            if html:
                layover_lookup = parse_layover_details(html)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait_time = config.request_delay * attempt
            print(
                (
                    f"Error for {origin_code}->{destination_code} "
                    f"({departure_date}) on attempt {attempt}: {exc}"
                ),
                file=sys.stderr,
            )
            if attempt < config.max_retries:
                time.sleep(wait_time)

    if result is None:
        if last_exc:
            print(
                f"Skip {origin_code}->{destination_code} ({departure_date}) after {config.max_retries} failures",
                file=sys.stderr,
            )
            print(f"Last error: {last_exc}", file=sys.stderr)
        return []

    flights: List[LegFlight] = []
    seen: set[Tuple[str, str, str]] = set()
    base_year = int(departure_date.split("-", 1)[0])

    for flight in result.flights:
        if len(flights) >= config.max_leg_results:
            break
        key = (flight.name, flight.departure, flight.price)
        if key in seen:
            continue
        seen.add(key)
        departure_std = standardize_time(flight.departure, base_year)
        if not departure_std:
            continue
        stop_text, stop_detail = layover_lookup.get(key, ("", ""))
        flights.append(
            LegFlight(
                airline_name=flight.name,
                departure_at=departure_std,
                stops=describe_stops(flight.stops, stop_text),
                stop_notes=stop_detail,
                price=parse_price_to_int(flight.price),
                is_best=flight.is_best,
            )
        )

    return flights


def build_itineraries(
    *,
    config: SearchConfig,
    origin_code: str,
    destination: Dict[str, str],
    departure_date: str,
    return_date: str,
) -> List[ItineraryRow]:
    outbound_flights = fetch_leg_flights(
        config=config,
        origin_code=origin_code,
        destination_code=destination["iata"],
        departure_date=departure_date,
    )
    time.sleep(config.request_delay)
    return_flights = fetch_leg_flights(
        config=config,
        origin_code=destination["iata"],
        destination_code=origin_code,
        departure_date=return_date,
    )

    if not outbound_flights or not return_flights:
        print(
            (
                f"Skip itinerary {origin_code}->{destination['iata']} "
                f"({departure_date}/{return_date}) due to empty leg"
            ),
            file=sys.stderr,
        )
        return []

    rows: List[ItineraryRow] = []

    for outbound in outbound_flights:
        for inbound in return_flights:
            total_price: Optional[int] = None
            if outbound.price is not None and inbound.price is not None:
                total_price = outbound.price + inbound.price
            rows.append(
                ItineraryRow(
                    origin_code=origin_code,
                    destination_code=destination["iata"],
                    outbound_departure_at=outbound.departure_at,
                    return_departure_at=inbound.departure_at,
                    outbound_airline=outbound.airline_name,
                    outbound_stops=outbound.stops,
                    outbound_stop_notes=outbound.stop_notes,
                    outbound_price=outbound.price,
                    outbound_is_best=outbound.is_best,
                    return_airline=inbound.airline_name,
                    return_stops=inbound.stops,
                    return_stop_notes=inbound.stop_notes,
                    return_price=inbound.price,
                    return_is_best=inbound.is_best,
                    total_price=total_price,
                    currency=config.currency_code,
                )
            )
    return rows


def write_csv(rows: Sequence[ItineraryRow], output_path: Path) -> None:
    if not rows:
        print("No flight data available to write.", file=sys.stderr)
        return
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as csvfile:
        fieldnames = list(asdict(rows[0]).keys())
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(asdict(row))


def run_search(config: SearchConfig) -> List[ItineraryRow]:
    all_rows: List[ItineraryRow] = []
    for _, origin_code in config.origins.items():
        for destination in config.destinations:
            for departure_date, return_date in config.itineraries:
                print(
                    f"Processing {origin_code}->{destination['iata']} for {departure_date} / {return_date}",
                    file=sys.stderr,
                )
                rows = build_itineraries(
                    config=config,
                    origin_code=origin_code,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                )
                all_rows.extend(rows)
                time.sleep(config.request_delay)
    return all_rows


def execute_search(config: SearchConfig) -> List[ItineraryRow]:
    rows = run_search(config)
    if not rows:
        print("No flights captured.", file=sys.stderr)
        return rows
    write_csv(rows, config.output_path)
    print(f"Saved {len(rows)} rows to {config.output_path}")
    return rows


__all__ = [
    "SearchConfig",
    "LegFlight",
    "ItineraryRow",
    "run_search",
    "execute_search",
]
