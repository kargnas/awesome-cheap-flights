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

## Build, Test, and Development Commands
- `uvx awesome-cheap-flights --help`: Smoke-check the published CLI.
- `uv run python -m awesome_cheap_flights.cli --config sample.config.yaml --output output/demo.csv`: Executes a lightweight search using the sample config.
- `uv run python -m awesome_cheap_flights.cli --output output/full.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04`: Direct CLI run overriding config-specified values.
- `uv lock`: Refreshes dependency lockfile after editing `pyproject.toml`.

## Coding Style & Naming Conventions
- Python 3.10+, PEP 8 defaults; prefer 4-space indentation and descriptive snake_case identifiers.
- Keep CLI/YAML keys in lowercase plural form (`departures`, `destinations`, `itineraries`).
- YAML comment style must use `#`; inline annotations go after the IATA code (e.g., `ICN # Seoul Incheon`).

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

## Release / Publishing
- `scripts/bump_version.py --level {patch|minor|major}` updates `pyproject.toml` and writes the new version to stdout (and optional file).
- `.github/workflows/release.yml` bumps the chosen level, builds with `uv tool run --from build pyproject-build --wheel --sdist`, uploads via `uvx --from twine twine upload`, then tags/pushes/drafts the GitHub Release.
- Provide `PYPI_TOKEN` in repo secrets with upload scope.

Last commit id: 93018d0ca7cda0b508f3e68d7dd45485f49963f6
