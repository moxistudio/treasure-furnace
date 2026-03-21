"""core/import_manager.py 单元测试。"""

import asyncio
from unittest.mock import MagicMock

from core.import_manager import (
    ImportSessionStore,
    is_import_cancel,
    is_import_confirm,
    is_import_document,
    maybe_handle_import_message,
    parse_import_adjustment,
    render_adjustment_help,
    start_import_waiting,
)


# ---------------------------------------------------------------------------
# ImportSessionStore
# ---------------------------------------------------------------------------

def test_store_empty_by_default():
    store = ImportSessionStore()
    assert store.get("user1") is None
    assert not store.has_pending("user1")


def test_store_set_and_get():
    store = ImportSessionStore()
    store.set("user1", {"mode": "await_content"})
    assert store.get("user1") == {"mode": "await_content"}
    assert store.has_pending("user1")


def test_store_clear():
    store = ImportSessionStore()
    store.set("user1", {"mode": "await_confirm"})
    store.clear("user1")
    assert store.get("user1") is None
    assert not store.has_pending("user1")


def test_store_isolation():
    store = ImportSessionStore()
    store.set("a", {"x": 1})
    store.set("b", {"x": 2})
    assert store.get("a")["x"] == 1
    assert store.get("b")["x"] == 2
    store.clear("a")
    assert store.get("a") is None
    assert store.get("b") is not None


# ---------------------------------------------------------------------------
# 文本检测
# ---------------------------------------------------------------------------

def test_is_import_confirm():
    assert is_import_confirm("确认")
    assert is_import_confirm("放")
    assert is_import_confirm("ok")
    assert is_import_confirm("YES")
    assert not is_import_confirm("你好")
    assert not is_import_confirm("")


def test_is_import_cancel():
    assert is_import_cancel("取消")
    assert is_import_cancel("算了")
    assert is_import_cancel("cancel")
    assert not is_import_cancel("继续")
    assert not is_import_cancel("")


def test_is_import_document():
    store = ImportSessionStore()
    assert not is_import_document("photo.jpg", "", "u1", store=store)
    assert is_import_document("skill.md", "/import", "u1", store=store)
    assert not is_import_document("skill.md", "", "u1", store=store)
    store.set("u1", {"mode": "await_content"})
    assert is_import_document("data.yaml", "", "u1", store=store)


# ---------------------------------------------------------------------------
# 调整解析
# ---------------------------------------------------------------------------

def test_parse_adjustment_preview():
    assert parse_import_adjustment("预览") == ("preview", "")
    assert parse_import_adjustment("preview") == ("preview", "")


def test_parse_adjustment_trigger():
    result = parse_import_adjustment("触发词 翻译, translate")
    assert result is not None
    assert result[0] == "trigger_keywords"
    assert "翻译" in result[1]


def test_parse_adjustment_trust():
    result = parse_import_adjustment("信任 confirm")
    assert result == ("trust_level", "confirm")


def test_parse_adjustment_executor():
    result = parse_import_adjustment("执行器 marshal")
    assert result == ("executor_type", "marshal")


def test_parse_adjustment_knowledge():
    result = parse_import_adjustment("知识 共享知识区, 参考资料")
    assert result == ("knowledge_bindings", "共享知识区, 参考资料")


def test_parse_adjustment_none():
    assert parse_import_adjustment("你好") is None
    assert parse_import_adjustment("") is None


def test_render_adjustment_help():
    text = render_adjustment_help()
    assert "触发词" in text
    assert "信任" in text
    assert "执行器" in text
    assert "知识" in text


# ---------------------------------------------------------------------------
# 核心流程
# ---------------------------------------------------------------------------

def test_cancel_clears_session():
    store = ImportSessionStore()
    store.set("u1", {"mode": "await_content"})
    reply = asyncio.run(maybe_handle_import_message("u1", "取消", store=store))
    assert reply == "已取消这次新法宝导入。"
    assert not store.has_pending("u1")


