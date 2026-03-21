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

import asyncio

from treasure_forge import TreasureForge


def test_treasure_forge_maps_local_fs_tools(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: File Scout
description: 读取目录和文本文件
allowed-tools: file_list read_text file_move mkdir
---
请先列目录，再读文本文件，必要时移动文件。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="SKILL.md"))

    assert preview.mapped_tools == [
        "local_fs_list_dir",
        "local_fs_read_text",
        "local_fs_move",
        "local_fs_mkdir",
    ]
    assert any(flag["code"] == "risky_tool" for flag in preview.risk_flags)
