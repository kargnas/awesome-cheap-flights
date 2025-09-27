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
- `outbound_duration_hours`, `return_duration_hours`: decimal hour durations (e.g., 36.5 for 36h 30m).
- `outbound_airline` / `return_airline`: carrier labels from Google Flights.
- `outbound_stops`, `outbound_stop_notes` (and return equivalents): stop counts plus any layover airport IATA codes.
- `outbound_price`, `return_price`: per-leg integer fares (digits only).
- `total_price`: summed outbound + return integers when both legs expose fares, otherwise blank.
- `currency`: ISO code from config/CLI (defaults to `USD`).

## Project layout
- `awesome_cheap_flights/cli.py`: CLI entry point used by the console script/uvx
- `awesome_cheap_flights/__main__.py`: enables `python -m awesome_cheap_flights` invocations
- `awesome_cheap_flights/pipeline.py`: reusable pipeline encapsulating scraping, combination, and CSV export

## Release automation
Push to `main` triggers the `release` workflow automatically with a patch bump, build, publish, tag, and GitHub Release when changes touch `awesome_cheap_flights/*.py`, root-level `*.toml`, or `uv.lock`, and HEAD differs from the last release tag. Use the workflow_dispatch trigger when you need a manual run with `minor` or `current`. Provide a `PYPI_TOKEN` secret with publish rights. Select `current` to reuse the existing version number.

## README (한국어)
### 빠른 실행 (uvx)
1. uv가 없다면 아래 설치 표를 참고해 설치한다.
2. 다음 명령을 실행한다:
```bash
uvx awesome-cheap-flights \\
  --output output/sample.csv \\
  --departure ICN \\
  --destination FUK \\
  --itinerary 2026-01-01:2026-01-04
```
3. 스프레드시트 앱에서 CSV를 열고 `total_price` 기준으로 정렬한다.

`uvx`는 PyPI에서 게시된 패키지를 바로 받아오므로 클론이나 추가 설정이 필요 없다.

