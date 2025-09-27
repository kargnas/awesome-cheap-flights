# Awesome Cheap Flights

Command-line helper that batches short-haul round-trip searches from Seoul Incheon (ICN) to nearby East Asian airports using the `fast-flights` scraping library and exports the combinations to CSV.

## Configuration overview
- Advanced knobs (request delay, retry counts, per-leg limits) live in YAML.
- The CLI only overrides **departures**, **destinations**, **itineraries**, and the **output CSV path**.
- Entries can be bare IATA codes; append inline comments with `#` if you want to note the airport/city name.
- If `config.yaml` exists in the project root, it is picked up automatically; otherwise pass `--config path/to/file.yaml` or set `AWESOME_CHEAP_FLIGHTS_CONFIG`.

## Running the script
Always provide the output path and at least one departure, destination, and itinerary:
```bash
uv run python main.py \
  --output output/sample.csv \
  --departure ICN # Seoul Incheon \
  --destination FUK # Fukuoka \
  --itinerary 2025-10-06:2025-10-09
```
You can also pass YAML-style dictionaries on the CLI, e.g. `--itinerary "{'outbound': {'start': '2025-10-06', 'end': '2025-10-07'}, 'inbound': '2025-10-09'}"` to cover a date window.

## YAML configuration
Point to a YAML file (for development we use `sample.config.yaml`). Supported keys:
```yaml
departures:
  - ICN  # Seoul Incheon
destinations:
  - FUK  # Fukuoka
itineraries:
  - outbound: 2025-10-03
    inbound: 2025-10-05
  - outbound:
      start: 2025-10-06
      end: 2025-10-07
      step: 1
    inbound: 2025-10-09
output_path: output/flights2.csv
request_delay: 1.0
max_retries: 2
max_leg_results: 10
```
Each itinerary entry may contain `outbound`/`inbound` (preferred) or the legacy `departure`/`return`. Each side accepts a string date, a list of dates, or a `{start, end, step}` range; every combination of expanded outbound/inbound dates is searched.

## Output format
The script writes to the path you provide. `departure_date` and `return_date` columns store outbound and inbound departure timestamps in `YYYY-MM-DD HH:MM:SS` format. Stop details and fare breakdowns are captured per leg, and a summed `total_price_label` appears when both fare components are numeric.

## Project layout
- `main.py`: configuration/CLI entry point (YAML + limited flags)
- `awesome_cheap_flights/pipeline.py`: reusable pipeline encapsulating scraping, combination, and CSV export
```
