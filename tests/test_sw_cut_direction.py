"""The new explicit reverse flag must preserve all legacy cut arguments."""
from types import SimpleNamespace
from scripts import sw_part


def test_cut_direction_is_opt_in_and_keeps_legacy_default(monkeypatch):
    calls = []
    manager = SimpleNamespace(FeatureCut4=lambda *args: calls.append(args) or object())
    model = SimpleNamespace(FeatureManager=manager)
    monkeypatch.setattr(sw_part, "_ensure_sketch_selected", lambda *args: None)
    sw_part.extrude_cut(model, "sketch", 0)
    sw_part.extrude_cut(model, "sketch", 0, reverse=True)
    assert calls[0][:4] == (True, False, False, 1)
    assert calls[1][:4] == (True, False, True, 1)
    assert calls[0][:2] + calls[0][3:] == calls[1][:2] + calls[1][3:]
