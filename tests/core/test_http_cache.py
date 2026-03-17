from app.core.http_cache import build_etag, if_none_match_matches


# ---------------------------------------------------------------------------
# build_etag
# ---------------------------------------------------------------------------


def test_build_etag_deterministic():
    payload = {"a": 1, "b": 2}
    assert build_etag(payload) == build_etag(payload)


def test_build_etag_quoted():
    etag = build_etag({"x": 1})
    assert etag.startswith('"')
    assert etag.endswith('"')


def test_build_etag_different_payloads_differ():
    assert build_etag({"a": 1}) != build_etag({"a": 2})


def test_build_etag_key_order_irrelevant():
    """sorted keys means order doesn't matter."""
    assert build_etag({"b": 2, "a": 1}) == build_etag({"a": 1, "b": 2})


# ---------------------------------------------------------------------------
# if_none_match_matches
# ---------------------------------------------------------------------------


def test_none_header():
    assert if_none_match_matches(None, '"abc"') is False


def test_empty_header():
    assert if_none_match_matches("", '"abc"') is False


def test_exact_match():
    assert if_none_match_matches('"abc"', '"abc"') is True


def test_no_match():
    assert if_none_match_matches('"def"', '"abc"') is False


def test_multiple_values():
    assert if_none_match_matches('"aaa", "bbb", "ccc"', '"bbb"') is True


def test_multiple_values_no_match():
    assert if_none_match_matches('"aaa", "bbb"', '"ccc"') is False


def test_wildcard():
    assert if_none_match_matches("*", '"anything"') is True
