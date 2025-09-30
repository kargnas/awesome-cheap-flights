# Repository Guidelines

<writing_style>
- Tone: Concise English for UI.
- Use 4-5 examples.
- Rule: Max 12 words per sentence.
- Rule: Time info in minutes.
- Rule: End each sentence with a period.
- Example: Summary delayed. Retry in about 5 min.
</writing_style>


## Project Structure & Module Organization
- `awesome_cheap_flights/cli.py`: CLI arguments + config loader for console script and uvx runs.
- `awesome_cheap_flights/__main__.py`: Enables `python -m awesome_cheap_flights` compatibility.
- `awesome_cheap_flights/pipeline.py`: Core scraping/search pipeline including data structures, HTML parsing, and CSV export utilities.
- `sample.config.yaml`: Minimal example config used for smoke tests; copy to `config.yaml` for local overrides.
- `output/`: Git-ignored directory for generated CSV files (only tracked when explicitly whitelisted).

## Logging & Observability
- Pipeline logs now flow through a shared Rich console with color-coded warnings and errors.
- `run_search` drives a Rich progress bar (TTY only) that advances per itinerary pair and logs row deltas.
- Non-interactive sessions fall back to concise text logs on stderr while preserving the same counts.
- A summary table prints after each run with processed itineraries, skips, rows collected, and elapsed minutes.
- A search overview table is emitted upfront listing origin codes, destination codes, pax, currency, and other knobs; each iteration label repeats route, pax, and currency for quick scanning.

## Build, Test, and Development Commands
- `uvx awesome-cheap-flights --help`: Smoke-check the published CLI.
- `uv run python -m awesome_cheap_flights.cli --config sample.config.yaml --output output/demo.csv`: Executes a lightweight search using the sample config.
- `uv run python -m awesome_cheap_flights.cli --output output/full.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04`: Direct CLI run overriding config-specified values.
- `uv lock`: Refreshes dependency lockfile after editing `pyproject.toml`.

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8 defaults; prefer 4-space indentation and descriptive snake_case identifiers.
- Keep CLI/YAML keys in lowercase plural form (`departures`, `destinations`, `itineraries`).
- YAML comment style must use `#`; inline annotations go after the IATA code (e.g., `ICN # Seoul Incheon`).
- Rich-powered logging is part of the packaging footprint; keep `rich>=13.7` declared in `pyproject.toml` when adjusting deps.
- CLI accepts comma-separated inputs (e.g., `--departure ICN,GMP`) and the legacy `Name:CODE` syntax has been removed.

## Testing Guidelines
- No automated tests yet; validate changes by running the sample config and inspecting generated CSV size and headers.
- When adding parsing logic, craft targeted configs in `sample.config.yaml` to reproduce new branches before committing.

## Commit & Pull Request Guidelines
- Follow existing concise, imperative commit style (e.g., “Switch to departures/arrivals config with pure IATA codes”).
- Each PR should include: summary of changes, CLI command used for verification, any config updates, and links to related issues.
- Keep CSV artifacts out of version control unless required for review; share sample outputs via temporary paths or gists.
- ALWAYS update README.md and AGENTS.md whenever you touch project logic. After your edits run `git rev-parse HEAD` and replace the final `Last commit id:` line in both files with that hash (exactly once per file).
- If the hash changes while you keep editing, refresh the `Last commit id:` line again before you finish.
- NEVER use `git add .`, add all the files manually by mentioning the file names.

## Configuration Tips
- Store local secrets or large route lists in `config.yaml` (git-ignored). Use `sample.config.yaml` only for reproducible smoke tests.
- Prefer `outbound` / `inbound` keys for itineraries; ranges are specified via `{start, end}` blocks.
- Set the top-level `currency` key (uppercase ISO code) when you need fares labeled in something other than USD.
- Use the `passengers` key to control the number of adult seats (defaults to 1).
- Clamp layovers with `max_stops` (0=nonstop, 1=one stop, 2=two stops).
- Legacy `departure`/`return` itinerary keys are removed; only `outbound`/`inbound` are valid now.
- If neither CLI nor YAML sets an output path, the run writes to `output/<local timestamp>_<TZ>.csv`.

## Release / Publishing
- `scripts/bump_version.py --level {patch|minor|current}` updates `pyproject.toml` and writes the new version to stdout (and optional file). Use `current` to reuse the existing version.
- `.github/workflows/release.yml` auto-runs on pushes to `main` with a patch bump when changes touch `awesome_cheap_flights/*.py`, root `*.toml`, or `uv.lock`, and HEAD differs from the last release tag; it builds with `uv tool run --from build pyproject-build --wheel --sdist`, uploads via `uvx --from twine twine upload`, then tags/pushes/drafts the GitHub Release. Manually dispatch when you need `minor` or `current`.
- Provide `PYPI_TOKEN` in repo secrets with upload scope.

Last commit id: da8db682d8ecb073ee15601073ca786efcbee654
