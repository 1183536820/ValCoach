"""Input validation utilities for login/register forms."""

import re
from typing import Optional


def validate_email(email: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not email or not email.strip():
        return "邮箱不能为空"
    email = email.strip()
    if len(email) > 254:
        return "邮箱地址过长"
    if "@" not in email or "." not in email.split("@")[-1]:
        return "邮箱格式不正确"
    return None


def validate_password(password: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not password:
        return "密码不能为空"
    if len(password) < 6:
        return "密码长度不能少于 6 位"
    if len(password) > 128:
        return "密码长度不能超过 128 位"
    return None


def validate_game_name(name: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not name or not name.strip():
        return "游戏 ID 不能为空"
    if len(name) > 50:
        return "游戏 ID 过长"
    return None


def validate_tag_line(tag: str) -> Optional[str]:
    """Return error message if invalid, None if valid."""
    if not tag or not tag.strip():
        return "Tagline 不能为空"
    if len(tag) > 20:
        return "Tagline 过长"
    if not re.match(r'^[a-zA-Z0-9_]+$', tag.strip()):
        return "Tagline 只能包含字母、数字和下划线"
    return None
