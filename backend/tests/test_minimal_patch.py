from app.domain.agents.minimal_patch import (
    filter_substantive_file_changes,
    has_substantive_change,
)


def test_has_substantive_change_real_edit():
    old = "  - targets: ['host.docker.internal:5500']\n"
    new = "  - targets: ['lumina-api:5500']\n"
    assert has_substantive_change(old, new)


def test_ignores_trailing_blank_lines():
    old = "export { foo };\n\n\n\n"
    new = "export { foo };\n"
    assert not has_substantive_change(old, new)


def test_ignores_eof_newline_only():
    old = '{\n  "name": "app"\n}\n'
    new = '{\n  "name": "app"\n}'
    assert not has_substantive_change(old, new)


def test_filter_drops_whitespace_only_files():
    originals = {
        "prometheus.yml": "targets: ['host.docker.internal:5500']\n",
        "other.js": "const x = 1;\n\n\n",
    }
    generated = {
        "prometheus.yml": "targets: ['lumina-api:5500']\n",
        "other.js": "const x = 1;\n",
    }
    result = filter_substantive_file_changes(generated, originals)
    assert list(result.keys()) == ["prometheus.yml"]
