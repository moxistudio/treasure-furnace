from __future__ import annotations

from collections.abc import Iterable
from typing import Any


_TIER_LABEL_MAP: dict[str, str] = {
    "small": "小",
    "medium": "中",
    "large": "大",
}

_TIER_TEXT_MAP: dict[str, str] = {
    "small": "小事",
    "medium": "中事",
    "large": "大事",
}

_EXECUTOR_TIER_MAP: dict[str, str] = {
    "llm_call": "small",
    "nimbus": "medium",
    "marshal": "large",
    "builtin": "small",
}

_VISIBILITY_LABEL_MAP: dict[str, str] = {
    "public": "public",
    "user_invocable": "public",
    "helper_only": "helper only",
}


def _as_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _coerce_list(value: Any) -> list[str]:
    if isinstance(value, (list, tuple, set)):
        source = value
    elif value is None:
        source = []
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


def _get_import_source(item: object) -> dict[str, Any]:
    raw_spec = _as_dict(getattr(item, "raw_spec", None))
    if isinstance(raw_spec.get("import_source"), dict):
        return raw_spec.get("import_source") or {}
    spec = _as_dict(getattr(item, "spec", None))
    if isinstance(spec.get("import_source"), dict):
        return spec.get("import_source") or {}
    return {}


def _get_steps(item: object) -> list[dict[str, Any]]:
    steps = getattr(item, "steps", None)
    if isinstance(steps, list):
        return [step for step in steps if isinstance(step, dict)]
    spec = _as_dict(getattr(item, "spec", None))
    raw_spec = _as_dict(getattr(item, "raw_spec", None))
    for candidate in (spec.get("steps"), raw_spec.get("steps")):
        if isinstance(candidate, list):
            return [step for step in candidate if isinstance(step, dict)]
    return []


def _executor_type(item: object) -> str:
    explicit = str(getattr(item, "executor_type", "") or "").strip()
    if explicit:
        return explicit
    spec = _as_dict(getattr(item, "spec", None))
    raw_spec = _as_dict(getattr(item, "raw_spec", None))
    for container in (spec, raw_spec):
        executor = container.get("executor") if isinstance(container.get("executor"), dict) else {}
        token = str(executor.get("type") or "").strip()
        if token:
            return token
    return "builtin"


def _execution_tier(item: object) -> str:
    explicit = str(getattr(item, "execution_tier", "") or "").strip()
    if explicit:
        return explicit
    return _EXECUTOR_TIER_MAP.get(_executor_type(item), "small")


def _visibility_code(item: object) -> str:
    import_source = _get_import_source(item)
    explicit = str(import_source.get("visibility") or "").strip().lower()
    if explicit:
        return explicit
    spec = _as_dict(getattr(item, "spec", None))
    raw_spec = _as_dict(getattr(item, "raw_spec", None))
    for container in (spec, raw_spec):
        executor = container.get("executor") if isinstance(container.get("executor"), dict) else {}
        runtime_hints = executor.get("runtime_hints") if isinstance(executor.get("runtime_hints"), dict) else {}
        if runtime_hints.get("user_invocable") is False:
            return "helper_only"
    claude_code = import_source.get("claude_code") if isinstance(import_source.get("claude_code"), dict) else {}
    if claude_code.get("user_invocable") is False:
        return "helper_only"
    if bool(getattr(item, "helper_only", False)):
        return "helper_only"
    return "public"


def _visibility_label(item: object) -> str:
    return _VISIBILITY_LABEL_MAP.get(_visibility_code(item), _visibility_code(item) or "public")


def _declared_tools(item: object) -> list[str]:
    explicit = _coerce_list(getattr(item, "declared_tools", None))
    if explicit:
        return explicit
    return _coerce_list(_get_import_source(item).get("declared_tools"))


def _mapped_tools(item: object) -> list[str]:
    explicit = _coerce_list(getattr(item, "mapped_tools", None))
    if explicit:
        return explicit
    import_mapped = _coerce_list(_get_import_source(item).get("mapped_tools"))
    if import_mapped:
        return import_mapped
    return _coerce_list(getattr(item, "tools", None))


def _unmapped_tools(item: object) -> list[str]:
    explicit = _coerce_list(getattr(item, "unmapped_tools", None))
    if explicit:
        return explicit
    return _coerce_list(_get_import_source(item).get("unmapped_tools"))


