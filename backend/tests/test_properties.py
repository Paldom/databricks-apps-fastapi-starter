"""Property-based tests for pure helper functions."""

from hypothesis import given
from hypothesis import strategies as st

from app.agents.response_utils import response_to_text, text_to_response
from app.core.observability import safe_attr


@given(st.text())
def test_text_response_roundtrip(text):
    """Wrapping text in a response and extracting it is lossless."""
    assert response_to_text(text_to_response(text)) == text


@given(
    st.one_of(
        st.none(),
        st.booleans(),
        st.integers(),
        st.floats(allow_nan=False),
        st.text(),
        st.lists(st.text()),
        st.dictionaries(st.text(), st.integers()),
    )
)
def test_safe_attr_is_bounded_span_value(value):
    """safe_attr always yields an OTel-safe scalar; strings are truncated."""
    result = safe_attr(value)
    assert isinstance(result, str | int | float | bool)
    if isinstance(result, str):
        assert len(result) <= 256
