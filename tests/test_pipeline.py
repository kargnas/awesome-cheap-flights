from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pytest

from awesome_cheap_flights.pipeline import (
    FilterSettings,
    ItinerarySettings,
    LegDeparture,
    LegFlight,
    OutputSettings,
    PlanLeg,
    PlanConfig,
    PlanOptions,
    PlanRunResult,
    PlanOutput,
    RequestSettings,
    SearchConfig,
    SegmentRow,
    _build_plan_itinerary_combinations,
    _build_summary_headers,
    _compose_stop_notes,
    _extract_layover_notes,
    _flight_contains_codes,
    _segment_row_from_mapping,
    run_plan,
    write_csv,
)
from selectolax.lexbor import LexborHTMLParser


def _make_plan() -> PlanConfig:
    return PlanConfig(
        name="demo",
        places={"home": ["ICN"], "via": ["HKG"], "dest": ["SIN"]},
        legs=[
            PlanLeg(
                origin_place="home",
                destination_place="via",
                departure=LegDeparture(dates=["2026-03-01"]),
            ),
            PlanLeg(
                origin_place="via",
                destination_place="dest",
                departure=LegDeparture(dates=["2026-03-03"]),
            ),
        ],
        options=PlanOptions(include_hidden=True, max_hidden_hops=1),
        filters={},
        output=PlanOutput(filename="demo.csv"),
    )


def _make_config(plan: PlanConfig) -> SearchConfig:
    return SearchConfig(
        schema_version="v2",
        currency_code="USD",
        passenger_count=1,
        request=RequestSettings(delay=0.0, retries=1, max_leg_results=5),
        filters=FilterSettings(max_stops=1, include_hidden=True, max_hidden_hops=1),
        output=OutputSettings(directory="output", filename_pattern="{plan}_{timestamp}.csv"),
        itinerary=ItinerarySettings(),
        http_proxy=None,
        concurrency=1,
        debug=False,
        plans=[plan],
    )


