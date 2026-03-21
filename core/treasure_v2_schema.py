from __future__ import annotations

import re
from typing import Any


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        source = re.split(r"[\s,，、/|]+", value)
    elif isinstance(value, (list, tuple, set)):
        source = list(value)
    else:
        source = [value]
    out: list[str] = []
    seen: set[str] = set()
    for item in source:
        token = str(item or "").strip()
        if not token or token in seen:
            continue
        seen.add(token)
        out.append(token)
    return out


def _infer_output_contract(spec: dict[str, Any]) -> dict[str, Any]:
    system_prompt = str(spec.get("system_prompt") or "").strip()
    lowered = system_prompt.lower()
    output_format = "plain_text"
    if "json" in lowered or "合法 json" in system_prompt or "输出 json" in system_prompt:
        output_format = "json"
    elif "markdown 表格" in system_prompt or "markdown table" in lowered:
        output_format = "markdown_table"
    elif "markdown" in lowered:
        output_format = "markdown"

    rules: list[str] = []
    for snippet, rule in (
        ("只输出", "优先直接输出结果，不加多余铺垫"),
        ("不加说明", "默认不追加解释说明"),
        ("不要解释", "避免额外解释，除非用户追问"),
        ("保持原文段落结构", "尽量保留原始结构与层次"),
        ("先给结论", "先给结论，再补关键要点"),
    ):
        if snippet in system_prompt and rule not in rules:
            rules.append(rule)
    if not rules:
        rules.append("输出应可直接给用户使用")
    return {"format": output_format, "rules": rules[:4]}


def build_treasure_v2_preview(
    *,
    spec: dict[str, Any],
    runtime_suggestion: dict[str, Any] | None = None,
    knowledge_suggestions: dict[str, Any] | None = None,
    scene_suggestions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    raw_spec = spec if isinstance(spec, dict) else {}
    meta = _as_dict(raw_spec.get("meta"))
    trigger = _as_dict(raw_spec.get("trigger"))
    runtime = _as_dict(runtime_suggestion)
    knowledge = _as_dict(knowledge_suggestions)
    scenes = [dict(item) for item in (scene_suggestions or []) if isinstance(item, dict)]

    tool_whitelist: list[str] = []
    capabilities = _as_dict(raw_spec.get("capabilities"))
    for item in capabilities.get("tools") or []:
        if isinstance(item, str):
            name = item.strip()
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = ""
        if name and name not in tool_whitelist:
            tool_whitelist.append(name)

    glossary_paths = [
        f"references/{name}"
        for name in _coerce_list(knowledge.get("glossary_candidates"))
    ]
    reference_paths = [
        f"references/{name}"
        for name in _coerce_list(knowledge.get("reference_candidates"))
    ]

    scene_overrides: dict[str, Any] = {}
    for item in scenes:
        scene = str(item.get("scene") or "").strip()
        if not scene:
            continue
        scene_overrides[scene] = {
            "status": "suggested",
            "reason": str(item.get("reason") or "").strip(),
        }

    return {
        "schema": "2.0-preview",
        "meta": {
            "id": str(meta.get("id") or "").strip(),
            "name": str(meta.get("name") or "").strip(),
            "description": str(meta.get("description") or "").strip(),
            "origin": str(meta.get("origin") or "").strip(),
        },
        "trigger": {
            "keywords": _coerce_list(trigger.get("keywords")),
            "negative_keywords": _coerce_list(trigger.get("negative_keywords")),
            "intents": _coerce_list(trigger.get("intent_types")),
        },
        "runtime": {
            "kind": str(runtime.get("kind") or "builtin").strip() or "builtin",
            "profile": str(runtime.get("profile") or "general").strip() or "general",
            "reason": str(runtime.get("reason") or "").strip(),
            "suggested_execution_tier": str(runtime.get("suggested_execution_tier") or "").strip(),
        },
        "tool_whitelist": tool_whitelist,
        "output_contract": _infer_output_contract(raw_spec),
        "knowledge_bindings": {
            "suggested": _coerce_list(knowledge.get("suggested")),
            "selected": _coerce_list(knowledge.get("selected")),
            "shared_knowledge": "user_shared" if "shared" in _coerce_list(knowledge.get("selected")) else "",
            "glossaries": glossary_paths[:8],
            "references": reference_paths[:12],
        },
        "scene_overrides": scene_overrides,
    }


__all__ = ["build_treasure_v2_preview"]
