import json
from pathlib import Path

import pytest

import apex_core.config as config_module
from apex_core.config import load_config


def _write_json(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _build_base_config() -> dict:
    return {
        "token": "TEST",
        "guild_ids": [1],
        "role_ids": {"admin": 99},
        "ticket_categories": {"support": 1, "billing": 2, "sales": 3},
        "operating_hours": {"start_hour_utc": 9, "end_hour_utc": 21},
        "payment_methods": [
            {"name": "Wallet", "instructions": "Use wallet"},
        ],
        "logging_channels": {"audit": 10, "payments": 11, "tickets": 12, "errors": 13},
        "roles": [
            {
                "name": "Client",
                "role_id": 1,
                "assignment_mode": "automatic_spend",
                "unlock_condition": 0,
                "discount_percent": 0,
            }
        ],
        "refund_settings": {"enabled": True, "max_days": 3, "handling_fee_percent": 10},
        "rate_limits": {"balance": {"cooldown": 60, "max_uses": 2, "per": "user"}},
    }


@pytest.fixture
def payments_payload() -> dict:
    return {
        "payment_methods": [
            {
                "name": "Wallet",
                "instructions": "Use wallet",
                "emoji": "💰",
                "metadata": {"is_enabled": True},
            }
        ],
        "order_confirmation_template": "Order #{order_id} {service_name} {variant_name} {price} {eta}",
        "refund_policy": "3 days",
    }


def test_load_config_success(tmp_path, monkeypatch, payments_payload):
    config_path = tmp_path / "config.json"
    payments_path = tmp_path / "payments.json"

    _write_json(config_path, _build_base_config())
    _write_json(payments_path, payments_payload)

    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", payments_path)

    cfg = load_config(config_path)
    assert cfg.token == "TEST"
    assert cfg.refund_settings is not None and cfg.refund_settings.max_days == 3
    assert cfg.payment_settings is not None
    assert cfg.payment_settings.order_confirmation_template.startswith("Order #")
    assert "balance" in cfg.rate_limits


def test_load_config_missing_file(tmp_path, monkeypatch):
    config_path = tmp_path / "missing.json"
    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", tmp_path / "payments.json")

    with pytest.raises(FileNotFoundError):
        load_config(config_path)


def test_rate_limit_validation_errors(tmp_path, monkeypatch, payments_payload):
    config_path = tmp_path / "config.json"
    payments_path = tmp_path / "payments.json"

    invalid_config = _build_base_config()
    invalid_config["rate_limits"] = {"balance": "invalid"}

    _write_json(config_path, invalid_config)
    _write_json(payments_path, payments_payload)

    monkeypatch.setattr(config_module, "PAYMENTS_CONFIG_PATH", payments_path)

    with pytest.raises(ValueError, match="rate_limits entry"):
        load_config(config_path)
