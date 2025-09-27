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
- `main.py`: Compatibility shim that forwards to `awesome_cheap_flights.cli`.
- `awesome_cheap_flights/cli.py`: CLI arguments + config loader for console script and uvx runs.
- `awesome_cheap_flights/pipeline.py`: Core scraping/search pipeline including data structures, HTML parsing, and CSV export utilities.
- `sample.config.yaml`: Minimal example config used for smoke tests; copy to `config.yaml` for local overrides.
- `output/`: Git-ignored directory for generated CSV files (only tracked when explicitly whitelisted).

## Build, Test, and Development Commands
- `uvx awesome-cheap-flights --help`: Smoke-check the published CLI.
- `uv run python main.py --config sample.config.yaml --output output/demo.csv`: Executes a lightweight search using the sample config.
- `uv run python main.py --output output/full.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04`: Direct CLI run overriding config-specified values.
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
- ALWAYS update README.md and AGENTS.md after modifications of logics. (Write the LATEST commit id on the end of the document, and update the documents by looking at the commits after that commit id everytime when you update the document)

## Configuration Tips
- Store local secrets or large route lists in `config.yaml` (git-ignored). Use `sample.config.yaml` only for reproducible smoke tests.
- Prefer `outbound` / `inbound` keys for itineraries; ranges are specified via `{start, end}` blocks.

## Release / Publishing
- `scripts/bump_version.py --level {patch|minor|major}` updates `pyproject.toml` and writes the new version to stdout (and optional file).
- `.github/workflows/release.yml` bumps the chosen level, publishes to PyPI via `uv publish`, tags, pushes, and drafts the GitHub Release.
- The workflow expects `PYPI_TOKEN` in repo secrets with upload scope.

Last commit id: 3f9586824e15e3a7fc6f1787a6d98621b9a992f6
