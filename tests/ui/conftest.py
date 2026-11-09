"""tests/ui 共享夹具：桥接层会话隔离 + FileState 直接实例化（承 002 测试模式）。"""

import pytest

from pylightroom.state import FileState, session as session_module


@pytest.fixture()
def file_state():
    session_module.set_session(None)
    state = FileState(_reflex_internal_init=True)
    yield state
    session_module.set_session(None)
