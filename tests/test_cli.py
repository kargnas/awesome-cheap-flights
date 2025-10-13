from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from awesome_cheap_flights.cli import build_config


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
              "path": ["home", "beach"],
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
    args = Namespace(
        config=str(config_path),
        plan=None,
        currency=None,
        passengers=None,
        http_proxy=None,
        concurrency=None,
        debug=False,
    )

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
    leg = plan.departures[("home", "beach")]
    assert leg.dates == ["2026-03-01", "2026-03-02"]
    assert leg.max_stops is None