def test_empty_text_returns_prompt():
    store = ImportSessionStore()
    store.set("u1", {"mode": "await_content"})
    reply = asyncio.run(maybe_handle_import_message("u1", "", store=store))
    assert "请直接贴上" in reply


def test_no_session_returns_none():
    store = ImportSessionStore()
    reply = asyncio.run(maybe_handle_import_message("u1", "hello", store=store))
    assert reply is None


def test_start_import_waiting():
    store = ImportSessionStore()
    reply = asyncio.run(start_import_waiting("u1", store=store))
    assert "请把要导入的内容发给我" in reply
    assert store.get("u1")["mode"] == "await_content"


def test_confirm_installs_and_clears():
    """确认安装后清除会话状态。"""
    store = ImportSessionStore()
    mock_preview = MagicMock()
    mock_preview.display_name = "Test Skill"
    mock_preview.source_type = "agent_skill"
    mock_preview.render_text.return_value = "preview text"
    mock_preview.trigger_keywords = ["test"]

    store.set("u1", {"mode": "await_confirm", "preview": mock_preview})

    mock_forge = MagicMock()
    mock_result = MagicMock()
    mock_result.agent_id = "test_skill"
    mock_result.package_dir = "/runtime_assets/test_skill"
    mock_result.pack_yaml_path = "/runtime_assets/test_skill/pack.yaml"
    mock_result.skill_md_path = "/runtime_assets/test_skill/SKILL.md"
    mock_forge.install_preview.return_value = mock_result

    # 需要让 isinstance(preview, ForgePreview) 检查通过
    import core.import_manager as im
    from unittest.mock import patch
    with patch.object(im, "ForgePreview", type(mock_preview), create=True):
        # 直接 patch treasure_forge.ForgePreview 的 isinstance 检查
        import treasure_forge
        original_fp = treasure_forge.ForgePreview
        try:
            treasure_forge.ForgePreview = type(mock_preview)
            reply = asyncio.run(
                maybe_handle_import_message(
                    "u1", "确认", forge=mock_forge, store=store, pocket_reload_fn=lambda: None,
                )
            )
        finally:
            treasure_forge.ForgePreview = original_fp

    assert "新法宝" in reply
    assert "安装目录：" in reply
    assert "新法宝包：" in reply
    assert "技能入口：" in reply
    assert "/runtime_assets/test_skill/pack.yaml" in reply
    assert not store.has_pending("u1")
    mock_forge.install_preview.assert_called_once_with(mock_preview)


def test_adjustment_knowledge_updates_preview():
    store = ImportSessionStore()
    mock_preview = MagicMock()
    mock_preview.display_name = "Study Translator"
    mock_preview.source_type = "agent_skill"
    mock_preview.render_text.return_value = "updated preview"
    mock_preview.knowledge_suggestions = {"selected": ["shared", "references"]}

    store.set("u1", {"mode": "await_confirm", "preview": mock_preview})

    mock_forge = MagicMock()
    updated_preview = MagicMock()
    updated_preview.display_name = "Study Translator"
    updated_preview.source_type = "agent_skill"
    updated_preview.render_text.return_value = "updated preview"
    updated_preview.knowledge_suggestions = {"selected": ["shared", "references"]}
    mock_forge.revise_preview.return_value = updated_preview

    import core.import_manager as im
    from unittest.mock import patch
    with patch.object(im, "ForgePreview", type(mock_preview), create=True):
        import treasure_forge
        original_fp = treasure_forge.ForgePreview
        try:
            treasure_forge.ForgePreview = type(mock_preview)
            reply = asyncio.run(
                maybe_handle_import_message(
                    "u1",
                    "知识 共享知识区, 参考资料",
                    forge=mock_forge,
                    store=store,
                )
            )
        finally:
            treasure_forge.ForgePreview = original_fp

    assert "已更新知识绑定" in reply
    mock_forge.revise_preview.assert_called_once_with(mock_preview, knowledge_bindings="共享知识区, 参考资料")
