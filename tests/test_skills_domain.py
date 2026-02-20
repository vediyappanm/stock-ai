"""
Module:      tests.test_skills_domain
Purpose:     Unit tests for skills domain models
"""

# Standard Library
from datetime import datetime

# Third Party
import pytest

# Local / Internal
from skills_domain.models import (
    Result,
    ResultMetadata,
    Skill,
    SkillMetadata,
    SkillResource,
    ValidationIssue,
    ValidationResult,
    ValidationSeverity,
)


class TestResultMetadata:
    """Test ResultMetadata validation."""

    def test_valid_metadata_creation(self):
        """Happy path: valid metadata creation."""
        metadata = ResultMetadata(
            correlation_id="test-123",
            source="test_source",
            retry_count=0
        )
        assert metadata.correlation_id == "test-123"
        assert metadata.source == "test_source"
        assert metadata.retry_count == 0

    def test_empty_correlation_id_raises(self):
        """Error path: empty correlation_id raises ValueError."""
        with pytest.raises(ValueError, match="correlation_id cannot be empty"):
            ResultMetadata(correlation_id="", source="test")

    def test_empty_source_raises(self):
        """Error path: empty source raises ValueError."""
        with pytest.raises(ValueError, match="source cannot be empty"):
            ResultMetadata(correlation_id="test", source="")

    def test_negative_retry_count_raises(self):
        """Error path: negative retry_count raises ValueError."""
        with pytest.raises(ValueError, match="retry_count cannot be negative"):
            ResultMetadata(correlation_id="test", source="test", retry_count=-1)


class TestResult:
    """Test Result wrapper."""

    def test_successful_result(self):
        """Happy path: successful result with data."""
        result = Result(success=True, data="test_data")
        assert result.success is True
        assert result.data == "test_data"
        assert result.unwrap() == "test_data"

    def test_failed_result_requires_error_message(self):
        """Error path: failed result without error_message raises."""
        with pytest.raises(ValueError, match="Failed Result must include error_message"):
            Result(success=False)

    def test_failed_result_with_error_message(self):
        """Happy path: failed result with error message."""
        result = Result(
            success=False,
            error_code="TEST_ERROR",
            error_message="Test error occurred"
        )
        assert result.success is False
        assert result.error_code == "TEST_ERROR"

    def test_unwrap_on_failed_result_raises(self):
        """Error path: unwrap on failed result raises RuntimeError."""
        result = Result(
            success=False,
            error_code="TEST_ERROR",
            error_message="Test error"
        )
        with pytest.raises(RuntimeError, match=r"\[TEST_ERROR\] Test error"):
            result.unwrap()


class TestSkillMetadata:
    """Test SkillMetadata validation."""

    def test_valid_skill_metadata(self):
        """Happy path: valid skill metadata creation."""
        metadata = SkillMetadata(
            name="test-skill",
            description="A test skill for validation"
        )
        assert metadata.name == "test-skill"
        assert metadata.description == "A test skill for validation"

    def test_empty_name_raises(self):
        """Error path: empty name raises ValueError."""
        with pytest.raises(ValueError, match="name cannot be empty"):
            SkillMetadata(name="", description="test")

    def test_empty_description_raises(self):
        """Error path: empty description raises ValueError."""
        with pytest.raises(ValueError, match="description cannot be empty"):
            SkillMetadata(name="test", description="")

    def test_name_too_long_raises(self):
        """Error path: name exceeding max length raises ValueError."""
        long_name = "a" * 65
        with pytest.raises(ValueError, match="name too long"):
            SkillMetadata(name=long_name, description="test")

    def test_description_too_long_raises(self):
        """Error path: description exceeding max length raises ValueError."""
        long_desc = "a" * 1025
        with pytest.raises(ValueError, match="description too long"):
            SkillMetadata(name="test", description=long_desc)

    def test_compatibility_too_long_raises(self):
        """Error path: compatibility exceeding max length raises ValueError."""
        long_compat = "a" * 501
        with pytest.raises(ValueError, match="compatibility too long"):
            SkillMetadata(
                name="test",
                description="test",
                compatibility=long_compat
            )


class TestSkillResource:
    """Test SkillResource validation."""

    def test_valid_resource(self):
        """Happy path: valid resource creation."""
        resource = SkillResource(
            path="scripts/test.py",
            resource_type="script",
            size_bytes=1024
        )
        assert resource.path == "scripts/test.py"
        assert resource.resource_type == "script"
        assert resource.size_bytes == 1024

    def test_empty_path_raises(self):
        """Error path: empty path raises ValueError."""
        with pytest.raises(ValueError, match="path cannot be empty"):
            SkillResource(path="", resource_type="script", size_bytes=100)

    def test_empty_resource_type_raises(self):
        """Error path: empty resource_type raises ValueError."""
        with pytest.raises(ValueError, match="resource_type cannot be empty"):
            SkillResource(path="test.py", resource_type="", size_bytes=100)

    def test_negative_size_raises(self):
        """Error path: negative size_bytes raises ValueError."""
        with pytest.raises(ValueError, match="size_bytes cannot be negative"):
            SkillResource(path="test.py", resource_type="script", size_bytes=-1)


class TestSkill:
    """Test Skill model."""

    def test_valid_skill(self):
        """Happy path: valid skill creation."""
        metadata = SkillMetadata(name="test-skill", description="Test skill")
        skill = Skill(metadata=metadata, body_content="# Test Skill\n\nContent here")
        assert skill.metadata.name == "test-skill"
        assert skill.body_content == "# Test Skill\n\nContent here"

    def test_empty_body_content_raises(self):
        """Error path: empty body_content raises ValueError."""
        metadata = SkillMetadata(name="test", description="test")
        with pytest.raises(ValueError, match="body_content cannot be empty"):
            Skill(metadata=metadata, body_content="")


class TestValidationResult:
    """Test ValidationResult model."""

    def test_valid_result_no_issues(self):
        """Happy path: validation result with no issues."""
        result = ValidationResult(is_valid=True, issues=[])
        assert result.is_valid is True
        assert result.has_errors() is False
        assert result.has_warnings() is False
        assert result.error_count() == 0
        assert result.warning_count() == 0

    def test_result_with_errors(self):
        """Happy path: validation result with errors."""
        issues = [
            ValidationIssue(
                severity=ValidationSeverity.ERROR,
                message="Test error"
            )
        ]
        result = ValidationResult(is_valid=False, issues=issues)
        assert result.is_valid is False
        assert result.has_errors() is True
        assert result.error_count() == 1

    def test_result_with_warnings(self):
        """Happy path: validation result with warnings."""
        issues = [
            ValidationIssue(
                severity=ValidationSeverity.WARNING,
                message="Test warning"
            )
        ]
        result = ValidationResult(is_valid=True, issues=issues)
        assert result.has_warnings() is True
        assert result.warning_count() == 1

    def test_result_with_mixed_issues(self):
        """Happy path: validation result with mixed severity issues."""
        issues = [
            ValidationIssue(severity=ValidationSeverity.ERROR, message="Error 1"),
            ValidationIssue(severity=ValidationSeverity.ERROR, message="Error 2"),
            ValidationIssue(severity=ValidationSeverity.WARNING, message="Warning 1"),
        ]
        result = ValidationResult(is_valid=False, issues=issues)
        assert result.error_count() == 2
        assert result.warning_count() == 1
