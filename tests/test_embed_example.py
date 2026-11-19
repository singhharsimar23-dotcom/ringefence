def test_the_embed_example_runs_offline_and_verifies():
    import importlib.util
    from pathlib import Path
    spec = importlib.util.spec_from_file_location("embed", Path(__file__).parent.parent / "examples" / "embed.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    assert m.main()["ok"] is True
