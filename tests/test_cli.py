from __future__ import annotations

from argparse import Namespace
from pathlib import Path

import pytest

from awesome_cheap_flights.cli import build_config


def _build_args(config_path: Path) -> Namespace:
    return Namespace(
        config=str(config_path),
        plan=None,
        currency=None,
        passengers=None,
        http_proxy=None,
        concurrency=None,
        seat_class=None,
        itinerary_leg_limit=None,
        itinerary_max_combos=None,
        csv_only=None,
        output=None,
        debug=False,
    )


def test_build_config_parses_v2_schema(tmp_path: Path) -> None:
    config_path = tmp_path / "config.yaml"
    config_path.write_text(
        """
        {
          "schema_version": "v2",
          "defaults": {
            "currency": "KRW",
            "passengers": 2,
            "request": {
              "delay": 0.2,
              "retries": 3,
              "max_leg_results": 4
            },
            "filters": {
              "max_stops": 1,
              "include_hidden": false,
              "max_hidden_hops": 1
            },
            "output": {
              "directory": "output",
              "filename_pattern": "{plan}_{timestamp}.csv"
            }
          },
          "plans": [
            {
              "name": "demo",
              "places": {
                "home": ["ICN"],
                "beach": ["CEB"]
              },
              "departures": {
                "home->beach": {
                  "dates": ["2026-03-01", "2026-03-02"]
                }
              }
            }
          ]
        }
        """,
        encoding="utf-8",
    )
    args = _build_args(config_path)

    config = build_config(args)

    assert config.schema_version == "v2"
    assert config.currency_code == "KRW"
    assert config.passenger_count == 2
    assert config.request.delay == 0.2
    assert config.request.retries == 3
    assert config.request.max_leg_results == 4
    assert config.filters.max_stops == 1
    assert config.filters.include_hidden is False
    assert config.output.directory.name == "output"
    assert len(config.plans) == 1
    plan = config.plans[0]
    assert plan.name == "demo"
    assert plan.places["home"] == ["ICN"]
    assert len(plan.legs) == 1
    leg = plan.legs[0]
    assert leg.origin_place == "home"
    assert leg.destination_place == "beach"
    assert leg.departure.dates == ["2026-03-01", "2026-03-02"]
    assert leg.departure.max_stops is None


def test_build_config_rejects_legacy_path(tmp_path: Path) -> None:
    config_path = tmp_path / "legacy-path.yaml"
    config_path.write_text(
        """
schema_version: v2
plans:
  - name: legacy
    places:
      a: [ICN]
      b: [HKG]
    path: [a, b]
    departures:
      "a->b":
        dates: ["2026-03-01"]
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="deprecated 'path'"):
        build_config(_build_args(config_path))


def test_build_config_rejects_unknown_departure_place(tmp_path: Path) -> None:
    config_path = tmp_path / "unknown-place.yaml"
    config_path.write_text(
        """
schema_version: v2
plans:
  - name: bad
    places:
      home: [ICN]
    departures:
      "home->missing":
        dates: ["2026-03-01"]
        """,
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="undefined place 'missing'"):
        build_config(_build_args(config_path))
