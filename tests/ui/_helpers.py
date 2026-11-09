"""组件树绑定断言助手（research D7：无浏览器测试，Var/事件 token 收集）。

原理：Reflex 组件树的 props 直接挂在节点 __dict__（Var 对象含 _js_expr），
事件绑定挂在 event_triggers（EventChain → EventSpec(handler.fn)）。
期望 token 与被测组件由同一 State 属性引用生成，天然同构。
"""

from __future__ import annotations

from reflex_base.event import EventChain, EventSpec


def walk(component):
    yield component
    for child in getattr(component, "children", None) or []:
        if isinstance(child, str):
            continue
        yield from walk(child)


def _tokenize(value) -> set[str]:
    if value is None or isinstance(value, (str, int, float, bool)):
        return {str(value)}
    fn = getattr(value, "fn", None)  # EventHandler（不带括号的处理器引用）
    if fn is not None and callable(fn):
        return {fn.__qualname__}
    if isinstance(value, EventChain):
        tokens: set[str] = set()
        for spec in value.events:
            tokens |= _tokenize(spec)
        return tokens
    if isinstance(value, EventSpec):
        return {value.handler.fn.__qualname__}
    if isinstance(value, (list, tuple)):
        tokens = set()
        for item in value:
            tokens |= _tokenize(item)
        return tokens
    if isinstance(value, dict):
        tokens = set()
        for key, item in value.items():
            tokens |= _tokenize(key) | _tokenize(item)
        return tokens
    js_expr = getattr(value, "_js_expr", None)
    if js_expr is not None:
        return {js_expr}
    return {str(value)}


def var_tokens(component) -> set[str]:
    """全树 State Var 的 _js_expr 集合（含操作 Var 内嵌的原始表达式）。"""
    tokens: set[str] = set()
    for node in walk(component):
        for key, value in vars(node).items():
            if key == "children":
                continue
            tokens |= _tokenize(value)
    return tokens


def bind_var(component, var) -> bool:
    """Var 绑定判定：原始 _js_expr 以子串形式出现在任一 token 中。"""
    expr = getattr(var, "_js_expr", None)
    if expr is None:
        return False
    return any(expr in token for token in var_tokens(component))


def handler_names(component) -> set[str]:
    """全树事件处理器 qualname 集合（如 'FileState.on_slider_change'）。"""
    tokens: set[str] = set()
    for node in walk(component):
        for trigger in getattr(node, "event_triggers", {}).values():
            tokens |= _tokenize(trigger)
    return tokens


def assert_binds(component, *refs) -> None:
    """断言组件树绑定了给定 State 属性/事件引用。

    refs 的每个元素与页面写法同源：Var（如 FileState.preview_data_url）或
    EventSpec（如 FileState.undo()）。Var 查 _js_expr，事件查 handler qualname。
    """
    v_tokens = var_tokens(component)
    h_tokens = handler_names(component)
    missing: list[str] = []
    for ref in refs:
        fn = getattr(ref, "fn", None)  # EventHandler 引用
        if isinstance(ref, EventSpec):
            ok = ref.handler.fn.__qualname__ in h_tokens
        elif fn is not None and callable(fn):
            ok = fn.__qualname__ in h_tokens
        else:
            ok = bind_var(component, ref)
        if not ok:
            missing.append(f"{ref!r}")
    assert not missing, "绑定断言失败：" + "; ".join(missing)