def _source_files(item: object) -> list[str]:
    import_files = _coerce_list(_get_import_source(item).get("source_files"))
    if import_files:
        return import_files
    source_name = str(getattr(item, "source_name", "") or "").strip()
    source_files = getattr(item, "source_files", None)
    if not isinstance(source_files, dict):
        return []
    out: list[str] = []
    for name in source_files.keys():
        token = str(name or "").strip()
        if token and token != source_name:
            out.append(token)
    return out


def _resource_count(item: object) -> int:
    explicit = getattr(item, "resource_count", None)
    if isinstance(explicit, int) and explicit > 0:
        return explicit
    import_source = _get_import_source(item)
    import_count = import_source.get("resource_count")
    if isinstance(import_count, int) and import_count > 0:
        return import_count
    source_files = _source_files(item)
    if source_files:
        return len(source_files)
    return len(_get_steps(item))


def _risk_flags(item: object) -> list[Any]:
    explicit = getattr(item, "risk_flags", None)
    if isinstance(explicit, list):
        return explicit
    imported = _get_import_source(item).get("risk_flags")
    return imported if isinstance(imported, list) else []


def _render_risk_flags(item: object) -> str:
    rendered: list[str] = []
    seen: set[str] = set()
    for flag in _risk_flags(item):
        if isinstance(flag, dict):
            text = str(flag.get("detail") or flag.get("code") or "").strip()
        else:
            text = str(flag or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        rendered.append(text)
    return "；".join(rendered) if rendered else "无"


def build_forge_preview_governance_lines(preview: object) -> list[str]:
    spec = _as_dict(getattr(preview, "spec", None))
    meta = spec.get("meta") if isinstance(spec.get("meta"), dict) else {}
    display_name = str(getattr(preview, "display_name", "") or meta.get("name") or "未命名法宝").strip()
    version = str(meta.get("version") or "1.0.0").strip() or "1.0.0"
    source_type = str(getattr(preview, "source_type", "") or _get_import_source(preview).get("type") or "unknown").strip()
    origin_url = str(getattr(preview, "origin_url", "") or _get_import_source(preview).get("origin_url") or "").strip()
    declared_tools = _declared_tools(preview)
    mapped_tools = _mapped_tools(preview)
    unmapped_tools = _unmapped_tools(preview)
    tool_text = ", ".join(mapped_tools[:8]) if mapped_tools else "（暂无）"
    tier_text = _TIER_TEXT_MAP.get(_execution_tier(preview), "未知")
    lines = [
        f"📦 {display_name} v{version}",
        f"来源：{source_type}",
    ]
    if origin_url:
        lines.append(f"导入来源 URL：{origin_url}")
    lines.append(f"工具：{tool_text}（{len(declared_tools)} 个声明 / {len(mapped_tools)} 个已映射）")
    if unmapped_tools:
        lines.append(f"未映射工具：{', '.join(unmapped_tools[:8])}")
    lines.append(f"执行层：{tier_text}（{_executor_type(preview)}）")
    lines.append(f"资源数量：{_resource_count(preview)}")
    lines.append(f"风险：{_render_risk_flags(preview)}")
    lines.append(f"可见性：{_visibility_label(preview)}")
    return lines


def build_treasure_detail_text(treasure: object) -> str:
    import_source = _get_import_source(treasure)
    source_type = str(import_source.get("type") or "").strip()
    source_name = str(import_source.get("name") or "").strip()
    origin_url = str(import_source.get("origin_url") or "").strip()
    declared_tools = _declared_tools(treasure)
    mapped_tools = _mapped_tools(treasure)
    unmapped_tools = _unmapped_tools(treasure)
    source_files = _source_files(treasure)
    claude_code = import_source.get("claude_code") if isinstance(import_source.get("claude_code"), dict) else {}
    icon = str(getattr(treasure, "icon", "🔮") or "🔮").strip() or "🔮"
    name = str(getattr(treasure, "name", "未命名法宝") or "未命名法宝").strip()
    description = str(getattr(treasure, "description", "") or "").strip()
    tools = _coerce_list(getattr(treasure, "tools", None))
    keywords = _coerce_list(getattr(treasure, "trigger_keywords", None))
    lines = [
        f"{icon} {name}",
        f"ID：{str(getattr(treasure, 'id', '') or '').strip()}",
        f"描述：{description or '（暂无）'}",
        f"执行方式：{_executor_type(treasure)}",
        f"执行层级：{_execution_tier(treasure)}",
        f"工具：{', '.join(tools) if tools else '（暂无）'}",
        f"触发词：{', '.join(keywords) if keywords else '（暂无）'}",
        f"信任等级：{str(getattr(treasure, 'trust_level', 'auto') or 'auto').strip()}",
        f"来源：{str(getattr(treasure, 'origin', 'builtin') or 'builtin').strip()}",
    ]
    knowledge_config = _as_dict(getattr(treasure, "knowledge_config", None))
    if knowledge_config.get("enabled"):
        retrieval = knowledge_config.get("retrieval") if isinstance(knowledge_config.get("retrieval"), dict) else {}
        lines.append(
            "知识库：已启用"
            f"（top_k={int(retrieval.get('top_k') or 5)}"
            f" / 用户共享={'是' if retrieval.get('include_user_shared') else '否'}）"
        )
    steps = _get_steps(treasure)
    if steps:
        step_ids = [str(item.get("id") or "?") for item in steps]
        lines.append(f"步骤链：{' → '.join(step_ids)}（共 {len(step_ids)} 步）")
    if source_type:
        lines.append(f"导入来源类型：{source_type}")
    if source_name:
        lines.append(f"导入来源文件：{source_name}")
    if origin_url:
        lines.append(f"导入来源 URL：{origin_url}")
    package_path = str(getattr(treasure, "package_path", "") or "").strip()
    if package_path:
        lines.append(f"法宝包路径：{package_path}")
    if declared_tools:
        lines.append(f"源 Skill 声明工具：{', '.join(declared_tools)}")
    if mapped_tools:
        lines.append(f"映射后工具：{', '.join(mapped_tools)}")
    if unmapped_tools:
        lines.append(f"未映射工具：{', '.join(unmapped_tools)}")
    if import_source:
        lines.append(f"资源数量：{_resource_count(treasure)}")
        lines.append(f"风险：{_render_risk_flags(treasure)}")
        lines.append(f"可见性：{_visibility_label(treasure)}")
    if source_files:
        lines.append(f"附带资源数：{len(source_files)}")
        lines.append(f"附带资源：{', '.join(source_files[:6])}")
    if claude_code:
        lines.append(f"Claude 子法宝：{'是' if bool(claude_code.get('agent')) else '否'}")
        context_mode = str(claude_code.get("context_mode") or claude_code.get("context") or "").strip()
        if context_mode:
            lines.append(f"Claude 上下文：{context_mode}")
        preferred_model = str(claude_code.get("preferred_model") or "").strip()
        if preferred_model:
            lines.append(f"Claude 推荐模型：{preferred_model}")
        if "disable_model_invocation" in claude_code:
            lines.append(f"Claude 自动调度：{'关闭' if bool(claude_code.get('disable_model_invocation')) else '开启'}")
        if "user_invocable" in claude_code:
            lines.append(f"Claude 用户直呼：{'开启' if bool(claude_code.get('user_invocable')) else '关闭'}")
    if _visibility_label(treasure) == "helper only":
        lines.append("法宝可见性：helper only（默认不出现在主口袋列表，也不会被用户直呼匹配）")
    return "\n".join(lines)


def build_pocket_manifest_lines(treasures: Iterable[object]) -> list[str]:
    lines: list[str] = []
    for item in treasures:
        name = str(getattr(item, "name", "未命名法宝") or "未命名法宝").strip()
        icon = str(getattr(item, "icon", "🔮") or "🔮").strip() or "🔮"
        description = str(getattr(item, "description", "") or "").strip()
        keywords = getattr(item, "trigger_keywords", []) or []
        keyword_text = ", ".join(str(kw).strip() for kw in keywords[:5] if str(kw).strip())
        tier = str(getattr(item, "execution_tier", "") or "").strip()
        tier_label = _TIER_LABEL_MAP.get(tier, "")
        tier_tag = f"[{tier_label}]" if tier_label else ""
        suffix = f"（触发词：{keyword_text}）" if keyword_text else ""
        lines.append(f"{icon} {name}{tier_tag}：{description}{suffix}".strip())
    return lines


def build_pocket_manifest(treasures: Iterable[object]) -> str:
    lines = build_pocket_manifest_lines(treasures)
    if not lines:
        return "【你的口袋里暂时还没有法宝】\n可先导入一个标准 SKILL.md，或等待内置法宝加载。"
    body = "\n".join(lines)
    return (
        "【你的口袋里目前有这些法宝】\n"
        f"{body}\n\n"
        f"共 {len(lines)} 个法宝可用。输入 /pocket 查看详情。"
    )
