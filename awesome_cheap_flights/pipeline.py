import csv
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from pathlib import Path
from threading import Lock
from typing import Dict, List, Optional, Sequence, Tuple

from fast_flights import FlightData, Passengers, Result
from fast_flights.core import parse_response
from fast_flights.fallback_playwright import CODE as PLAYWRIGHT_FALLBACK_CODE
from fast_flights.flights_impl import TFSData
from fast_flights.primp import Client
from selectolax.lexbor import LexborHTMLParser

from rich import box
from rich.console import Console
from rich.progress import (
    BarColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

TIME_PATTERN = re.compile(
    r"(?P<hour>\d{1,2}):(?P<minute>\d{2})\s*(?P<ampm>AM|PM)\s*on\s*"
    r"(?P<weekday>[A-Za-z]{3}),\s*(?P<month>[A-Za-z]{3})\s*(?P<day>\d{1,2})"
    r"(?:\s*\+(?P<plus>\d+)\s*day[s]?)?"
)


DURATION_PATTERN = re.compile(r'(?:(?P<hours>\d+)\s*h(?:ours?)?)?(?:\s*(?P<minutes>\d+)\s*m(?:in)?)?', re.IGNORECASE)


console = Console(stderr=True, highlight=False)


class ProgressReporter:
    def __init__(self, total_steps: int, *, config: Optional["SearchConfig"] = None) -> None:
        self.total_steps = total_steps
        self.rows_collected = 0
        self.processed = 0
        self.skipped = 0
        self._task_id: Optional[int] = None
        self._progress: Optional[Progress] = None
        self._start = time.perf_counter()
        self._config = config
        self._lock = Lock()

    def __enter__(self) -> "ProgressReporter":
        if self.total_steps > 0 and console.is_terminal:
            self._progress = Progress(
                SpinnerColumn(),
                TextColumn("{task.description}"),
                BarColumn(bar_width=None),
                TaskProgressColumn(),
                TimeElapsedColumn(),
                TimeRemainingColumn(),
                console=console,
                redirect_stdout=False,
                redirect_stderr=False,
            )
            self._progress.__enter__()
            self._task_id = self._progress.add_task("Preparing", total=self.total_steps)
        self._render_overview()
        return self

    def __exit__(self, exc_type, exc, exc_tb) -> None:
        if self._progress is not None:
            self._progress.__exit__(exc_type, exc, exc_tb)
        self._render_summary()

    def record_success(self, label: str, rows_added: int) -> None:
        with self._lock:
            self.processed += 1
            self.rows_collected += rows_added
            message = f"+{rows_added} rows"
            total_note = f"total {self.rows_collected}"
            log_line = f"[green]{label}[/] {message} {total_note}"
            if self._progress is not None and self._task_id is not None:
                self._progress.update(self._task_id, advance=1, description=label)
                self._progress.log(log_line)
            else:
                console.log(log_line)

    def record_skip(self, label: str, reason: str) -> None:
        with self._lock:
            self.processed += 1
            self.skipped += 1
            note = reason if reason.endswith(".") else f"{reason}."
            total_note = f"total {self.rows_collected}"
            log_line = f"[yellow]{label}[/] {note} {total_note}"
            if self._progress is not None and self._task_id is not None:
                self._progress.update(self._task_id, advance=1, description=label)
                self._progress.log(log_line)
            else:
                console.log(log_line)

    def log_warning(self, message: str) -> None:
        text = message if message.endswith(".") else f"{message}."
        with self._lock:
            if self._progress is not None:
                self._progress.log(f"[yellow]{text}")
            else:
                console.log(f"[yellow]{text}")

    def log_error(self, message: str) -> None:
        text = message if message.endswith(".") else f"{message}."
        with self._lock:
            if self._progress is not None:
                self._progress.log(f"[red]{text}")
            else:
                console.log(f"[red]{text}")

    def _render_summary(self) -> None:
        elapsed_minutes = (time.perf_counter() - self._start) / 60 or 0.0
        table = Table(title="Flight Capture Summary", box=box.SIMPLE_HEAD)
        table.add_column("Metric", justify="left")
        table.add_column("Value", justify="right")
        table.add_row("Itineraries processed", str(self.processed))
        table.add_row("Itineraries skipped", str(self.skipped))
        table.add_row("Rows collected", str(self.rows_collected))
        table.add_row("Elapsed minutes", f"{elapsed_minutes:.2f}")
        console.print(table)

    def _render_overview(self) -> None:
        if self._config is None:
            return
        origins = ", ".join(sorted(self._config.origins.values())) or "-"
        destinations = ", ".join(dest.get("iata", "?") for dest in self._config.destinations) or "-"
        total_pairs = (
            len(self._config.origins)
            * len(self._config.destinations)
            * len(self._config.itineraries)
        )
        table = Table(title="Search Overview", box=box.SIMPLE_HEAD)
        table.add_column("Field", justify="left")
        table.add_column("Value", justify="right")
        table.add_row("Origins", origins)
        table.add_row("Destinations", destinations)
        table.add_row("Passengers", str(self._config.passenger_count))
        table.add_row("Currency", self._config.currency_code)
        table.add_row("Max stops", str(self._config.max_stops))
        table.add_row("Max leg results", str(self._config.max_leg_results))
        table.add_row("Request delay", f"{self._config.request_delay:.2f}s")
        table.add_row("Retry limit", str(self._config.max_retries))
        table.add_row("Concurrency", str(self._config.concurrency))
        table.add_row("HTTP proxy", self._config.http_proxy or "-")
        table.add_row("Total itineraries", str(total_pairs))
        console.print(table)


def _warn(message: str, reporter: Optional[ProgressReporter] = None) -> None:
    if reporter is not None:
        reporter.log_warning(message)
    else:
        text = message if message.endswith(".") else f"{message}."
        console.log(f"[yellow]{text}")


def _error(message: str, reporter: Optional[ProgressReporter] = None) -> None:
    if reporter is not None:
        reporter.log_error(message)
    else:
        text = message if message.endswith(".") else f"{message}."
        console.log(f"[red]{text}")


def _core_fetch(params: Dict[str, str], proxy: Optional[str]) -> object:
    client = Client(impersonate="chrome_126", verify=False, proxy=proxy)
    res = client.get("https://www.google.com/travel/flights", params=params)
    assert res.status_code == 200, f"{res.status_code} Result: {res.text_markdown}"
    return res


def _fallback_fetch(params: Dict[str, str], proxy: Optional[str]) -> object:
    client = Client(impersonate="chrome_100", verify=False, proxy=proxy)
    res = client.post(
        "https://try.playwright.tech/service/control/run",
        json={
            "code": PLAYWRIGHT_FALLBACK_CODE
            % (
                "https://www.google.com/travel/flights"
                + "?"
                + "&".join(f"{k}={v}" for k, v in params.items())
            ),
            "language": "python",
        },
    )
    assert res.status_code == 200, f"{res.status_code} Result: {res.text_markdown}"

    class DummyResponse:
        status_code = 200
        text = json.loads(res.text)["output"]
        text_markdown = text

    return DummyResponse


def _get_flights_from_filter(
    filter_payload: TFSData,
    *,
    currency: str,
    mode: str = "common",
    proxy: Optional[str] = None,
) -> Result:
    data = filter_payload.as_b64()
    params = {
        "tfs": data.decode("utf-8"),
        "hl": "en",
        "tfu": "EgQIABABIgA",
        "curr": currency,
    }

    def resolve(mode_value: str) -> object:
        if mode_value in {"common", "fallback"}:
            try:
                return _core_fetch(params, proxy)
            except AssertionError as exc:
                if mode_value == "fallback":
                    return _fallback_fetch(params, proxy)
                raise exc
        if mode_value == "local":
            from fast_flights.local_playwright import local_playwright_fetch

            return local_playwright_fetch(params)
        return _fallback_fetch(params, proxy)

    response = resolve(mode)
    try:
        return parse_response(response)
    except RuntimeError as exc:
        if mode == "fallback":
            return _get_flights_from_filter(
                filter_payload,
                currency=currency,
                mode="force-fallback",
                proxy=proxy,
            )
        raise exc

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
    passenger_count: int = 1
    max_stops: int = 2
    http_proxy: Optional[str] = None
    concurrency: int = 1

    def __post_init__(self) -> None:
        self.output_path = Path(self.output_path)
        self.currency_code = self.currency_code.upper()
        try:
            self.passenger_count = int(self.passenger_count)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid passenger count: {self.passenger_count}") from exc
        if self.passenger_count < 1:
            raise ValueError("Passenger count must be at least 1")
        try:
            self.max_stops = int(self.max_stops)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid max stops: {self.max_stops}") from exc
        if self.max_stops < 0 or self.max_stops > 2:
            raise ValueError("Max stops must be between 0 and 2")
        try:
            self.concurrency = int(self.concurrency)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Invalid concurrency: {self.concurrency}") from exc
        if self.concurrency < 1:
            raise ValueError("Concurrency must be at least 1")


@dataclass
class LegFlight:
    airline_name: str
    departure_at: str
    stops: str
    stop_notes: str
    duration_hours: Optional[float]
    price: Optional[int]
    is_best: bool


@dataclass
class ItineraryRow:
    origin_code: str
    destination_code: str
    outbound_departure_at: str
    outbound_duration_hours: Optional[float]
    return_departure_at: str
    return_duration_hours: Optional[float]
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
    round_trip_price: Optional[int]


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


def parse_duration_to_hours(raw: str) -> Optional[float]:
    if not raw:
        return None
    match = DURATION_PATTERN.search(raw)
    if not match:
        return None
    hours = int(match.group("hours")) if match.group("hours") else 0
    minutes = int(match.group("minutes")) if match.group("minutes") else 0
    total_minutes = hours * 60 + minutes
    if total_minutes == 0:
        return None
    value = total_minutes / 60
    return round(value, 2)


def extract_stop_codes(raw: str) -> str:
    if not raw:
        return ""
    codes = []
    for token in re.findall(r"[A-Z]{3}", raw):
        if token not in codes:
            codes.append(token)
    return " ".join(codes)


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
            layover_codes = extract_stop_codes(" ".join(layover_values))
            key = (name, " ".join(departure_time.split()), price_clean)
            details.setdefault(key, (stop_text, layover_codes))

    return details


def fetch_leg_html(
    *,
    origin_code: str,
    destination_code: str,
    departure_date: str,
    max_stops: int,
    passenger_count: int,
    currency_code: str,
    proxy: Optional[str],
) -> str:
    flight_data = build_flight_data(origin_code, destination_code, departure_date)
    filter_payload = TFSData.from_interface(
        flight_data=flight_data,
        trip="one-way",
        passengers=Passengers(adults=passenger_count),
        seat="economy",
        max_stops=max_stops,
    )
    params = {
        "tfs": filter_payload.as_b64().decode("utf-8"),
        "hl": "en",
        "tfu": "EgQIABABIgA",
        "curr": currency_code,
    }
    try:
        response = _core_fetch(params, proxy)
        return response.text
    except AssertionError:
        try:
            response = _fallback_fetch(params, proxy)
            return response.text
        except Exception:  # noqa: BLE001
            return ""


def fetch_round_trip_price(
    *,
    config: SearchConfig,
    origin_code: str,
    destination_code: str,
    departure_date: str,
    return_date: str,
    max_stops: int,
    reporter: Optional[ProgressReporter] = None,
) -> Optional[int]:
    last_exc: Optional[Exception] = None
    for attempt in range(1, config.max_retries + 1):
        try:
            flight_data = [
                FlightData(
                    date=departure_date,
                    from_airport=origin_code,
                    to_airport=destination_code,
                ),
                FlightData(
                    date=return_date,
                    from_airport=destination_code,
                    to_airport=origin_code,
                ),
            ]
            filter_payload = TFSData.from_interface(
                flight_data=flight_data,
                trip="round-trip",
                passengers=Passengers(adults=config.passenger_count),
                seat="economy",
                max_stops=max_stops,
            )
            result = _get_flights_from_filter(
                filter_payload,
                currency=config.currency_code,
                mode="common",
                proxy=config.http_proxy,
            )
            best_price: Optional[int] = None
            for flight in result.flights:
                price_value = parse_price_to_int(flight.price)
                if price_value is None:
                    continue
                if best_price is None or price_value < best_price:
                    best_price = price_value
            return best_price
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait_time = config.request_delay * attempt
            _warn(
                (
                    f"Round-trip fail {origin_code}->{destination_code} "
                    f"{departure_date}/{return_date} try {attempt}: {exc}"
                ),
                reporter,
            )
            if attempt < config.max_retries:
                time.sleep(wait_time)
    if last_exc:
        _warn(
            (
                f"Round-trip skip {origin_code}->{destination_code} "
                f"{departure_date}/{return_date} after {config.max_retries} tries"
            ),
            reporter,
        )
        _error(f"Round-trip last error: {last_exc}", reporter)
    return None


def fetch_leg_flights(
    *,
    config: SearchConfig,
    origin_code: str,
    destination_code: str,
    departure_date: str,
    max_stops: int,
    reporter: Optional[ProgressReporter] = None,
) -> List[LegFlight]:
    last_exc: Optional[Exception] = None
    result: Optional[Result] = None
    layover_lookup: Dict[Tuple[str, str, str], Tuple[str, str]] = {}

    for attempt in range(1, config.max_retries + 1):
        try:
            flight_data = build_flight_data(origin_code, destination_code, departure_date)
            filter_payload = TFSData.from_interface(
                flight_data=flight_data,
                trip="one-way",
                passengers=Passengers(adults=config.passenger_count),
                seat="economy",
                max_stops=max_stops,
            )
            result = _get_flights_from_filter(
                filter_payload,
                currency=config.currency_code,
                mode="common",
                proxy=config.http_proxy,
            )
            html = fetch_leg_html(
                origin_code=origin_code,
                destination_code=destination_code,
                departure_date=departure_date,
                max_stops=max_stops,
                passenger_count=config.passenger_count,
                currency_code=config.currency_code,
                proxy=config.http_proxy,
            )
            if html:
                layover_lookup = parse_layover_details(html)
            break
        except Exception as exc:  # noqa: BLE001
            last_exc = exc
            wait_time = config.request_delay * attempt
            _warn(
                (
                    f"Leg fail {origin_code}->{destination_code} "
                    f"{departure_date} try {attempt}: {exc}"
                ),
                reporter,
            )
            if attempt < config.max_retries:
                time.sleep(wait_time)

    if result is None:
        if last_exc:
            _warn(
                (
                    f"Leg skip {origin_code}->{destination_code} "
                    f"{departure_date} after {config.max_retries} tries"
                ),
                reporter,
            )
            _error(f"Leg last error: {last_exc}", reporter)
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
        notes = stop_detail or extract_stop_codes(stop_text)
        flights.append(
            LegFlight(
                airline_name=flight.name,
                departure_at=departure_std,
                stops=describe_stops(flight.stops, stop_text),
                stop_notes=notes,
                duration_hours=parse_duration_to_hours(flight.duration),
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
    reporter: Optional[ProgressReporter] = None,
) -> List[ItineraryRow]:
    outbound_flights = fetch_leg_flights(
        config=config,
        origin_code=origin_code,
        destination_code=destination["iata"],
        departure_date=departure_date,
        max_stops=config.max_stops,
        reporter=reporter,
    )
    time.sleep(config.request_delay)
    return_flights = fetch_leg_flights(
        config=config,
        origin_code=destination["iata"],
        destination_code=origin_code,
        departure_date=return_date,
        max_stops=config.max_stops,
        reporter=reporter,
    )
    time.sleep(config.request_delay)
    round_trip_price = fetch_round_trip_price(
        config=config,
        origin_code=origin_code,
        destination_code=destination["iata"],
        departure_date=departure_date,
        return_date=return_date,
        max_stops=config.max_stops,
        reporter=reporter,
    )

    if not outbound_flights or not return_flights:
        _warn(
            (
                f"Itinerary skip {origin_code}->{destination['iata']} "
                f"{departure_date}/{return_date}: empty leg"
            ),
            reporter,
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
                    outbound_duration_hours=outbound.duration_hours,
                    return_departure_at=inbound.departure_at,
                    return_duration_hours=inbound.duration_hours,
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
                    round_trip_price=None,
                )
            )
    if rows and round_trip_price is not None:
        best_index: Optional[int] = None
        best_value: Optional[int] = None
        for idx, row in enumerate(rows):
            if row.total_price is None:
                continue
            if best_value is None or row.total_price < best_value:
                best_index = idx
                best_value = row.total_price
        if best_index is None:
            best_index = 0
        rows[best_index].round_trip_price = round_trip_price

    return rows


def write_csv(rows: Sequence[ItineraryRow], output_path: Path) -> None:
    if not rows:
        _warn("No flight data available to write")
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
    tasks: List[Tuple[str, str, Dict[str, str], str, str, str]] = []
    for origin_name, origin_code in config.origins.items():
        origin_label = origin_name or origin_code
        for destination in config.destinations:
            destination_city = destination.get("city") or destination.get("iata", "?")
            destination_label = f"{destination_city} ({destination.get('iata', '?')})"
            for departure_date, return_date in config.itineraries:
                label = (
                    f"{origin_label} ({origin_code}) → {destination_label} "
                    f"{departure_date}/{return_date} · {config.passenger_count} pax · "
                    f"{config.currency_code}"
                )
                tasks.append((origin_code, origin_label, destination, departure_date, return_date, label))

    total_steps = len(tasks)
    with ProgressReporter(total_steps, config=config) as reporter:
        if config.concurrency <= 1:
            for origin_code, _, destination, departure_date, return_date, label in tasks:
                rows = build_itineraries(
                    config=config,
                    origin_code=origin_code,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    reporter=reporter,
                )
                added = len(rows)
                all_rows.extend(rows)
                if added > 0:
                    reporter.record_success(label, added)
                else:
                    reporter.record_skip(label, "Empty leg")
                time.sleep(config.request_delay)
        else:
            def process_task(task: Tuple[str, str, Dict[str, str], str, str, str]) -> Tuple[str, List[ItineraryRow]]:
                origin_code, _, destination, departure_date, return_date, label = task
                rows = build_itineraries(
                    config=config,
                    origin_code=origin_code,
                    destination=destination,
                    departure_date=departure_date,
                    return_date=return_date,
                    reporter=None,
                )
                return label, rows

            with ThreadPoolExecutor(max_workers=config.concurrency) as executor:
                futures = {executor.submit(process_task, task): task for task in tasks}
                for future in as_completed(futures):
                    label, rows = future.result()
                    added = len(rows)
                    all_rows.extend(rows)
                    if added > 0:
                        reporter.record_success(label, added)
                    else:
                        reporter.record_skip(label, "Empty leg")
    return all_rows


def execute_search(config: SearchConfig) -> List[ItineraryRow]:
    rows = run_search(config)
    if not rows:
        _warn("No flights captured")
        return rows
    write_csv(rows, config.output_path)
    console.log(f"[green]Saved {len(rows)} rows.[/]")
    console.log(f"[green]Output path: {config.output_path}.")
    return rows


__all__ = [
    "SearchConfig",
    "LegFlight",
    "ItineraryRow",
    "run_search",
    "execute_search",
]
