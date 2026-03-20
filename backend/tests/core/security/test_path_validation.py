import pytest

from app.core.errors import PathValidationError
from app.core.security.path_validation import validate_volume_path


class TestValidateVolumePath:
    def test_valid_simple_path(self):
        assert validate_volume_path("file.txt") == "file.txt"

    def test_valid_nested_path(self):
        assert validate_volume_path("dir/subdir/file.txt") == "dir/subdir/file.txt"

    def test_strips_leading_slash_normalization(self):
        # PurePosixPath("/foo") is absolute — should be rejected
        with pytest.raises(PathValidationError, match="Absolute"):
            validate_volume_path("/foo/bar.txt")

    def test_rejects_empty_string(self):
        with pytest.raises(PathValidationError, match="empty"):
            validate_volume_path("")

    def test_rejects_whitespace_only(self):
        with pytest.raises(PathValidationError, match="empty"):
            validate_volume_path("   ")

    def test_rejects_dot_dot(self):
        with pytest.raises(PathValidationError, match="traversal"):
            validate_volume_path("foo/../etc/passwd")

    def test_rejects_leading_dot_dot(self):
        with pytest.raises(PathValidationError, match="traversal"):
            validate_volume_path("../secret")

    def test_rejects_bare_dot_dot(self):
        with pytest.raises(PathValidationError, match="traversal"):
            validate_volume_path("..")

    def test_rejects_absolute_path(self):
        with pytest.raises(PathValidationError, match="Absolute"):
            validate_volume_path("/etc/passwd")

    def test_rejects_null_bytes(self):
        with pytest.raises(PathValidationError, match="Null"):
            validate_volume_path("foo\x00bar")

    def test_normalizes_redundant_separators(self):
        result = validate_volume_path("dir//file.txt")
        assert ".." not in result
        # PurePosixPath normalizes "dir//file.txt" to "dir/file.txt"
        assert result == "dir/file.txt"

    def test_rejects_dot_only(self):
        with pytest.raises(PathValidationError, match="empty"):
            validate_volume_path(".")
