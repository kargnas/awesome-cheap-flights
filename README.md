# Awesome Cheap Flights

[![release](https://github.com/kargnas/awesome-cheap-flights/actions/workflows/release.yml/badge.svg?branch=main)](https://github.com/kargnas/awesome-cheap-flights/actions/workflows/release.yml)

Weekend-hopper toolkit for spotting cheap ICN short-hauls without opening a browser.

## Quick win (uvx)
1. Grab uv if you do not already have it (see the install table below).
2. Run:
```bash
uvx awesome-cheap-flights \
  --output output/sample.csv \
  --departure ICN \
  --destination FUK \
  --itinerary 2026-01-01:2026-01-04
```
3. Crack open the CSV in your spreadsheet app and sort by `total_price`.

`uvx` pulls the published package from PyPI, so there is no clone or setup step.

## No-uv onboarding
| Platform | Install uv | Notes |
| --- | --- | --- |
| macOS / Linux | `curl -Ls https://astral.sh/uv/install.sh \| sh` | Restart shell, `uv --version` to confirm. |
| Windows (PowerShell) | `powershell -ExecutionPolicy Bypass -Command "iwr https://astral.sh/uv/install.ps1 -useb \| iex"` | Openssl fix? Run in admin if needed. |
| iOS / iPadOS | Install [iSH](https://ish.app/), then inside: `apk add curl` followed by the macOS/Linux command above. | Keep iSH in foreground while scraping. |
| Android | Install [Termux](https://termux.dev/en/), run `pkg install curl`, then use the macOS/Linux command. | Grant storage if you want CSV on shared storage. |

Prefer pip? Install once and use the console script:
```bash
pip install awesome-cheap-flights
awesome-cheap-flights --output output/sample.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04
```

## Configuration deep dive
- Advanced knobs (request delay, retry counts, per-leg limits) live in YAML.
- CLI overrides cover **departures**, **destinations**, **itineraries**, the **output CSV path**, and `currency`.
- Inline comments with `#` keep airport notes readable.
- `config.yaml` in the project root is picked up automatically; otherwise use `--config` or set `AWESOME_CHEAP_FLIGHTS_CONFIG`.

### YAML sample
```yaml
departures:
  - ICN  # Seoul Incheon
destinations:
  - FUK  # Fukuoka
itineraries:
  - outbound: 2026-01-01
    inbound: 2026-01-03
  - outbound:
      start: 2026-01-02
      end: 2026-01-03
    inbound: 2026-01-05
output_path: output/flights2.csv
request_delay: 1.0
max_retries: 2
max_leg_results: 10
currency: USD
```
Each itinerary entry may contain `outbound`/`inbound` (preferred) or the legacy `departure`/`return`. Each side accepts a string date, a list of dates, or a `{start, end}` range that expands one day at a time; every combination of expanded outbound/inbound dates is searched.

## Output format
Each row contains these fields:
- `origin_code`, `destination_code`: IATA codes for the searched pair.
- `outbound_departure_at`, `return_departure_at`: normalized timestamps (local date/time parsed from Google Flights).
- `outbound_airline` / `return_airline`: carrier labels from Google Flights.
- `outbound_stops`, `outbound_stop_notes` (and return equivalents): stop counts plus layover snippets when available.
- `outbound_price`, `return_price`: per-leg integer fares (digits only).
- `total_price`: summed outbound + return integers when both legs expose fares, otherwise blank.
- `currency`: ISO code from config/CLI (defaults to `USD`).

## Project layout
- `awesome_cheap_flights/cli.py`: CLI entry point used by the console script/uvx
- `awesome_cheap_flights/__main__.py`: enables `python -m awesome_cheap_flights` invocations
- `awesome_cheap_flights/pipeline.py`: reusable pipeline encapsulating scraping, combination, and CSV export

## Release automation
Trigger the `release` GitHub Actions workflow (workflow_dispatch) to bump the version (patch by default, with minor/current options), build wheels via `uv tool run --from build pyproject-build --wheel --sdist`, push them with `uvx --from twine twine upload`, tag, push, and open a GitHub Release. Provide a `PYPI_TOKEN` secret with publish rights. Select current to reuse the existing version number.

Last commit id: ca198005ee5a9a8eaa69fa9ff40f0cfd765f4ce9
