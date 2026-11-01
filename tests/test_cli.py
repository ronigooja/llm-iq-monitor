from llm_iq_monitor import cli


def test_run_and_manual_call_sync_entries(monkeypatch):
    called = []
    monkeypatch.setattr("llm_iq_monitor.runner_main.serve", lambda: called.append(("run",)))
    monkeypatch.setattr("llm_iq_monitor.runner_main.manual", lambda models: called.append(("manual", models)))
    cli.main(["run"])
    cli.main(["manual", "alpha", "beta"])
    assert called == [("run",), ("manual", ["alpha", "beta"])]
