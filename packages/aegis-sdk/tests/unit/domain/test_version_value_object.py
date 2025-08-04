"""Tests for the Version value object."""

import pytest

from aegis_sdk.domain.value_objects import Version


class TestVersion:
    """Test the Version value object."""

    def test_create_version_with_all_parts(self):
        """Test creating a version with major, minor, and patch."""
        version = Version(major=1, minor=2, patch=3)
        assert version.major == 1
        assert version.minor == 2
        assert version.patch == 3

    def test_create_version_with_defaults(self):
        """Test creating a version with default values."""
        version = Version(major=1)
        assert version.major == 1
        assert version.minor == 0
        assert version.patch == 0

    def test_version_string_representation(self):
        """Test string representation follows semantic versioning."""
        version = Version(major=2, minor=1, patch=5)
        assert str(version) == "2.1.5"

    def test_version_from_string(self):
        """Test creating version from string."""
        version = Version.from_string("3.4.5")
        assert version.major == 3
        assert version.minor == 4
        assert version.patch == 5

    def test_version_from_string_with_partial(self):
        """Test creating version from partial string."""
        version1 = Version.from_string("3.4")
        assert version1.major == 3
        assert version1.minor == 4
        assert version1.patch == 0

        version2 = Version.from_string("3")
        assert version2.major == 3
        assert version2.minor == 0
        assert version2.patch == 0

    def test_version_from_string_invalid_format(self):
        """Test that invalid version strings raise ValueError."""
        with pytest.raises(ValueError, match="Invalid version format"):
            Version.from_string("invalid")

        with pytest.raises(ValueError, match="Invalid version format"):
            Version.from_string("1.2.3.4")

        with pytest.raises(ValueError, match="Invalid version format"):
            Version.from_string("1.a.3")

    def test_version_comparison(self):
        """Test version comparison operations."""
        v1 = Version(major=1, minor=0, patch=0)
        v2 = Version(major=1, minor=0, patch=1)
        v3 = Version(major=1, minor=1, patch=0)
        v4 = Version(major=2, minor=0, patch=0)

        # Less than
        assert v1 < v2
        assert v2 < v3
        assert v3 < v4

        # Greater than
        assert v4 > v3
        assert v3 > v2
        assert v2 > v1

        # Equal
        assert v1 == Version(major=1, minor=0, patch=0)
        assert v1 != v2

        # Less than or equal
        assert v1 <= v2
        assert v1 <= Version(major=1, minor=0, patch=0)

        # Greater than or equal
        assert v2 >= v1
        assert v2 >= Version(major=1, minor=0, patch=1)

    def test_version_immutability(self):
        """Test that Version is immutable."""
        from pydantic import ValidationError

        version = Version(major=1, minor=2, patch=3)

        with pytest.raises(ValidationError, match="frozen"):
            version.major = 2

        with pytest.raises(ValidationError, match="frozen"):
            version.minor = 3

        with pytest.raises(ValidationError, match="frozen"):
            version.patch = 4

    def test_version_is_compatible_with(self):
        """Test version compatibility checking."""
        v1 = Version(major=1, minor=2, patch=3)

        # Same major version is compatible
        assert v1.is_compatible_with(Version(major=1, minor=3, patch=0))
        assert v1.is_compatible_with(Version(major=1, minor=2, patch=4))

        # Different major version is not compatible
        assert not v1.is_compatible_with(Version(major=2, minor=0, patch=0))
        assert not v1.is_compatible_with(Version(major=0, minor=9, patch=0))

    def test_version_validation(self):
        """Test version validation rules."""
        from pydantic import ValidationError

        # Negative values should raise ValidationError (handled by Field constraints)
        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Version(major=-1, minor=0, patch=0)

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Version(major=1, minor=-1, patch=0)

        with pytest.raises(ValidationError, match="greater than or equal to 0"):
            Version(major=1, minor=0, patch=-1)

    def test_version_hash(self):
        """Test that Version is hashable."""
        v1 = Version(major=1, minor=2, patch=3)
        v2 = Version(major=1, minor=2, patch=3)
        v3 = Version(major=1, minor=2, patch=4)

        # Same versions have same hash
        assert hash(v1) == hash(v2)

        # Can be used in sets
        version_set = {v1, v2, v3}
        assert len(version_set) == 2  # v1 and v2 are the same

    def test_version_bump_methods(self):
        """Test version bumping methods."""
        version = Version(major=1, minor=2, patch=3)

        # Bump patch
        new_version = version.bump_patch()
        assert new_version == Version(major=1, minor=2, patch=4)
        assert version == Version(major=1, minor=2, patch=3)  # Original unchanged

        # Bump minor
        new_version = version.bump_minor()
        assert new_version == Version(major=1, minor=3, patch=0)
        assert version == Version(major=1, minor=2, patch=3)  # Original unchanged

        # Bump major
        new_version = version.bump_major()
        assert new_version == Version(major=2, minor=0, patch=0)
        assert version == Version(major=1, minor=2, patch=3)  # Original unchanged
