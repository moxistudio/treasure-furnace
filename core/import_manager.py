"""
新法宝导入流程管理器。
处理 /import 的完整交互流程：预览 → 调整 → 确认/取消 → 安装 → 入袋。
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# 会话状态管理
# ---------------------------------------------------------------------------

class ImportSessionStore:
    """管理所有用户的导入会话状态。"""

    def __init__(self) -> None:
        self._states: dict[str, dict[str, object]] = {}

    def get(self, user_id: str) -> dict[str, object] | None:
        state = self._states.get(user_id)
        return state if isinstance(state, dict) else None

    def set(self, user_id: str, state: dict[str, object]) -> None:
        self._states[user_id] = state

    def clear(self, user_id: str) -> None:
        self._states.pop(user_id, None)

    def has_pending(self, user_id: str) -> bool:
        return self.get(user_id) is not None


# 模块级默认会话存储
_default_store = ImportSessionStore()


def get_default_store() -> ImportSessionStore:
    return _default_store


# ---------------------------------------------------------------------------
# 文本检测
# ---------------------------------------------------------------------------

_CONFIRM_WORDS = frozenset({"放", "确认", "导入", "install", "ok", "yes", "y"})
_CANCEL_WORDS = frozenset({"取消", "算了", "不用了", "cancel", "stop", "no", "n"})


def is_import_confirm(text: str) -> bool:
    return str(text or "").strip().lower() in _CONFIRM_WORDS


def is_import_cancel(text: str) -> bool:
    return str(text or "").strip().lower() in _CANCEL_WORDS


def is_import_document(file_name: str, caption: str, user_id: str, *, store: ImportSessionStore | None = None) -> bool:
    """判断一个文档消息是否属于导入流程。"""
    ext = Path(file_name or "").suffix.lower()
    if ext not in {".md", ".txt", ".yaml", ".yml", ".zip"}:
        return False
    caption_lower = str(caption or "").strip().lower()
    s = store or _default_store
    return bool(caption_lower.startswith("/import") or s.has_pending(user_id))


# ---------------------------------------------------------------------------
# 调整解析
# ---------------------------------------------------------------------------

_ADJUSTMENT_PATTERNS: dict[str, str] = {
    "trigger_keywords": r"^(?:触发词|关键词|trigger|triggers|keywords?)\s*[:：=]?\s*(.+)$",
    "trust_level": r"^(?:信任|信任等级|trust|trust_level)\s*[:：=]?\s*(.+)$",
    "executor_type": r"^(?:执行器|执行方式|executor)\s*[:：=]?\s*(.+)$",
    "knowledge_bindings": r"^(?:知识|知识库|knowledge|knowledge_bindings?)\s*[:：=]?\s*(.+)$",
}

_PREVIEW_WORDS = frozenset({"preview", "show", "预览", "看看", "看一下", "查看预览"})


def render_adjustment_help() -> str:
    return (
        '当前在新法宝锻造确认阶段。发送\u201c放\u201d完成导入，或继续校准：\n'
        "- 触发词 关键词1, 关键词2\n"
        "- 信任 auto | confirm | always_confirm\n"
        "- 执行器 builtin | nimbus | marshal\n"
        "- 知识 共享知识区, 术语表, 参考资料\n"
        '- 发送\u201c预览\u201d查看当前版本，发送\u201c取消\u201d放弃。'
    )


def parse_import_adjustment(text: str) -> tuple[str, str] | None:
    raw = str(text or "").strip()
    if not raw:
        return None
    if raw.lower() in _PREVIEW_WORDS:
        return "preview", ""
    for field, pattern in _ADJUSTMENT_PATTERNS.items():
        match = re.match(pattern, raw, flags=re.IGNORECASE)
        if match:
            return field, str(match.group(1) or "").strip()
    return None


def _preview_mcp_meta(preview: Any) -> dict[str, Any]:
    spec = getattr(preview, "spec", None)
    if not isinstance(spec, dict):
        return {}
    import_source = spec.get("import_source") if isinstance(spec.get("import_source"), dict) else {}
    mcp_meta = import_source.get("mcp")
    return mcp_meta if isinstance(mcp_meta, dict) else {}


def _render_mcp_preview_suffix(preview: Any) -> str:
    mcp_meta = _preview_mcp_meta(preview)
    resolved = [str(item).strip() for item in (mcp_meta.get("resolved_servers") or []) if str(item).strip()]
    if not resolved:
        return ""
    mapped = [str(item).strip() for item in (mcp_meta.get("suggested_mapped_tools") or []) if str(item).strip()]
    lines = ["MCP 识别：", f"- Servers: {', '.join(resolved)}"]
    if mapped:
        lines.append(f"- 映射能力: {', '.join(mapped[:6])}")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# 核心流程
# ---------------------------------------------------------------------------

async def preview_import_source(
    user_id: str,
    raw_source: str,
    *,
    username: str = "",
    source_name: str = "",
    forge: Any = None,
    store: ImportSessionStore | None = None,
    audit_fn: Any = None,
) -> str:
    """
    预览导入源。
    调用 forge.preview_from_input 并保存会话状态。
    """
    s = store or _default_store
    if forge is None:
        from treasure_forge import TreasureForge
        forge = TreasureForge()
    preview = await forge.preview_from_input(raw_source, source_name=source_name)
    s.set(user_id, {
        "mode": "await_confirm",
        "preview": preview,
        "source_name": source_name,
    })
    if callable(audit_fn):
        try:
            audit_fn(user_id, username, "SELF", f"import:preview:{preview.source_type}", preview.display_name[:200], 0, 0, 0)
        except Exception:
            pass
    rendered = preview.render_text()
    mcp_suffix = _render_mcp_preview_suffix(preview)
    if mcp_suffix:
        return f"{rendered}\n\n{mcp_suffix}"
    return rendered


async def handle_import_file(
    user_id: str,
    path: str,
    file_name: str,
    *,
    username: str = "",
    forge: Any = None,
    store: ImportSessionStore | None = None,
    audit_fn: Any = None,
) -> str:
    """处理文件导入（.md / .yaml / .zip）。"""
    s = store or _default_store
    if forge is None:
        from treasure_forge import TreasureForge
        forge = TreasureForge()
    preview = await forge.preview_from_file(path)
    s.set(user_id, {
        "mode": "await_confirm",
        "preview": preview,
        "source_name": file_name,
    })
    if callable(audit_fn):
        try:
            audit_fn(user_id, username, "SELF", f"import:file_preview:{preview.source_type}", file_name[:200], 0, 0, 0)
        except Exception:
            pass
    rendered = preview.render_text()
    mcp_suffix = _render_mcp_preview_suffix(preview)
    if mcp_suffix:
        return f"{rendered}\n\n{mcp_suffix}"
    return rendered


async def maybe_handle_import_message(
    user_id: str,
    text: str,
    username: str = "",
    *,
    forge: Any = None,
    store: ImportSessionStore | None = None,
    pocket_reload_fn: Any = None,
    audit_fn: Any = None,
) -> str | None:
    """
    处理导入中的用户消息（确认/取消/调整/文本粘贴）。
    返回回复文本，或 None 表示不在导入流程中。
    """
    s = store or _default_store
    state = s.get(user_id)
    if state is None:
        return None
    mode = str(state.get("mode") or "").strip().lower()
    stripped = str(text or "").strip()

    if not stripped:
        return "请直接贴上标准 SKILL.md / OpenClaw Skill 文本，或发送本地文件路径。"

    if is_import_cancel(stripped):
        s.clear(user_id)
        return "已取消这次新法宝导入。"

    if mode == "await_content":
        return await preview_import_source(user_id, stripped, username=username, forge=forge, store=s, audit_fn=audit_fn)

    if mode == "await_confirm":
        from treasure_forge import ForgePreview
        preview = state.get("preview")
        if not isinstance(preview, ForgePreview):
            s.clear(user_id)
            return "这次导入预览已经失效，请重新发送 /import。"

        adjustment = parse_import_adjustment(stripped)
        if adjustment is not None:
            field, value = adjustment
            if field == "preview":
                rendered = preview.render_text()
                mcp_suffix = _render_mcp_preview_suffix(preview)
                if mcp_suffix:
                    return f"{rendered}\n\n{mcp_suffix}"
                return rendered
            if forge is None:
                from treasure_forge import TreasureForge
                forge = TreasureForge()
            try:
                if field == "trigger_keywords":
                    updated_preview = forge.revise_preview(preview, trigger_keywords=value)
                    notice = f"已更新触发词：{'、'.join(updated_preview.trigger_keywords)}"
                elif field == "trust_level":
                    updated_preview = forge.revise_preview(preview, trust_level=value)
                    notice = f"已更新信任等级：{updated_preview.trust_level}"
                elif field == "executor_type":
                    updated_preview = forge.revise_preview(preview, executor_type=value)
                    notice = f"已更新执行器：{updated_preview.executor_type}"
                elif field == "knowledge_bindings":
                    updated_preview = forge.revise_preview(preview, knowledge_bindings=value)
                    selected = updated_preview.knowledge_suggestions.get("selected") or []
                    label = "、".join(str(item) for item in selected) if selected else "无"
                    notice = f"已更新知识绑定：{label}"
                else:
                    updated_preview = preview
                    notice = ""
            except ValueError as exc:
                return f"{exc}\n\n{render_adjustment_help()}"
            state["preview"] = updated_preview
            s.set(user_id, state)
            if callable(audit_fn):
                try:
                    audit_fn(user_id, username, "SELF", f"import:adjust:{field}", str(value)[:200], 0, 0, 0)
                except Exception:
                    pass
            rendered = updated_preview.render_text()
            mcp_suffix = _render_mcp_preview_suffix(updated_preview)
            if mcp_suffix:
                rendered = f"{rendered}\n\n{mcp_suffix}"
            return f"{notice}\n\n{rendered}".strip()

        if not is_import_confirm(stripped):
            return render_adjustment_help()

        # 确认安装
        if forge is None:
            from treasure_forge import TreasureForge
            forge = TreasureForge()
        result = forge.install_preview(preview)
        s.clear(user_id)
        if callable(pocket_reload_fn):
            try:
                pocket_reload_fn()
            except Exception:
                pass
        if callable(audit_fn):
            try:
                audit_fn(user_id, username, "OUT", f"import:installed:{preview.source_type}", result.agent_id, 0, 0, 0)
            except Exception:
                pass
        package_path = str(getattr(result, "pack_yaml_path", "") or "").strip()
        package_dir = str(getattr(result, "package_dir", "") or "").strip()
        skill_path = str(getattr(result, "skill_md_path", "") or "").strip()
        package_dir_line = f"安装目录：{package_dir}\n" if package_dir else ""
        package_line = f"新法宝包：{package_path}\n" if package_path else ""
        skill_line = f"技能入口：{skill_path}\n" if skill_path else ""
        return (
            f"\u2705 新法宝「{preview.display_name}」已放入口袋！\n"
            f"ID：{result.agent_id}\n"
            f"{package_dir_line}"
            f"{package_line}\n"
            f"{skill_line}"
            "你现在可以发 /pocket 查看，或直接用相关触发词把它掏出来。"
        )
    return None


async def start_import_waiting(
    user_id: str,
    *,
    store: ImportSessionStore | None = None,
    clear_pending_fn: Any = None,
) -> str:
    """启动导入等待流程。"""
    s = store or _default_store
    if callable(clear_pending_fn):
        try:
            clear_pending_fn(user_id, clear_marshal_session=True)
        except Exception:
            pass
    s.set(user_id, {"mode": "await_content"})
    return (
        "请把要导入的内容发给我：\n"
        "- 标准 SKILL.md（YAML frontmatter）\n"
        "- OpenClaw Skill 文本 / SKILL.md\n"
        "- 本地文件路径（.md / .txt / .yaml / .zip）\n\n"
        "我会先给你一个新法宝锻造预览，再由你确认是否放入口袋。"
    )
