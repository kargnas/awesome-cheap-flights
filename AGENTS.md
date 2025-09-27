# Repository Guidelines

<writing_style />
- Tone: UI용 간결체 영어, 예시 4-5 사용
- Rule: 문장 길이 최대 12단어, 시간 안내 시 분 단위 표기
- Rule: 문장 끝은 마침표로 마무리
- Example: Summary delayed. Retry in about 5 min.


## Project Structure & Module Organization
- `main.py`: CLI entry point that loads YAML config (defaults to `config.yaml`) and wires options to the pipeline.
- `awesome_cheap_flights/pipeline.py`: Core scraping/search pipeline including data structures, HTML parsing, and CSV export utilities.
- `sample.config.yaml`: Minimal example config used for smoke tests; copy to `config.yaml` for local overrides.
- `output/`: Git-ignored directory for generated CSV files (only tracked when explicitly whitelisted).

## Build, Test, and Development Commands
- `uv run python main.py --config sample.config.yaml --output output/demo.csv`: Executes a lightweight search using the sample config.
- `uv run python main.py --output output/full.csv --departure ICN --destination FUK --itinerary 2025-10-06:2025-10-09`: Direct CLI run overriding config-specified values.
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

## Configuration Tips
- Store local secrets or large route lists in `config.yaml` (git-ignored). Use `sample.config.yaml` only for reproducible smoke tests.
- Prefer `outbound` / `inbound` keys for itineraries; ranges are specified via `{start, end, step}` blocks.
