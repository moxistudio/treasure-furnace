from __future__ import annotations

import json
import sys
from types import SimpleNamespace

import yaml

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

import asyncio

from adapters.agent_executor import RuntimePlanExecutor
from adapters.agent_registry import AgentRegistry
from treasure_forge import TreasureForge


def test_treasure_forge_accepts_space_separated_allowed_tools_with_extra_spaces(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: Spacey Scout
description: 测试空格分隔工具解析
allowed-tools:   web_search    browser_read
---
请搜索后再读页面内容。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="SKILL.md"))

    assert preview.tools[:2] == ["web_search", "browser_read"]


def test_treasure_forge_maps_browser_skill_to_steps(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: Site Snapshot
description: 打开网页并截图
allowed-tools: browser_open browser_screenshot
---
打开页面后给我一张截图。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="SKILL.md"))

    assert preview.executor_type == "builtin"
    assert preview.tools[:2] == ["browser_open", "browser_screenshot"]
    assert [step["action"] for step in preview.spec["steps"]] == [
        "browser_open",
        "browser_screenshot",
        "send_to_user",
    ]
    assert preview.spec["steps"][1]["params"]["session_id"] == "{{open.session_id}}"


def test_treasure_forge_infers_marshal_for_code_skill(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: Repo Fixer
description: 修改代码并执行命令
allowed-tools: bash code_interpreter
---
请分析仓库并直接修复问题。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="SKILL.md"))

    assert preview.executor_type == "marshal"
    assert preview.trust_level == "confirm"
    assert preview.spec["steps"][0]["action"] == "send_to_user"


def test_treasure_forge_install_writes_package_outputs(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: Weekly Coach
description: 帮我做一页周复盘
---
你是一个简洁的周复盘教练。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="SKILL.md"))
    result = forge.install_preview(preview)

    assert result.package_dir is not None and result.package_dir.exists()
    assert result.pack_yaml_path is not None and result.pack_yaml_path.exists()
    assert result.skill_md_path is not None and result.skill_md_path.exists()

    pack_data = yaml.safe_load(result.pack_yaml_path.read_text(encoding="utf-8"))
    assert pack_data["meta"]["id"] == result.agent_id
    assert pack_data["meta"]["kind"] == "treasure"
    assert pack_data["skill"]["entry"] == "SKILL.md"
    assert [step["action"] for step in pack_data["runtime"]["steps"]] == [
        step["action"] for step in preview.spec["steps"]
    ]

    registry = AgentRegistry(tmp_path / "agents")
    loaded = registry.load_all()
    assert result.agent_id in loaded.agents


def test_runtime_executor_template_supports_json_field_access() -> None:
    rendered = RuntimePlanExecutor._render_template(
        "session={{open.session_id}} url={{open.url}} raw={{open.result}}",
        ctx={},
        step_results={
            "open": '{"ok": true, "session_id": "bs_123", "url": "https://github.com"}'
        },
    )

    assert rendered == 'session=bs_123 url=https://github.com raw={"ok": true, "session_id": "bs_123", "url": "https://github.com"}'


def test_treasure_forge_preview_surfaces_creator_suggestions(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: Study Translator
description: 英语学习里的翻译与讲解助手
---
请帮用户翻译英文句子，并解释关键短语。"""

    preview = asyncio.run(
        forge.preview_from_text(
            content,
            source_name="SKILL.md",
            source_files={"SKILL.md": content, "glossary_terms.md": "cache=缓存"},
        )
    )

    rendered = preview.render_text()

    assert "建议 runtime：builtin" in rendered
    assert "建议知识绑定：" in rendered
    assert "建议场景覆盖点：" in rendered
    assert "glossary" in preview.knowledge_suggestions["suggested"]
    assert any(item["scene"] == "study_buddy" for item in preview.scene_suggestions)


def test_treasure_forge_install_writes_creator_artifacts(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: Research Pack
description: 读取附带资料并产出调研摘要
allowed-tools: web_search
---
请结合附带资料完成调研总结。"""

    preview = asyncio.run(
        forge.preview_from_text(
            content,
            source_name="SKILL.md",
            source_files={
                "SKILL.md": content,
                "reference.md": "这是附带资料",
                "glossary_terms.md": "SLA=服务等级协议",
            },
        )
    )
    preview = forge.revise_preview(preview, knowledge_bindings="共享知识区, 术语表, 参考资料")
    result = forge.install_preview(preview)

    assert result.package_dir is not None
    assert (result.package_dir / "knowledge_bindings.json").exists()
    assert (result.package_dir / "treasure_v2.preview.json").exists()
    assert (result.package_dir / "references" / "reference.md").exists()
    assert result.package_dir is not None and (result.package_dir / "references" / "reference.md").exists()
    assert result.pack_yaml_path is not None and result.pack_yaml_path.exists()
    assert result.skill_md_path is not None and result.skill_md_path.exists()

    bindings = json.loads((result.package_dir / "knowledge_bindings.json").read_text(encoding="utf-8"))
    bridge = json.loads((result.package_dir / "treasure_v2.preview.json").read_text(encoding="utf-8"))
    pack_data = yaml.safe_load(result.pack_yaml_path.read_text(encoding="utf-8"))

    assert set(bindings["selected"]) == {"shared", "glossary", "references"}
    assert bridge["runtime"]["kind"] == "nimbus"
    assert "glossary_terms.md" in bindings["glossary_candidates"]
    assert pack_data["knowledge"]["enabled"] is True
    assert pack_data["knowledge"]["source_dirs"] == ["references"]
    assert pack_data["knowledge"]["retrieval_mode"] == "on_demand"


def test_treasure_forge_detects_gpt_frontmatter_payload(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
name: GPT Helper
instructions: 你是一个会总结的 GPT。
conversation_starters:
  - 帮我总结
---
这是导出的 GPT 配置。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="gpt.md"))

    assert preview.source_type == "gpt"


def test_treasure_forge_detects_openclaw_frontmatter_metadata(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = """---
metadata:
  clawdbot:
    tools: web_search browser_read
---
# Claw Researcher
请搜索后阅读页面。"""

    preview = asyncio.run(forge.preview_from_text(content, source_name="SKILL.md"))

    assert preview.source_type == "openclaw_skill"
    assert preview.declared_tools[:2] == ["web_search", "browser_read"]


def test_treasure_forge_detects_treasure_pack_yaml(tmp_path) -> None:
    forge = TreasureForge(tmp_path / "agents")
    content = yaml.safe_dump(
        {
            "meta": {"id": "deep_search", "name": "Pack Search", "description": "来自 pack.yaml"},
            "activation": {"trigger_keywords": ["搜索"], "intents": ["search"]},
            "tools": {"builtin": ["web_search", "llm_call", "send_to_user"]},
            "governance": {"trust_level": "auto"},
            "runtime": {"kind": "nimbus"},
        },
        allow_unicode=True,
        sort_keys=False,
    )

    preview = asyncio.run(forge.preview_from_text(content, source_name="pack.yaml"))

    assert preview.source_type == "treasure_pack"
    assert preview.spec["meta"]["id"] == "deep_search"
    assert preview.executor_type == "nimbus"
