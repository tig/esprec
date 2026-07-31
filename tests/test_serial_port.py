"""Control-line policy: POSIX hosts must not touch DTR/RTS."""

from __future__ import annotations

import os
import types

import pytest

from esprec import serial_port
from esprec.serial_port import AUTO, DEASSERT, KEEP, default_mode, resolve_mode


@pytest.fixture(autouse=True)
def _no_env(monkeypatch):
    monkeypatch.delenv("ESPREC_CONTROL_LINES", raising=False)


def _os_name(monkeypatch, name):
    monkeypatch.setattr(serial_port.os, "name", name)


def test_posix_keeps_control_lines(monkeypatch):
    _os_name(monkeypatch, "posix")
    assert default_mode() == KEEP
    assert resolve_mode() == KEEP


def test_windows_still_deasserts(monkeypatch):
    _os_name(monkeypatch, "nt")
    assert default_mode() == DEASSERT
    assert resolve_mode() == DEASSERT


def test_env_overrides_the_host(monkeypatch):
    _os_name(monkeypatch, "posix")
    monkeypatch.setenv("ESPREC_CONTROL_LINES", "deassert")
    assert resolve_mode() == DEASSERT
    monkeypatch.setenv("ESPREC_CONTROL_LINES", "KEEP")  # case-insensitive
    assert resolve_mode() == KEEP


def test_argument_beats_env(monkeypatch):
    _os_name(monkeypatch, "posix")
    monkeypatch.setenv("ESPREC_CONTROL_LINES", "deassert")
    assert resolve_mode(KEEP) == KEEP


def test_auto_is_accepted_explicitly(monkeypatch):
    _os_name(monkeypatch, "posix")
    assert resolve_mode(AUTO) == KEEP


def test_bad_mode_fails_closed():
    with pytest.raises(SystemExit, match="invalid control-lines mode"):
        resolve_mode("sometimes")


def test_bad_env_fails_closed(monkeypatch):
    monkeypatch.setenv("ESPREC_CONTROL_LINES", "off")
    with pytest.raises(SystemExit, match="invalid control-lines mode"):
        resolve_mode()


# --- HUPCL: keep the lines asserted between sessions -------------------------


@pytest.mark.skipif(os.name != "posix", reason="termios is POSIX only")
def test_clear_hupcl_turns_it_off():
    import termios

    master, slave = os.openpty()
    try:
        attrs = termios.tcgetattr(slave)
        attrs[2] |= termios.HUPCL
        termios.tcsetattr(slave, termios.TCSANOW, attrs)

        assert serial_port._clear_hupcl(types.SimpleNamespace(fileno=lambda: slave))
        assert not termios.tcgetattr(slave)[2] & termios.HUPCL
    finally:
        os.close(master)
        os.close(slave)


@pytest.mark.skipif(os.name != "posix", reason="termios is POSIX only")
def test_clear_hupcl_is_idempotent():
    import termios

    master, slave = os.openpty()
    try:
        fake = types.SimpleNamespace(fileno=lambda: slave)
        assert serial_port._clear_hupcl(fake)
        assert serial_port._clear_hupcl(fake)
        assert not termios.tcgetattr(slave)[2] & termios.HUPCL
    finally:
        os.close(master)
        os.close(slave)


def test_clear_hupcl_skipped_on_windows(monkeypatch):
    _os_name(monkeypatch, "nt")
    assert serial_port._clear_hupcl(object()) is False


def test_clear_hupcl_survives_a_port_without_termios(monkeypatch):
    """--fake ports and closed handles must not break the open path."""
    _os_name(monkeypatch, "posix")
    assert serial_port._clear_hupcl(types.SimpleNamespace(fileno=lambda: -1)) is False
    assert serial_port._clear_hupcl(object()) is False
