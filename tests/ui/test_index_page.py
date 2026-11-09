"""页面组装绑定测试（T005/T015/T017）：组件树断言六类组件与桥接层绑定（research D7）。"""

from pylightroom.state import FileState
from pylightroom.ui.pages.index import UploadBroker, index_page
from tests.ui._helpers import handler_names, var_tokens

REQUIRED_VARS = (
    "preview_data_url",
    "histogram",
    "histogram_rows",
    "schema_rows",
    "adjustment_values",
    "busy",
    "error_message",
    "exporting",
    "export_message",
    "file_name",
)

REQUIRED_HANDLERS = (
    "FileState.open_file",
    # undo/redo/apply_adjustment/on_slider_change 定义于 DevelopState（FileState 继承）
    "DevelopState.apply_adjustment",
    "DevelopState.undo",
    "DevelopState.redo",
    # slider/export 经 UploadBroker relay 转发；upload 的 on_drop 由 Reflex 渲染期处理
    # （树中无 EventSpec，Upload 组件存在性单测，handle_upload 转发正确性由 test_upload_export 端到端覆盖）
    "UploadBroker.relay_slider",
    "UploadBroker.handle_export",
)


def test_page_constructs():
    page = index_page()
    assert page is not None


def test_page_binds_all_state_vars():
    page = index_page()
    tokens = var_tokens(page)
    for name in REQUIRED_VARS:
        assert name in str(tokens), f"页面未绑定 var：{name}"


def test_page_binds_all_handlers():
    page = index_page()
    names = handler_names(page)
    for expected in REQUIRED_HANDLERS:
        assert expected in names, f"页面未绑定事件处理器：{expected}"


def test_undo_redo_bound_in_menu():
    names = handler_names(index_page())
    assert "DevelopState.undo" in names and "DevelopState.redo" in names


def test_upload_widget_present():
    from tests.ui._helpers import walk

    names = {type(node).__name__ for node in walk(index_page())}
    assert any("Upload" in name for name in names), f"页面缺少上传控件，实际组件：{sorted(names)}"


# ---------------------------------------------------------------------------
# T015（US3）：撤销/重做与滑块/预览的端到端同步
# ---------------------------------------------------------------------------


def exhaust(gen) -> None:
    for _ in gen:
        pass


def test_undo_restores_values_and_preview(png_sample, file_state):
    exhaust(file_state.open_file(png_sample))
    exhaust(file_state.on_slider_change("brightness", 1.5))
    assert file_state.adjustment_values["brightness"]["factor"] == 1.5
    assert file_state.preview_data_url != ""

    exhaust(file_state.undo())
    assert file_state.adjustment_values["brightness"]["factor"] == 1.0, "撤销后未回补 schema 默认值"
    assert file_state.preview_data_url != "", "撤销后预览未同步更新"

    exhaust(file_state.redo())
    assert file_state.adjustment_values["brightness"]["factor"] == 1.5, "重做后未恢复"


def test_empty_stack_undo_shows_readable_hint(png_sample, file_state):
    exhaust(file_state.open_file(png_sample))
    before_url = file_state.preview_data_url
    exhaust(file_state.undo())
    assert file_state.error_message != "", "空栈撤销应给出可读提示"
    assert file_state.preview_data_url == before_url, "空栈撤销不应改变界面"


# ---------------------------------------------------------------------------
# T017（US5）：错误反馈与忙碌指示端到端
# ---------------------------------------------------------------------------


def test_error_cleared_by_next_operation(corrupted_file, png_sample, file_state):
    exhaust(file_state.open_file(corrupted_file))
    assert file_state.error_message != "", "损坏文件应产生可读错误"
    assert file_state.file_name == "", "打开失败后文件名应保持为空"

    exhaust(file_state.open_file(png_sample))  # 下次操作（成功打开）清除旧错（FR-013）
    assert file_state.error_message == "", "成功操作后旧错应清除"
    assert file_state.busy is False, "操作完成后忙碌指示应消失"


def test_create_app_smoke():
    # app.py 含模块级单例（reflex run 经 rxconfig app_module_import 加载）；
    # RegistrationContext 仅允许一个 App，故复验单例而非再创建。
    from pylightroom.ui import app as app_module

    assert app_module.app is not None
    assert app_module.index_page is not None
