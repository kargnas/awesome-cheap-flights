from __future__ import annotations

from pathlib import Path
from typing import List, Optional

import pytest

from awesome_cheap_flights.pipeline import (
    FilterSettings,
    LegDeparture,
    LegFlight,
    OutputSettings,
    PlanConfig,
    PlanOptions,
    PlanRunResult,
    PlanOutput,
    RequestSettings,
    SearchConfig,
    run_plan,
)


def _make_plan() -> PlanConfig:
    return PlanConfig(
        name="demo",
        places={"home": ["ICN"], "via": ["HKG"], "dest": ["SIN"]},
        path=["home", "via", "dest"],
        departures={
            ("home", "via"): LegDeparture(dates=["2026-03-01"]),
            ("via", "dest"): LegDeparture(dates=["2026-03-03"]),
        },
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
    plan.departures[("home", "via")].max_stops = 0
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
