from __future__ import annotations

import pytest

from apex_market_scraper.cli import main


def test_cli_prints_help_when_no_args(capsys: pytest.CaptureFixture[str]) -> None:
    main([])
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower()
