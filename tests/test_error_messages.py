from __future__ import annotations

from apex_core.utils.error_messages import get_error_message


def test_get_error_message_formats_template() -> None:
    msg = get_error_message(
        "insufficient_balance",
        current_balance="$1.00",
        required_amount="$2.00",
    )

    assert "Insufficient Balance" in msg
    assert "$1.00" in msg
    assert "$2.00" in msg


def test_get_error_message_handles_missing_kwargs() -> None:
    msg = get_error_message("insufficient_balance")
    assert msg.startswith("❌")
    assert "Insufficient Balance" in msg


def test_get_error_message_unknown_type_returns_default() -> None:
    msg = get_error_message("does_not_exist")
    assert "An error occurred" in msg
