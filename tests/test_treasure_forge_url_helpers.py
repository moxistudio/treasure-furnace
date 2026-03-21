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

from treasure_forge import TreasureForge


def test_github_blob_url() -> None:
    blob = TreasureForge._github_raw_candidates(
        "https://github.com/user/repo/blob/main/runtime_assets/foo/pack.yaml"
    )

    assert blob == ["https://raw.githubusercontent.com/user/repo/main/runtime_assets/foo/pack.yaml"]


def test_github_tree_url() -> None:
    tree = TreasureForge._github_raw_candidates("https://github.com/user/repo/tree/main/agents/foo")

    assert tree == [
        "https://raw.githubusercontent.com/user/repo/main/agents/foo/pack.yaml",
        "https://raw.githubusercontent.com/user/repo/main/agents/foo/pack.yml",
        "https://raw.githubusercontent.com/user/repo/main/agents/foo/SKILL.md",
        "https://raw.githubusercontent.com/user/repo/main/agents/foo/skill.md",
        "https://raw.githubusercontent.com/user/repo/main/agents/foo/instructions.txt",
        "https://raw.githubusercontent.com/user/repo/main/agents/foo/README.md",
    ]


def test_github_root_url() -> None:
    root = TreasureForge._github_raw_candidates("https://github.com/user/repo")

    assert root == [
        "https://raw.githubusercontent.com/user/repo/main/pack.yaml",
        "https://raw.githubusercontent.com/user/repo/main/pack.yml",
        "https://raw.githubusercontent.com/user/repo/main/SKILL.md",
        "https://raw.githubusercontent.com/user/repo/main/skill.md",
        "https://raw.githubusercontent.com/user/repo/main/instructions.txt",
        "https://raw.githubusercontent.com/user/repo/main/README.md",
        "https://raw.githubusercontent.com/user/repo/master/pack.yaml",
        "https://raw.githubusercontent.com/user/repo/master/pack.yml",
        "https://raw.githubusercontent.com/user/repo/master/SKILL.md",
        "https://raw.githubusercontent.com/user/repo/master/skill.md",
        "https://raw.githubusercontent.com/user/repo/master/instructions.txt",
        "https://raw.githubusercontent.com/user/repo/master/README.md",
        "https://raw.githubusercontent.com/user/repo/HEAD/pack.yaml",
        "https://raw.githubusercontent.com/user/repo/HEAD/pack.yml",
        "https://raw.githubusercontent.com/user/repo/HEAD/SKILL.md",
        "https://raw.githubusercontent.com/user/repo/HEAD/skill.md",
        "https://raw.githubusercontent.com/user/repo/HEAD/instructions.txt",
        "https://raw.githubusercontent.com/user/repo/HEAD/README.md",
    ]


def test_github_raw_url() -> None:
    raw_url = "https://raw.githubusercontent.com/user/repo/main/runtime_assets/foo/pack.yaml"
    result = TreasureForge._github_raw_candidates(raw_url)

    assert result == [raw_url]


def test_treasure_forge_github_raw_candidates_non_github_urls() -> None:
    other_url = "https://example.com/skill.md"
    result = TreasureForge._github_raw_candidates(other_url)

    assert result == [other_url]
