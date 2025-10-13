from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _install_fast_flights_stub() -> None:
    import types

    if "fast_flights" in sys.modules:
        return

    fast_flights = types.ModuleType("fast_flights")

    class _Dummy:
        def __init__(self, *args, **kwargs) -> None:
            self.__dict__.update(kwargs)

    class _DummyResult:
        def __init__(self) -> None:
            self.flights = []

    fast_flights.FlightData = _Dummy
    fast_flights.Passengers = _Dummy
    fast_flights.Result = _DummyResult

    core = types.ModuleType("fast_flights.core")
    core.parse_response = lambda *args, **kwargs: _DummyResult()

    fallback = types.ModuleType("fast_flights.fallback_playwright")
    fallback.CODE = "print('fallback')"

    class _DummyTFS:
        @classmethod
        def from_interface(cls, *args, **kwargs):
            return cls()

        def as_b64(self) -> bytes:
            return b""

    flights_impl = types.ModuleType("fast_flights.flights_impl")
    flights_impl.TFSData = _DummyTFS

    class _DummyClient:
        def __init__(self, *args, **kwargs) -> None:
            self.status_code = 200

        def get(self, *args, **kwargs):
            return types.SimpleNamespace(status_code=200, text="", text_markdown="")

        def post(self, *args, **kwargs):
            return types.SimpleNamespace(status_code=200, text="{}", text_markdown="{}")

    primp = types.ModuleType("fast_flights.primp")
    primp.Client = _DummyClient

    sys.modules["fast_flights"] = fast_flights
    sys.modules["fast_flights.core"] = core
    sys.modules["fast_flights.fallback_playwright"] = fallback
    sys.modules["fast_flights.flights_impl"] = flights_impl
    sys.modules["fast_flights.primp"] = primp


_install_fast_flights_stub()


def _install_selectolax_stub() -> None:
    import types

    if "selectolax.lexbor" in sys.modules:
        return

    selectolax = types.ModuleType("selectolax")
    lexbor = types.ModuleType("selectolax.lexbor")

    class _DummyParser:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def css(self, *args, **kwargs):
            return []

        def css_first(self, *args, **kwargs):
            return None

    lexbor.LexborHTMLParser = _DummyParser

    sys.modules["selectolax"] = selectolax
    sys.modules["selectolax.lexbor"] = lexbor


_install_selectolax_stub()


def _install_rich_stub() -> None:
    import types

    if "rich" in sys.modules:
        return

    rich = types.ModuleType("rich")

    console_mod = types.ModuleType("rich.console")

    class _DummyConsole:
        def __init__(self, *args, **kwargs) -> None:
            self.is_terminal = False

        def log(self, *args, **kwargs) -> None:
            pass

        def print(self, *args, **kwargs) -> None:
            pass

    console_mod.Console = _DummyConsole

    markup_mod = types.ModuleType("rich.markup")
    markup_mod.escape = lambda value: value

    progress_mod = types.ModuleType("rich.progress")

    class _DummyColumn:
        def __init__(self, *args, **kwargs) -> None:
            pass

    class _DummyProgress:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def __enter__(self):
            return self

        def __exit__(self, *exc_info) -> None:
            pass

        def add_task(self, *args, **kwargs):
            return 1

        def update(self, *args, **kwargs) -> None:
            pass

        def log(self, *args, **kwargs) -> None:
            pass

    progress_mod.Progress = _DummyProgress
    progress_mod.SpinnerColumn = _DummyColumn
    progress_mod.TextColumn = _DummyColumn
    progress_mod.BarColumn = _DummyColumn
    progress_mod.TaskProgressColumn = _DummyColumn
    progress_mod.TimeElapsedColumn = _DummyColumn
    progress_mod.TimeRemainingColumn = _DummyColumn

    table_mod = types.ModuleType("rich.table")

    class _DummyTable:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def add_column(self, *args, **kwargs) -> None:
            pass

        def add_row(self, *args, **kwargs) -> None:
            pass

    table_mod.Table = _DummyTable

    box_mod = types.ModuleType("rich.box")
    box_mod.SIMPLE_HEAD = object()

    sys.modules["rich"] = rich
    sys.modules["rich.console"] = console_mod
    sys.modules["rich.markup"] = markup_mod
    sys.modules["rich.progress"] = progress_mod
    sys.modules["rich.table"] = table_mod
    sys.modules["rich.box"] = box_mod


_install_rich_stub()


def _install_yaml_stub() -> None:
    import json
    import types

    if "yaml" in sys.modules:
        return

    yaml = types.ModuleType("yaml")
    yaml.safe_load = lambda stream: json.loads(stream.read()) if hasattr(stream, "read") else json.loads(stream)

    sys.modules["yaml"] = yaml


_install_yaml_stub()
