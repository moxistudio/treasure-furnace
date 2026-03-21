from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


try:
    import httpx as _httpx  # noqa: F401
except ModuleNotFoundError:
    sys.modules["httpx"] = SimpleNamespace(
        AsyncClient=object,
        HTTPStatusError=Exception,
        RequestError=Exception,
    )


try:
    import openai as _openai  # noqa: F401
except ModuleNotFoundError:
    sys.modules["openai"] = SimpleNamespace(AsyncOpenAI=object)


if "storage" not in sys.modules:
    sys.modules["storage"] = SimpleNamespace(
        get_long_memories=lambda *args, **kwargs: [],
        get_work_logs=lambda *args, **kwargs: [],
    )
