import pytest

from app.core.code_safety import UnsafeGeneratedCodeError, scan_generated_code


def test_allows_safe_python():
    scan_generated_code({"app.py": "def hello():\n    return 1\n"})


def test_blocks_subprocess_in_python():
    with pytest.raises(UnsafeGeneratedCodeError, match="subprocess"):
        scan_generated_code({"app.py": "import subprocess\nsubprocess.run(['ls'])\n"})


def test_ignores_yaml_config():
    scan_generated_code({"prometheus.yml": "scrape_configs:\n  - job_name: api\n"})


def test_blocks_eval_in_js():
    with pytest.raises(UnsafeGeneratedCodeError, match="eval"):
        scan_generated_code({"index.js": "eval('alert(1)')\n"})
