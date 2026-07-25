# -------------------------------------------------------------------------
# Copyright (c) Microsoft Corporation. All rights reserved.
# Licensed under the MIT License.
# --------------------------------------------------------------------------
"""Unit tests for ANSI gating in the shared stderr console.

On Windows terminals using a legacy code page (cp936/cp1252) raw ANSI escape
sequences are not interpreted, so an error message rendered with color arrives
as unreadable garbage. See issue #218.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from winml.modelkit.utils.console import get_console, supports_ansi


if TYPE_CHECKING:
    import pytest


class _FakeStream:
    """Minimal stream stub: isatty() drives the gate, write/flush let Rich render."""

    def __init__(self, tty: bool):
        self._tty = tty
        self.buffer: list[str] = []

    def isatty(self) -> bool:
        return self._tty

    def write(self, text: str) -> int:
        self.buffer.append(text)
        return len(text)

    def flush(self) -> None:
        return None


def test_ansi_enabled_on_interactive_tty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert supports_ansi(_FakeStream(tty=True)) is True


def test_ansi_disabled_when_not_a_tty(monkeypatch: pytest.MonkeyPatch):
    # Redirected output (pipe, file, CI log) cannot interpret escape codes.
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert supports_ansi(_FakeStream(tty=False)) is False


def test_no_color_wins_over_an_interactive_tty(monkeypatch: pytest.MonkeyPatch):
    # NO_COLOR is checked first, matching the CLI's --no-color flag which sets it.
    monkeypatch.setenv("NO_COLOR", "1")
    assert supports_ansi(_FakeStream(tty=True)) is False


def test_missing_stream_is_treated_as_unsupported(monkeypatch: pytest.MonkeyPatch):
    # A stream without isatty (or absent entirely) must not get escape codes.
    monkeypatch.delenv("NO_COLOR", raising=False)
    assert supports_ansi(object()) is False


def test_console_disables_color_when_stream_is_not_a_tty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stderr", _FakeStream(tty=False))
    assert get_console().no_color is True


def test_console_keeps_color_on_a_tty(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stderr", _FakeStream(tty=True))
    assert get_console().no_color is False


def test_rendered_error_has_no_escape_codes_without_a_tty(monkeypatch: pytest.MonkeyPatch):
    """End-to-end guard: the reported symptom was escape codes in the output."""
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr("sys.stderr", _FakeStream(tty=False))

    console = get_console()
    with console.capture() as capture:
        console.print("[bold red]Failed to load model[/bold red]")

    output = capture.get()
    assert "Failed to load model" in output
    assert "\x1b[" not in output
