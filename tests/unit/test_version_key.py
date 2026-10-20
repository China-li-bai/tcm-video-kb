"""version_key stability and change detection."""
from tcmkb_core.ids import version_key

def test_version_key_stable():
    a = version_key("s06_clean", "1", {"gap": 1.2}, upstream_hash="abc", lexicon_hash="lex1")
    b = version_key("s06_clean", "1", {"gap": 1.2}, upstream_hash="abc", lexicon_hash="lex1")
    assert a == b
    assert len(a) == 12

def test_version_key_changes_on_config():
    a = version_key("s06_clean", "1", {"gap": 1.2}, upstream_hash="abc")
    b = version_key("s06_clean", "1", {"gap": 1.5}, upstream_hash="abc")
    assert a != b

def test_version_key_changes_on_upstream():
    a = version_key("s06_clean", "1", {}, upstream_hash="aaa")
    b = version_key("s06_clean", "1", {}, upstream_hash="bbb")
    assert a != b

def test_version_key_changes_on_lexicon():
    a = version_key("s06_clean", "1", {}, lexicon_hash="v1")
    b = version_key("s06_clean", "1", {}, lexicon_hash="v2")
    assert a != b

def test_version_key_sorts_config_keys():
    a = version_key("s04", "1", {"b": 1, "a": 2})
    b = version_key("s04", "1", {"a": 2, "b": 1})
    assert a == b
