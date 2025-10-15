# Awesome Cheap Flights

![Awesome Cheap Flights logo](assets/logo.png)

Weekend-hopper toolkit for spotting cheap ICN short-hauls without opening browser.

## Highlights
- Hidden-leg discovery merges with regular legs automatically.
- Hidden-leg discovery only bridges a single intermediate stop.
- Plans expand airport pools and date windows per leg.
- Duplicate flights per journey leg collapse into a single row.
- Progress logs now surface a sample flight summary per batch.
- Automatic itinerary workbooks enumerate every leg combination with totals.
- Seat class selector supports economy, premium-economy, business, and first.
- Itinerary sampling knobs and CSV-to-Excel conversion keep exports in your control.
- CSV rows expose variant metadata for hidden journeys.
- CSV rows now include seat_class and hidden-leg departure timestamps.
- Rich logging prints overview tables and elapsed minutes.

## Examples
Example 1. Quick uvx run.
```bash
uvx awesome-cheap-flights@latest --config sample.config.yaml --plan sample-hop
```
Example 2. Local CLI run.
```bash
uv run python -m awesome_cheap_flights.cli --config sample.config.yaml --plan sample-hop
```
Example 3. macOS uv install.
```bash
curl -Ls https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uvx awesome-cheap-flights@latest --config sample.config.yaml --plan sample-hop
```
Example 4. Windows uv install.
```powershell
powershell -ExecutionPolicy Bypass -Command "iwr https://astral.sh/uv/install.ps1 -useb | iex"
uvx awesome-cheap-flights@latest --config sample.config.yaml --plan sample-hop
```
Example 5. Android uv install.
```sh
pkg update
pkg install curl python
curl -Ls https://astral.sh/uv/install.sh | sh
source "$HOME/.local/bin/env"
uvx awesome-cheap-flights@latest --config sample.config.yaml --plan sample-hop
```
After each run, open the CSV and sort by price.

## Development mode
Run the CLI locally for iterative tweaks.
```bash
uv run python -m awesome_cheap_flights.cli --config config.yaml --output output/dev.csv
```
- Copy sample.config.yaml into config.yaml before editing routes.
- Update config.yaml to adjust places, paths, or windows.
- Set UV_CACHE_DIR=$(pwd)/.cache/uv to isolate uv cache.
- Use --output <path> to force a specific CSV file, directory, or pattern. Omit it to keep timestamped files inside output/.
- Combine CLI overrides with commas or repeated flags for airports.
- Use `--csv-only <path>` to turn saved CSVs into fresh itinerary workbooks without re-running searches.
- Sample plan completes within five minutes on modern laptops.

## Troubleshooting
- Upgrade typing_extensions when imports complain about missing features.
- Append --debug for full provider payload dumps during runs.
- Press Ctrl+C to save draft CSV and resume later minutes.
- Update to this revision if `python -m awesome_cheap_flights.cli` printed nothing.
- Install openpyxl>=3.1 if itinerary workbooks fail to generate.

## Configuration
- Set schema_version: v2 to enable the DSL.
- Fill defaults with currency, passenger count, and request minutes.
- Request delay accepts fractional seconds for rate limiting.
- Request seat lets you choose cabin class (economy, premium-economy, business, first).
- Itinerary leg/combo limits (0 = unlimited) tame workbook size without losing control.
- Filters hold max_stops, include_hidden, and max_hidden_hops limits.
- Departures allow per-leg max_stops overrides alongside date selectors.
- Output directory and filename_pattern customize CSV targets.
- Plans list places, path, departures, filters, and options blocks.
- Options include include_hidden toggles and hop caps per plan.
- CLI overrides accept plan, currency, passengers, seat class, itinerary limits, proxy, concurrency, debug.

### YAML sample
```yaml
schema_version: v2
defaults:
  currency: USD
  passengers: 1
  request:
    delay: 0.5
    retries: 1
    max_leg_results: 3
    seat: economy
  filters:
    max_stops: 1
    include_hidden: true
    max_hidden_hops: 1
  output:
    directory: output
    filename_pattern: "{plan}_{timestamp}.csv"
  itinerary:
    leg_limit: 0       # Unlimited per leg; set 10 for a conservative cap.
    max_combinations: 0
plans:
  - name: sample-hop
    places:
      home: [ICN]
      city: [FUK, HKG]
    path: [home, city, home]
    departures:
      "home->city":
        dates: ["2026-01-01", "2026-01-02"]
        max_stops: 0
      "city->home":
        window:
          start: "2026-01-04"
          end: "2026-01-05"
    filters:
      "home->city":
        max_stops: 0
    options:
      include_hidden: true
      max_hidden_hops: 1
http_proxy: null
concurrency: 1
```

Each plan expands airport combinations and departure calendars automatically.

## Output fields
- plan_name marks the source plan for grouping.
- journey_id stores a stable slug per journey.
- journey_label summarizes path and chosen dates.
- variant denotes scheduled legs or hidden discoveries.
- leg_sequence tracks zero-based leg ordering.
- origin_place and destination_place map to place identifiers.
- origin_code and destination_code store airport selections.
- hidden_via_places and hidden_via_codes capture intermediary hops.
- departure_date, departure_time, departure_at hold normalized timestamps.
- duration_hours stores decimal leg durations.
- airline holds the carrier label.
- stops and stop_notes capture layover counts and codes.
- seat_class records the requested cabin per segment.
- hidden_departure_at lists hidden-hop departure times when available.
- price stores integer fare digits.
- is_best mirrors Google Flights highlights.
- currency shows the fare currency code.

## Excel itinerary workbook
- Each run emits `<csv_stem>_itineraries.xlsx` alongside the CSV export.
- Columns follow `<origin_place>-><destination_place>_<field>` naming (e.g., `home->las_price`).
- Per-leg fields cover price, currency, seat_class, departure timestamps (including hidden departures), airline, stops, stop_notes, duration_hours, and variant flags.
- Totals include `total_price`, `total_currency`, and aggregated `total_duration_hours` when data is complete.
- Tune `leg_limit` (flights per leg, 0 = unlimited, 10 recommended) and `max_combinations` (0 = unlimited) to balance coverage versus file size.

## Project layout
- awesome_cheap_flights/cli.py handles CLI parsing and config loading.
- awesome_cheap_flights/__main__.py enables python -m execution.
- awesome_cheap_flights/pipeline.py runs scraping, expansion, and CSV export.

## Release automation
- Pushing main triggers release workflow when relevant files change.
- Append [minor] to bump the minor version automatically.
- Use workflow_dispatch for manual bumps when needed.
- Provide a PYPI_TOKEN secret with publish permissions.
- Select current to reuse the existing version during manual runs.

Last commit id: 2bf372667ca0784a16bf533f05e71d63cc703e50