### uv 없이 온보딩
| 플랫폼 | uv 설치 | 비고 |
| --- | --- | --- |
| macOS / Linux | `curl -Ls https://astral.sh/uv/install.sh \| sh` | 셸을 재시작한 뒤 `uv --version`으로 설치를 확인한다. |
| Windows (PowerShell) | `powershell -ExecutionPolicy Bypass -Command "iwr https://astral.sh/uv/install.ps1 -useb \| iex"` | OpenSSL 오류가 나면 관리자 권한으로 다시 실행한다. |
| iOS / iPadOS | [iSH](https://ish.app/) 설치 후 내부에서 `apk add curl` 실행, 이어서 위 macOS/Linux 명령 사용. | 크롤링 중에는 iSH를 전면에 둔다. |
| Android | [Termux](https://termux.dev/en/) 설치 후 `pkg install curl`, 이어서 위 macOS/Linux 명령 사용. | 공유 저장소에 CSV를 쓰려면 저장소 권한을 부여한다. |

pip이 더 익숙하면 한 번만 설치한 뒤 콘솔 스크립트를 사용한다:
```bash
pip install awesome-cheap-flights
awesome-cheap-flights --output output/sample.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04
```

### 설정 심화
- 고급 옵션(요청 지연, 재시도 횟수, 구간별 제한)은 YAML에 있다.
- CLI 옵션으로 **departures**, **destinations**, **itineraries**, **output CSV 경로**, `currency`를 덮어쓸 수 있다.
- `#`로 인라인 주석을 달아 공항 메모를 남길 수 있다.
- 프로젝트 루트의 `config.yaml`이 자동으로 로드되며, 없으면 `--config`나 `AWESOME_CHEAP_FLIGHTS_CONFIG` 환경 변수를 사용한다.

### YAML 예시
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
각 여정 항목은 `outbound`/`inbound`(권장) 또는 기존 `departure`/`return`을 사용할 수 있다. 각 필드는 문자열 날짜, 날짜 목록, `{start, end}` 범위를 허용하며 범위는 하루씩 확장되어 가능한 조합을 모두 검색한다.

### 출력 포맷
- `origin_code`, `destination_code`: 검색된 구간의 IATA 코드.
- `outbound_departure_at`, `return_departure_at`: 구글플라이트에서 파싱한 현지 시각.
- `outbound_airline` / `return_airline`: 구글플라이트에서 가져온 항공사 라벨.
- `outbound_stops`, `outbound_stop_notes`(복귀편 포함): 경유 횟수와 경유 정보.
- `outbound_price`, `return_price`: 편도 운임(숫자만).
- `total_price`: 왕복 운임이 둘 다 있을 때 합계, 아니면 빈 칸.
- `currency`: 설정/CLI에서 지정한 ISO 코드(기본 `USD`).

### 프로젝트 구성
- `awesome_cheap_flights/cli.py`: 콘솔 스크립트와 uvx에서 사용하는 진입점.
- `awesome_cheap_flights/__main__.py`: `python -m awesome_cheap_flights` 실행을 지원.
- `awesome_cheap_flights/pipeline.py`: 스크레이핑, 조합, CSV 내보내기를 담당하는 파이프라인.

### 릴리스 자동화
`main` 브랜치에 푸시하면서 `awesome_cheap_flights/*.py`, 루트의 `*.toml`, `uv.lock` 중 하나라도 수정되고 마지막 릴리스 태그와 커밋이 달라졌을 때만 `release` 워크플로가 자동으로 patch 버전을 올려서 빌드, `uvx --from twine twine upload`로 업로드, 태그/푸시, GitHub Release 생성까지 처리한다. 조건이 안 맞으면 릴리스는 스킵된다. `minor`나 `current`가 필요할 땐 workflow_dispatch를 수동 실행해라. 게시 권한이 있는 `PYPI_TOKEN` 시크릿을 제공해야 하며, current는 기존 버전 재사용이다.

## README (中文)
### 快速入门（uvx）
1. 如果还没有安装 uv，请参考下方安装表进行安装。
2. 运行以下命令：
```bash
uvx awesome-cheap-flights \\
  --output output/sample.csv \\
  --departure ICN \\
  --destination FUK \\
  --itinerary 2026-01-01:2026-01-04
```
3. 在表格软件中打开 CSV，并按 `total_price` 排序。

`uvx` 会直接从 PyPI 拉取已发布的包，无需克隆或额外配置。

### 无 uv 上手
| 平台 | 安装 uv | 备注 |
| --- | --- | --- |
| macOS / Linux | `curl -Ls https://astral.sh/uv/install.sh \| sh` | 重启 Shell 后通过 `uv --version` 确认安装。 |
| Windows (PowerShell) | `powershell -ExecutionPolicy Bypass -Command "iwr https://astral.sh/uv/install.ps1 -useb \| iex"` | 遇到 OpenSSL 报错时以管理员身份重试。 |
| iOS / iPadOS | 安装 [iSH](https://ish.app/)，在内部执行 `apk add curl`，然后运行上面的 macOS/Linux 命令。 | 抓取期间保持 iSH 在前台。 |
| Android | 安装 [Termux](https://termux.dev/en/)，执行 `pkg install curl`，然后运行上面的 macOS/Linux 命令。 | 需要写入共享存储的 CSV 时授予存储权限。 |

如果更习惯 pip，可先安装再调用控制台脚本：
```bash
pip install awesome-cheap-flights
awesome-cheap-flights --output output/sample.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04
```

### 配置详解
- 高级参数（请求延迟、重试次数、每段限制）在 YAML 中配置。
- CLI 可覆盖 **departures**、**destinations**、**itineraries**、**输出 CSV 路径** 以及 `currency`。
- 使用 `#` 添加行内注释，方便记录机场信息。
- 项目根目录的 `config.yaml` 会自动载入；若不存在，可使用 `--config` 或环境变量 `AWESOME_CHEAP_FLIGHTS_CONFIG`。

### YAML 示例
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
每个行程可以使用 `outbound`/`inbound`（推荐）或旧版的 `departure`/`return`。各字段支持单个日期、日期列表或 `{start, end}` 范围；范围会按天展开，遍历所有组合。

### 输出格式
- `origin_code`、`destination_code`：查询航段的 IATA 代码。
- `outbound_departure_at`、`return_departure_at`：从 Google Flights 解析出的本地时间。
- `outbound_airline` / `return_airline`：Google Flights 的航司标签。
- `outbound_stops`、`outbound_stop_notes`（返程同理）：经停次数与经停说明。
- `outbound_price`、`return_price`：各航段票价（仅数字）。
- `total_price`：两段票价都存在时的合计，否则留空。
- `currency`：配置/CLI 指定的 ISO 代码（默认 `USD`）。

### 项目结构
- `awesome_cheap_flights/cli.py`：控制台脚本与 uvx 的入口。
- `awesome_cheap_flights/__main__.py`：支持 `python -m awesome_cheap_flights` 调用。
- `awesome_cheap_flights/pipeline.py`：负责抓取、组合与导出 CSV 的核心管线。

### 发布自动化
当推送到 `main` 且改动涉及 `awesome_cheap_flights/*.py`、仓库根目录下的 `*.toml` 或 `uv.lock`，并且 HEAD 与上一次发布标签指向的提交不同，`release` 工作流会自动以 patch 升级、构建、`uvx --from twine twine upload` 上传，并完成打标签、推送和创建 GitHub Release；否则会跳过。若需要 `minor` 或 `current`，使用 workflow_dispatch 手动运行。务必提供具有发布权限的 `PYPI_TOKEN` 机密；选择 `current` 可复用现有版本号。

## README (日本語)
### かんたんスタート（uvx）
1. まだ uv を入れていない場合は下の表を参考にインストールする。
2. 次のコマンドを実行する:
```bash
uvx awesome-cheap-flights \\
  --output output/sample.csv \\
  --departure ICN \\
  --destination FUK \\
  --itinerary 2026-01-01:2026-01-04
```
3. 表計算ソフトで CSV を開き、`total_price` でソートする。

`uvx` は PyPI に公開済みのパッケージを直接取得するため、クローンや追加セットアップは不要。

### uv なしでの導入
| プラットフォーム | uv の入れ方 | メモ |
| --- | --- | --- |
| macOS / Linux | `curl -Ls https://astral.sh/uv/install.sh \| sh` | シェルを再起動し、`uv --version` で確認する。 |
| Windows (PowerShell) | `powershell -ExecutionPolicy Bypass -Command "iwr https://astral.sh/uv/install.ps1 -useb \| iex"` | OpenSSL エラー時は管理者権限で再実行する。 |
| iOS / iPadOS | [iSH](https://ish.app/) を入れ、内部で `apk add curl` 後に上記 macOS/Linux コマンドを実行。 | 取得中は iSH を前面に保つ。 |
| Android | [Termux](https://termux.dev/en/) を入れ、`pkg install curl` 後に上記 macOS/Linux コマンドを実行。 | 共有ストレージへ CSV を保存するなら権限を付与する。 |

pip を使いたい場合は一度インストールしてからコンソールスクリプトを呼び出す:
```bash
pip install awesome-cheap-flights
awesome-cheap-flights --output output/sample.csv --departure ICN --destination FUK --itinerary 2026-01-01:2026-01-04
```

### 設定の詳細
- 高度なパラメータ（リクエスト遅延、リトライ回数、区間ごとの制限）は YAML で管理する。
- CLI では **departures**、**destinations**、**itineraries**、**出力 CSV パス**、`currency` を上書きできる。
- `#` を使って行内コメントを追加し、空港メモを残せる。
- プロジェクト直下の `config.yaml` が自動で読み込まれる。存在しない場合は `--config` か `AWESOME_CHEAP_FLIGHTS_CONFIG` 環境変数を利用する。

### YAML サンプル
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
各行程は `outbound`/`inbound`（推奨）または旧式の `departure`/`return` を指定できる。フィールドには単一日付、日付リスト、`{start, end}` 範囲が使え、範囲は日単位で展開されて全組み合わせを検索する。

### 出力フォーマット
- `origin_code`、`destination_code`: 検索区間の IATA コード。
- `outbound_departure_at`、`return_departure_at`: Google Flights から解析した現地日時。
- `outbound_airline` / `return_airline`: Google Flights の航空会社ラベル。
- `outbound_stops`、`outbound_stop_notes`（復路も同様）: 経由回数と経由情報。
- `outbound_price`、`return_price`: 各区間の運賃（数字のみ）。
- `total_price`: 往復どちらも運賃が取得できた場合の合計、なければ空欄。
- `currency`: 設定や CLI で指定した ISO コード（デフォルトは `USD`）。

### プロジェクト構成
- `awesome_cheap_flights/cli.py`: コンソールスクリプトと uvx のエントリーポイント。
- `awesome_cheap_flights/__main__.py`: `python -m awesome_cheap_flights` の実行を可能にする。
- `awesome_cheap_flights/pipeline.py`: スクレイピング、組み合わせ、CSV 出力を担うパイプライン。

### リリース自動化
`awesome_cheap_flights/*.py`、リポジトリ直下の `*.toml`、`uv.lock` いずれかに変更を含み、直近のリリースタグが指すコミットと HEAD が異なる `main` ブランチへのプッシュで `release` ワークフローが自動実行され、patch バージョンへ更新・ビルドし、`uvx --from twine twine upload` で公開、タグ付けとプッシュ、GitHub Release まで行う。条件を満たさない場合はスキップされる。`minor` や `current` が必要な場合は workflow_dispatch を手動起動すること。公開権限付きの `PYPI_TOKEN` シークレットを必ず設定し、current を選ぶと既存バージョンを再利用できる。

Last commit id: 0c027f640e4fa26fce549ccac43e0fda572e77b5
