"""T005：Presenter 事件翻译器测试（先失败后实现）。

以同步调用回调方法模拟引擎后台线程，覆盖锁语义下的：
版本新者胜、data URL 编码、忙碌通道、错误通道、Condition 有界等待、reset。
"""

from __future__ import annotations

import base64
import threading
import time

from pylightroom.state.presenter import Presenter


class TestOnRenderComplete:
    def test_levels_stored_independently(self):
        presenter = Presenter()
        presenter.on_render_complete("preview-thumb-v1", b"thumb-bytes")
        presenter.on_render_complete("preview-full-v1", b"full-bytes")
        assert presenter.latest("thumb").image_bytes == b"thumb-bytes"
        assert presenter.latest("full").image_bytes == b"full-bytes"
        assert presenter.latest("medium") is None

    def test_older_version_does_not_overwrite(self):
        """乱序回调：旧版本不覆盖新版本（新者胜，spec 边界用例）。"""
        presenter = Presenter()
        presenter.on_render_complete("preview-thumb-v3", b"v3")
        presenter.on_render_complete("preview-thumb-v2", b"v2")
        assert presenter.latest("thumb").version == 3
        assert presenter.latest("thumb").image_bytes == b"v3"

    def test_higher_version_overwrites(self):
        presenter = Presenter()
        presenter.on_render_complete("preview-thumb-v2", b"v2")
        presenter.on_render_complete("preview-thumb-v3", b"v3")
        assert presenter.latest("thumb").version == 3
        assert presenter.latest("thumb").image_bytes == b"v3"

    def test_empty_container_returns_none(self):
        assert Presenter().latest("thumb") is None


class TestDataUrl:
    def test_bytes_encoded_immediately(self):
        """回调字节即时编码为 data URL（FR-005，research D5）。"""
        presenter = Presenter()
        raw = b"\x89PNG-fake-bytes"
        presenter.on_render_complete("preview-thumb-v1", raw)
        result = presenter.latest("thumb")
        expected = "data:image/png;base64," + base64.b64encode(raw).decode("ascii")
        assert result.data_url == expected
        assert result.image_bytes == raw


class TestBusy:
    def test_progress_sets_busy_true(self):
        presenter = Presenter()
        presenter.on_progress("preview-thumb-v1", "render", 0.0)
        assert presenter.busy is True

    def test_full_complete_clears_busy(self):
        presenter = Presenter()
        presenter.on_progress("preview-full-v1", "render", 0.9)
        assert presenter.busy is True
        presenter.on_render_complete("preview-full-v1", b"done")
        assert presenter.busy is False

    def test_full_error_clears_busy(self):
        presenter = Presenter()
        presenter.on_progress("preview-full-v1", "render", 0.9)
        presenter.on_error("preview-full-v1", "后台渲染失败")
        assert presenter.busy is False

    def test_lower_level_complete_keeps_busy(self):
        """仅 full 级完成清忙；thumb/medium 完成不清（高分补齐仍在途）。"""
        presenter = Presenter()
        presenter.on_progress("preview-full-v1", "render", 0.9)
        presenter.on_render_complete("preview-medium-v1", b"m")
        assert presenter.busy is True


class TestOnError:
    def test_error_recorded_in_channel(self):
        presenter = Presenter()
        presenter.on_error("preview-full-v1", "boom")
        assert presenter.error_message == "boom"

    def test_newer_error_overwrites_older(self):
        presenter = Presenter()
        presenter.on_error("preview-full-v1", "old")
        presenter.on_error("preview-full-v2", "new")
        assert presenter.error_message == "new"

    def test_stale_error_does_not_overwrite(self):
        """乱序错误回调：旧版本错误不覆盖新版本错误。"""
        presenter = Presenter()
        presenter.on_error("preview-full-v2", "new")
        presenter.on_error("preview-full-v1", "old")
        assert presenter.error_message == "new"

    def test_unparseable_task_id_only_records_message(self):
        """无法解析的 task_id：仅记录错误消息，不影响结果容器。"""
        presenter = Presenter()
        presenter.on_render_complete("preview-thumb-v1", b"thumb")
        presenter.on_error("weird-task-id", "mystery")
        assert presenter.error_message == "mystery"
        assert presenter.latest("thumb") is not None

    def test_unparseable_render_complete_is_ignored(self):
        presenter = Presenter()
        presenter.on_render_complete("weird-task-id", b"x")
        assert presenter.latest("thumb") is None
        assert presenter.latest("medium") is None
        assert presenter.latest("full") is None

    def test_error_version_exposed(self):
        """错误版本随错误记录暴露（桥接层按版本门控回显）。"""
        presenter = Presenter()
        presenter.on_error("preview-full-v3", "boom")
        assert presenter.error_version == 3


class TestWaitFor:
    def test_already_arrived_returns_immediately(self):
        presenter = Presenter()
        presenter.on_render_complete("preview-full-v2", b"ready")
        assert presenter.wait_for("full", 2, timeout=1.0) is True

    def test_timeout_when_no_result(self):
        """无结果时超时返回 False，且有界（不永久阻塞）。"""
        presenter = Presenter()
        start = time.monotonic()
        assert presenter.wait_for("full", 9, timeout=0.05) is False
        assert time.monotonic() - start < 2.0

    def test_returns_when_background_delivers(self):
        """后台线程延迟送达 → Condition 等待命中（research D4，非轮询）。"""
        presenter = Presenter()

        def deliver():
            time.sleep(0.05)
            presenter.on_render_complete("preview-full-v2", b"late")

        threading.Thread(target=deliver).start()
        assert presenter.wait_for("full", 2, timeout=2.0) is True
        assert presenter.latest("full").image_bytes == b"late"

    def test_satisfied_by_newer_version(self):
        """等待期间到达更高版本同样满足（≥ 语义，避免久等陈旧版本）。"""
        presenter = Presenter()

        def deliver():
            time.sleep(0.05)
            presenter.on_render_complete("preview-full-v3", b"newer")

        threading.Thread(target=deliver).start()
        assert presenter.wait_for("full", 2, timeout=2.0) is True
        assert presenter.latest("full").image_bytes == b"newer"

    def test_error_interrupts_wait(self):
        """对应版本的 full 级错误提前中断等待（及时落错误通道）。"""
        presenter = Presenter()

        def fail():
            time.sleep(0.05)
            presenter.on_error("preview-full-v2", "后台失败")

        threading.Thread(target=fail).start()
        start = time.monotonic()
        assert presenter.wait_for("full", 2, timeout=5.0) is False
        assert time.monotonic() - start < 2.0  # 未等满超时
        assert presenter.error_message == "后台失败"


class TestReset:
    def test_reset_clears_all(self):
        presenter = Presenter()
        presenter.on_render_complete("preview-thumb-v1", b"t")
        presenter.on_render_complete("preview-full-v1", b"f")
        presenter.on_progress("preview-thumb-v5", "render", 0.0)
        presenter.on_error("preview-full-v2", "boom")
        presenter.reset()
        assert presenter.latest("thumb") is None
        assert presenter.latest("full") is None
        assert presenter.error_message == ""
        assert presenter.busy is False
