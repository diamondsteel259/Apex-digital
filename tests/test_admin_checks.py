from __future__ import annotations

from types import SimpleNamespace

import pytest

import apex_core.utils.admin_checks as admin_checks


def test_admin_command_check_false_without_guild(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_checks, "is_admin", lambda *_args, **_kwargs: True)

    interaction = SimpleNamespace(guild=None, client=SimpleNamespace(config={}), user=object())
    assert admin_checks.admin_command_check(interaction) is False


def test_admin_command_check_true_when_is_admin(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_checks, "is_admin", lambda *_args, **_kwargs: True)

    interaction = SimpleNamespace(
        guild=object(),
        client=SimpleNamespace(config={"role_ids": {}}),
        user=object(),
    )
    assert admin_checks.admin_command_check(interaction) is True


def test_admin_only_exposes_predicate(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(admin_checks, "is_admin", lambda *_args, **_kwargs: False)

    decorator = admin_checks.admin_only()

    @decorator
    def dummy():
        pass

    dummy()  # execute the function body for coverage

    checks = getattr(dummy, "__discord_app_commands_checks__", None)
    assert checks
    predicate = checks[0]

    interaction = SimpleNamespace(
        guild=object(),
        client=SimpleNamespace(config={"role_ids": {}}),
        user=object(),
    )
    assert predicate(interaction) is False
