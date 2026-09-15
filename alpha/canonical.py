"""V3.9.1 alpha canonicalization: commutative normalization + signature.

兼容 V3.9 AlphaExpression 与 V3.9.1 AlphaExpressionV391 两种表达式树。
"""
from __future__ import annotations

COMMUTATIVE = {"add", "mul"}


def canonicalize(expression):
    """把表达式规范化为唯一形式：递归排序交换律子节点。"""
    if not getattr(expression, "children", None):
        return expression
    children = [canonicalize(child) for child in expression.children]
    op = (expression.operator or "").lower()
    if len(children) == 2 and op in COMMUTATIVE:
        left, right = children
        if left.to_string() > right.to_string():
            children = [right, left]
    cls = type(expression)
    if hasattr(expression, "constant"):
        return cls(
            operator=expression.operator,
            children=children,
            feature=expression.feature,
            constant=expression.constant,
        )
    return cls(
        operator=expression.operator,
        children=children,
        value=expression.value,
        feature=expression.feature,
    )


def signature(expression) -> str:
    return canonicalize(expression).to_string()
