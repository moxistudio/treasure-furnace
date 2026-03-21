from __future__ import annotations

import sys
from types import SimpleNamespace

try:
    import httpx as _httpx  # noqa: F401
except ModuleNotFoundError:
    sys.modules["httpx"] = SimpleNamespace(
        AsyncClient=object,
        HTTPStatusError=Exception,
        RequestError=Exception,
    )

from treasure_forge import _RISKY_TOOL_MAP, _SAFE_TOOL_MAP


def test_expanded_safe_tool_aliases() -> None:
    assert _SAFE_TOOL_MAP["tavily_search"] == "web_search"
    assert _SAFE_TOOL_MAP["perplexity"] == "web_search"
    assert _SAFE_TOOL_MAP["exa_search"] == "web_search"
    assert _SAFE_TOOL_MAP["serper"] == "web_search"
    assert _SAFE_TOOL_MAP["brave_search"] == "web_search"
    assert _SAFE_TOOL_MAP["playwright_navigate"] == "browser_open"
    assert _SAFE_TOOL_MAP["puppeteer_navigate"] == "browser_open"
    assert _SAFE_TOOL_MAP["playwright_screenshot"] == "browser_screenshot"
    assert _SAFE_TOOL_MAP["read_file"] == "file_read"
    assert _SAFE_TOOL_MAP["list_files"] == "file_read"
    assert _SAFE_TOOL_MAP["glob"] == "file_read"
    assert _SAFE_TOOL_MAP["ripgrep"] == "file_read"
    assert _SAFE_TOOL_MAP["jina_reader"] == "web_fetch"
    assert _SAFE_TOOL_MAP["firecrawl"] == "web_fetch"


def test_expanded_risky_tool_aliases() -> None:
    assert _RISKY_TOOL_MAP["subprocess"] == "shell_exec"
    assert _RISKY_TOOL_MAP["os_exec"] == "shell_exec"
    assert _RISKY_TOOL_MAP["spawn"] == "shell_exec"
    assert _RISKY_TOOL_MAP["popen"] == "shell_exec"


def test_existing_aliases_not_broken() -> None:
    assert _SAFE_TOOL_MAP["google"] == "web_search"
    assert _SAFE_TOOL_MAP["browse"] == "browser_open"
    assert _RISKY_TOOL_MAP["bash"] == "shell_exec"
