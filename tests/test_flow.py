"""The pipeline model behind the Try it canvas and the demo strips: which node is idle, running, waiting for a person, or stopped."""
import json
import shutil
import subprocess

import pytest

from ringfence.config import ROOT

node = shutil.which("node")


@pytest.mark.skipif(node is None, reason="node is not installed")
def test_flow_model_states():
    r = subprocess.run([node, str(ROOT / "tests" / "flow_model.js")], check=False, capture_output=True, text=True, encoding="utf-8")
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout) == []
