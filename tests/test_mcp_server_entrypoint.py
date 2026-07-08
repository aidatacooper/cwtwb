from __future__ import annotations

from cwtwb import mcp_server


def test_mcp_server_help_alias_prints_cli_help(capsys):
    assert mcp_server.main(["-help"]) == 0

    captured = capsys.readouterr()
    assert "Tableau workbook engineering toolkit" in captured.out
    assert "cwtwb mcp" in captured.out


def test_mcp_server_runs_transport_without_help(monkeypatch):
    called = {"mcp": False}

    def fake_run():
        called["mcp"] = True

    monkeypatch.setattr(mcp_server, "_run_mcp_server", fake_run)

    assert mcp_server.main([]) == 0
    assert called["mcp"] is True