def test_run_plan_generates_hidden_rows(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    plan = _make_plan()
    config = _make_config(plan)

    def fake_fetch_leg_flights(**kwargs) -> List[LegFlight]:
        origin = kwargs["origin_code"]
        destination = kwargs["destination_code"]
        if origin == "ICN" and destination == "HKG":
            return [
                LegFlight(
                    airline_name="DemoAir",
                    departure_at="2026-03-01 09:00:00",
                    stops="Nonstop",
                    stop_notes="",
                    duration_hours=3.5,
                    price=150,
                    is_best=True,
                    seat_class="economy",
                    hidden_departure_at="",
                )
            ]
        if origin == "HKG" and destination == "SIN":
            return [
                LegFlight(
                    airline_name="DemoAir",
                    departure_at="2026-03-03 08:00:00",
                    stops="Nonstop",
                    stop_notes="",
                    duration_hours=4.0,
                    price=200,
                    is_best=True,
                    seat_class="economy",
                    hidden_departure_at="",
                )
            ]
        if origin == "ICN" and destination == "SIN":
            return [
                LegFlight(
                    airline_name="HiddenJet",
                    departure_at="2026-03-01 07:30:00",
                    stops="1 stop",
                    stop_notes="HKG",
                    duration_hours=6.5,
                    price=180,
                    is_best=False,
                    seat_class="economy",
                    hidden_departure_at="",
                )
            ]
        return []

    monkeypatch.setattr("awesome_cheap_flights.pipeline.fetch_leg_flights", fake_fetch_leg_flights)

    result: PlanRunResult = run_plan(config, plan)

    assert result.output_path.name.startswith("demo")
    assert len(result.rows) == 3

    scheduled = [row for row in result.rows if row.variant == "scheduled"]
    hidden = [row for row in result.rows if row.variant == "hidden"]

    assert len(scheduled) == 2
    assert len(hidden) == 1
    hidden_row = hidden[0]
    assert hidden_row.hidden_via_codes == "HKG"
    assert hidden_row.origin_code == "ICN"
    assert hidden_row.destination_code == "SIN"
    assert hidden_row.currency == "USD"


def test_departure_max_stops_override(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = _make_plan()
    plan.legs[0].departure.max_stops = 0
    config = _make_config(plan)
    captured: List[tuple[str, str, Optional[int]]] = []

    def fake_fetch_leg_flights(**kwargs) -> List[LegFlight]:
        captured.append(
            (
                kwargs["origin_code"],
                kwargs["destination_code"],
                kwargs.get("max_stops"),
            )
        )
        return []

    monkeypatch.setattr("awesome_cheap_flights.pipeline.fetch_leg_flights", fake_fetch_leg_flights)

    run_plan(config, plan)

    scheduled_call = next(
        max_stops
        for origin, destination, max_stops in captured
        if origin == "ICN" and destination == "HKG"
    )
    assert scheduled_call == 0


def test_summary_headers_include_leg_destination_codes() -> None:
    plan = _make_plan()
    headers = _build_summary_headers(plan, [])
    assert "home->via_destination_code" in headers
    assert "via->dest_destination_code" in headers


def test_hidden_rows_skip_disconnected_surface_gap(monkeypatch: pytest.MonkeyPatch) -> None:
    plan = PlanConfig(
        name="surface-gap",
        places={"icn": ["ICN"], "hkg": ["HKG"], "szx": ["SZX"]},
        legs=[
            PlanLeg(
                origin_place="icn",
                destination_place="hkg",
                departure=LegDeparture(dates=["2026-03-01"]),
            ),
            PlanLeg(
                origin_place="szx",
                destination_place="icn",
                departure=LegDeparture(dates=["2026-03-07"]),
            ),
        ],
        options=PlanOptions(include_hidden=True, max_hidden_hops=1),
        filters={},
        output=PlanOutput(filename="surface-gap.csv"),
    )
    config = _make_config(plan)
    captured: List[tuple[str, str]] = []

    def fake_fetch_leg_flights(**kwargs) -> List[LegFlight]:
        captured.append((kwargs["origin_code"], kwargs["destination_code"]))
        key = (kwargs["origin_code"], kwargs["destination_code"])
        if key == ("ICN", "HKG"):
            return [
                LegFlight(
                    airline_name="DemoAir",
                    departure_at="2026-03-01 09:00:00",
                    stops="Nonstop",
                    stop_notes="",
                    duration_hours=3.5,
                    price=150,
                    is_best=True,
                    seat_class="economy",
                    hidden_departure_at="",
                )
            ]
        if key == ("SZX", "ICN"):
            return [
                LegFlight(
                    airline_name="DemoAir",
                    departure_at="2026-03-07 14:00:00",
                    stops="Nonstop",
                    stop_notes="",
                    duration_hours=3.5,
                    price=160,
                    is_best=True,
                    seat_class="economy",
                    hidden_departure_at="",
                )
            ]
        return []

    monkeypatch.setattr("awesome_cheap_flights.pipeline.fetch_leg_flights", fake_fetch_leg_flights)

    result = run_plan(config, plan)
    scheduled = [row for row in result.rows if row.variant == "scheduled"]
    hidden = [row for row in result.rows if row.variant == "hidden"]

    assert len(scheduled) == 2
    assert len(hidden) == 0
    assert ("HKG", "SZX") not in captured
    assert ("ICN", "ICN") not in captured


def test_layover_notes_prefer_code_and_city_with_duration() -> None:
    html = """
    <li>
      <div class="sSHqwe tPgKwe ogfYpf"
           aria-label="Layover (1 of 2) is a 7 hr 45 min overnight layover at Jinan Yaoqiang International Airport in Jinan. Layover (2 of 2) is a 45 min layover at Wuyishan Airport in Wuyishan."></div>
    </li>
    """
    parser = LexborHTMLParser(html)
    item = parser.css_first("li")
    assert item is not None

    layover_note = _extract_layover_notes(item, "TNA WUS")
    assert layover_note == (
        "TNA Jinan (7 hr 45 min overnight); "
        "WUS Wuyishan (45 min)"
    )

    stop_notes = _compose_stop_notes(
        destination_code="SZX",
        layover_codes="TNA WUS",
        layover_notes=layover_note,
        stop_text="2 stops",
    )
    assert stop_notes.startswith("ARR SZX | STOPOVER ")
    assert "TNA Jinan" in stop_notes
    assert "7 hr 45 min overnight" in stop_notes


def test_hidden_filter_ignores_arrival_code_in_stop_notes() -> None:
    flight = LegFlight(
        airline_name="HiddenJet",
        departure_at="2026-03-01 07:30:00",
        stops="1 stop",
        stop_notes="ARR SZX | STOPOVER HKG Hong Kong (2 hr)",
        duration_hours=6.5,
        price=180,
        is_best=False,
        seat_class="economy",
        hidden_departure_at="",
    )
    assert _flight_contains_codes(flight, ["HKG"])
    assert not _flight_contains_codes(flight, ["SZX"])


def test_write_csv_outputs_na_for_missing_price(tmp_path: Path) -> None:
    row = SegmentRow(
        plan_name="demo",
        journey_id="demo-0001",
        journey_label="demo-0001 ICN->SIN 2026-03-01",
        variant="scheduled",
        leg_sequence=0,
        origin_place="home",
        origin_code="ICN",
        destination_place="dest",
        destination_code="SIN",
        hidden_via_places="",
        hidden_via_codes="",
        departure_date="2026-03-01",
        departure_at="2026-03-01 09:00:00",
        departure_time="09:00",
        duration_hours=6.5,
        airline="DemoAir",
        stops="Nonstop",
        stop_notes="ARR SIN",
        price=None,
        is_best=True,
        currency="USD",
        seat_class="economy",
        hidden_departure_at="",
    )
    csv_path = tmp_path / "rows.csv"
    write_csv([row], csv_path)

    text = csv_path.read_text(encoding="utf-8")
    assert "N/A" in text


def test_itinerary_combinations_show_na_for_missing_leg_price() -> None:
    plan = _make_plan()
    scheduled_rows = [
        SegmentRow(
            plan_name=plan.name,
            journey_id="demo-0001",
            journey_label="demo-0001 ICN->SIN 2026-03-01",
            variant="scheduled",
            leg_sequence=0,
            origin_place="home",
            origin_code="ICN",
            destination_place="via",
            destination_code="HKG",
            hidden_via_places="",
            hidden_via_codes="",
            departure_date="2026-03-01",
            departure_at="2026-03-01 09:00:00",
            departure_time="09:00",
            duration_hours=3.5,
            airline="DemoAir",
            stops="Nonstop",
            stop_notes="ARR HKG",
            price=150,
            is_best=True,
            currency="USD",
            seat_class="economy",
            hidden_departure_at="",
        ),
        SegmentRow(
            plan_name=plan.name,
            journey_id="demo-0001",
            journey_label="demo-0001 ICN->SIN 2026-03-01",
            variant="scheduled",
            leg_sequence=1,
            origin_place="via",
            origin_code="HKG",
            destination_place="dest",
            destination_code="SIN",
            hidden_via_places="",
            hidden_via_codes="",
            departure_date="2026-03-03",
            departure_at="2026-03-03 08:00:00",
            departure_time="08:00",
            duration_hours=4.0,
            airline="DemoAir",
            stops="Nonstop",
            stop_notes="ARR SIN",
            price=None,
            is_best=True,
            currency="USD",
            seat_class="economy",
            hidden_departure_at="",
        ),
    ]

    combos, _, _, _, _ = _build_plan_itinerary_combinations(
        plan,
        scheduled_rows,
        ItinerarySettings(),
    )
    assert len(combos) == 1
    record = combos[0]
    assert record["via->dest_price"] == "N/A"
    assert record["total_price"] == "N/A"


def test_segment_row_parser_accepts_na_price() -> None:
    parsed = _segment_row_from_mapping(
        {
            "plan_name": "demo",
            "journey_id": "demo-0001",
            "journey_label": "demo-0001 ICN->SIN 2026-03-01",
            "variant": "scheduled",
            "leg_sequence": "0",
            "origin_place": "home",
            "origin_code": "ICN",
            "destination_place": "dest",
            "destination_code": "SIN",
            "hidden_via_places": "",
            "hidden_via_codes": "",
            "departure_date": "2026-03-01",
            "departure_at": "2026-03-01 09:00:00",
            "departure_time": "09:00",
            "duration_hours": "6.5",
            "airline": "DemoAir",
            "stops": "Nonstop",
            "stop_notes": "ARR SIN",
            "price": "N/A",
            "is_best": "true",
            "currency": "USD",
            "seat_class": "economy",
            "hidden_departure_at": "",
        }
    )
    assert parsed.price is None
