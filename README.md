# Awesome Cheap Flights

Weekend-hopper toolkit for spotting cheap ICN short-hauls without opening a browser.

## Quick win (uvx)
1. Grab uv if you do not already have it (see the install table below).
2. Run:
```bash
uvx awesome-cheap-flights   --output output/sample.csv   --departure ICN   --destination FUK   --itinerary 2026-01-01:2026-01-04
```
3. Crack open the CSV in your spreadsheet app and sort by `total_price_label`.

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
- CLI overrides cover **departures**, **destinations**, **itineraries**, and the **output CSV path**.
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
```
Each itinerary entry may contain `outbound`/`inbound` (preferred) or the legacy `departure`/`return`. Each side accepts a string date, a list of dates, or a `{start, end}` range that expands one day at a time; every combination of expanded outbound/inbound dates is searched.

## Output format
CSV headers include `departure_date`, `return_date`, airline, stop details, per-leg fares, and a computed `total_price_label` when numeric values are present.

## Project layout
- `awesome_cheap_flights/cli.py`: CLI entry point used by the console script/uvx
- `awesome_cheap_flights/__main__.py`: enables `python -m awesome_cheap_flights` invocations
- `awesome_cheap_flights/pipeline.py`: reusable pipeline encapsulating scraping, combination, and CSV export

## Release automation
Trigger the `release` GitHub Actions workflow (workflow_dispatch) to bump the version (patch by default, with minor/major options), build wheels via `uvx build`, push them with `uvx twine upload`, tag, push, and open a GitHub Release. Provide a `PYPI_TOKEN` secret with publish rights.

Last commit id: 3f9586824e15e3a7fc6f1787a6d98621b9a992f6
