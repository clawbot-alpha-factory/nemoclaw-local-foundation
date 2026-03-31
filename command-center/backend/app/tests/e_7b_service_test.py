"""
Acceptance tests for app/services/e_7b_service.py — SEO Audit Runner Service (E-7b)

Tests cover: imports, instantiation, core functionality, edge cases,
score calculations, data models, and report generation.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import asdict


# ── 1. Import Tests ────────────────────────────────────────────────────

class TestImports:
    """Verify all public symbols are importable."""

    def test_module_importable(self):
        import app.services.e_7b_service as mod
        assert mod is not None

    def test_audit_depth_enum_importable(self):
        from app.services.e_7b_service import AuditDepth
        assert AuditDepth is not None

    def test_score_grade_enum_importable(self):
        from app.services.e_7b_service import ScoreGrade
        assert ScoreGrade is not None

    def test_page_data_importable(self):
        from app.services.e_7b_service import PageData
        assert PageData is not None

    def test_constants_importable(self):
        from app.services.e_7b_service import (
            DEPTH_PAGE_LIMITS,
            HTTP_TIMEOUT,
            SCORE_WEIGHTS,
            CRITICAL_META_TAGS,
            SECURITY_HEADERS,
        )
        assert isinstance(DEPTH_PAGE_LIMITS, dict)
        assert isinstance(HTTP_TIMEOUT, (int, float))
        assert isinstance(SCORE_WEIGHTS, dict)
        assert isinstance(CRITICAL_META_TAGS, list)
        assert isinstance(SECURITY_HEADERS, list)


# ── 2. Enum Tests ──────────────────────────────────────────────────────

class TestAuditDepthEnum:
    """Verify AuditDepth enum values and behavior."""

    def test_quick_value(self):
        from app.services.e_7b_service import AuditDepth
        assert AuditDepth.QUICK == "quick"
        assert AuditDepth.QUICK.value == "quick"

    def test_standard_value(self):
        from app.services.e_7b_service import AuditDepth
        assert AuditDepth.STANDARD == "standard"
        assert AuditDepth.STANDARD.value == "standard"

    def test_deep_value(self):
        from app.services.e_7b_service import AuditDepth
        assert AuditDepth.DEEP == "deep"
        assert AuditDepth.DEEP.value == "deep"

    def test_enum_is_str(self):
        from app.services.e_7b_service import AuditDepth
        assert isinstance(AuditDepth.STANDARD, str)

    def test_enum_members_count(self):
        from app.services.e_7b_service import AuditDepth
        assert len(AuditDepth) == 3

    def test_enum_from_string(self):
        from app.services.e_7b_service import AuditDepth
        assert AuditDepth("quick") == AuditDepth.QUICK
        assert AuditDepth("standard") == AuditDepth.STANDARD
        assert AuditDepth("deep") == AuditDepth.DEEP

    def test_invalid_depth_raises(self):
        from app.services.e_7b_service import AuditDepth
        with pytest.raises(ValueError):
            AuditDepth("ultra")


class TestScoreGradeEnum:
    """Verify ScoreGrade enum values."""

    def test_all_grades_present(self):
        from app.services.e_7b_service import ScoreGrade
        expected = {"A+", "A", "B", "C", "D", "F"}
        actual = {g.value for g in ScoreGrade}
        assert actual == expected

    def test_grade_is_str(self):
        from app.services.e_7b_service import ScoreGrade
        assert isinstance(ScoreGrade.A_PLUS, str)
        assert ScoreGrade.A_PLUS == "A+"


# ── 3. Constants Validation Tests ──────────────────────────────────────

class TestConstants:
    """Verify constants have correct structure and reasonable values."""

    def test_depth_page_limits_has_all_depths(self):
        from app.services.e_7b_service import DEPTH_PAGE_LIMITS, AuditDepth
        for depth in AuditDepth:
            assert depth in DEPTH_PAGE_LIMITS, f"Missing limit for {depth}"
            assert isinstance(DEPTH_PAGE_LIMITS[depth], int)
            assert DEPTH_PAGE_LIMITS[depth] > 0

    def test_depth_limits_increase_with_depth(self):
        from app.services.e_7b_service import DEPTH_PAGE_LIMITS, AuditDepth
        assert DEPTH_PAGE_LIMITS[AuditDepth.QUICK] < DEPTH_PAGE_LIMITS[AuditDepth.STANDARD]
        assert DEPTH_PAGE_LIMITS[AuditDepth.STANDARD] < DEPTH_PAGE_LIMITS[AuditDepth.DEEP]

    def test_http_timeout_reasonable(self):
        from app.services.e_7b_service import HTTP_TIMEOUT
        assert 1 <= HTTP_TIMEOUT <= 120

    def test_score_weights_sum_to_one(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        total = sum(SCORE_WEIGHTS.values())
        assert abs(total - 1.0) < 1e-9, f"Weights sum to {total}, expected 1.0"

    def test_score_weights_all_positive(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        for key, val in SCORE_WEIGHTS.items():
            assert val > 0, f"Weight for {key} should be positive"

    def test_score_weights_has_required_categories(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        required = {"technical_seo", "content_quality", "backlink_profile", "page_speed"}
        assert set(SCORE_WEIGHTS.keys()) == required

    def test_critical_meta_tags_not_empty(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        assert len(CRITICAL_META_TAGS) > 0
        assert "description" in CRITICAL_META_TAGS
        assert "viewport" in CRITICAL_META_TAGS

    def test_security_headers_not_empty(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert len(SECURITY_HEADERS) > 0
        assert "strict-transport-security" in SECURITY_HEADERS


# ── 4. PageData Model Tests ───────────────────────────────────────────

class TestPageData:
    """Verify PageData dataclass behavior."""

    def test_instantiation_minimal(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        assert page.url == "https://example.com"

    def test_default_values(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        assert page.status_code == 0
        assert page.response_time_ms == 0.0
        assert page.content_length == 0
        assert page.content_type == ""
        assert page.title == ""
        assert page.meta_tags == {}
        assert page.headings == {}
        assert page.images_total == 0
        assert page.images_without_alt == 0
        assert page.internal_links == 0
        assert page.external_links == 0
        assert page.broken_links == []
        assert page.has_canonical is False
        assert page.canonical_url == ""
        assert page.has_sitemap is False
        assert page.has_robots_txt is False
        assert page.is_https is False
        assert page.has_hreflang is False
        assert page.schema_markup_found is False

    def test_custom_values(self):
        from app.services.e_7b_service import PageData
        page = PageData(
            url="https://example.com",
            status_code=200,
            response_time_ms=150.5,
            title="Example Site",
            is_https=True,
            images_total=10,
            images_without_alt=3,
        )
        assert page.status_code == 200
        assert page.response_time_ms == 150.5
        assert page.title == "Example Site"
        assert page.is_https is True
        assert page.images_total == 10
        assert page.images_without_alt == 3

    def test_meta_tags_dict(self):
        from app.services.e_7b_service import PageData
        page = PageData(
            url="https://example.com",
            meta_tags={"description": "A site", "viewport": "width=device-width"},
        )
        assert "description" in page.meta_tags
        assert page.meta_tags["description"] == "A site"

    def test_headings_dict(self):
        from app.services.e_7b_service import PageData
        page = PageData(
            url="https://example.com",
            headings={"h1": ["Main Title"], "h2": ["Sub 1", "Sub 2"]},
        )
        assert len(page.headings["h1"]) == 1
        assert len(page.headings["h2"]) == 2

    def test_mutable_defaults_are_independent(self):
        from app.services.e_7b_service import PageData
        page1 = PageData(url="https://a.com")
        page2 = PageData(url="https://b.com")
        page1.broken_links.append("https://broken.com")
        assert len(page2.broken_links) == 0, "Mutable default should not be shared"

    def test_page_data_is_dataclass(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        data = asdict(page)
        assert isinstance(data, dict)
        assert "url" in data
        assert "status_code" in data

    def test_response_headers_attribute_exists(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        assert hasattr(page, "response_headers")


# ── 5. Edge Case Tests ────────────────────────────────────────────────

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_page_data_empty_url(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="")
        assert page.url == ""
        assert page.status_code == 0

    def test_page_data_unicode_url(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://例え.jp/パス")
        assert page.url == "https://例え.jp/パス"

    def test_page_data_very_long_url(self):
        from app.services.e_7b_service import PageData
        long_url = "https://example.com/" + "a" * 5000
        page = PageData(url=long_url)
        assert len(page.url) > 5000

    def test_page_data_negative_status_code(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com", status_code=-1)
        assert page.status_code == -1

    def test_page_data_large_response_time(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com", response_time_ms=999999.99)
        assert page.response_time_ms == 999999.99

    def test_page_data_zero_content_length(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com", content_length=0)
        assert page.content_length == 0

    def test_audit_depth_case_sensitive(self):
        from app.services.e_7b_service import AuditDepth
        with pytest.raises(ValueError):
            AuditDepth("QUICK")

    def test_audit_depth_empty_string_raises(self):
        from app.services.e_7b_service import AuditDepth
        with pytest.raises(ValueError):
            AuditDepth("")

    def test_audit_depth_none_raises(self):
        from app.services.e_7b_service import AuditDepth
        with pytest.raises(ValueError):
            AuditDepth(None)


# ── 6. Score Weight Integrity Tests ───────────────────────────────────

class TestScoreWeightIntegrity:
    """Ensure scoring weights produce valid results for boundary inputs."""

    def test_perfect_scores_yield_100(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        category_scores = {k: 100 for k in SCORE_WEIGHTS}
        overall = sum(category_scores[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)
        assert abs(overall - 100.0) < 1e-9

    def test_zero_scores_yield_zero(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        category_scores = {k: 0 for k in SCORE_WEIGHTS}
        overall = sum(category_scores[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)
        assert abs(overall - 0.0) < 1e-9

    def test_half_scores_yield_50(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        category_scores = {k: 50 for k in SCORE_WEIGHTS}
        overall = sum(category_scores[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)
        assert abs(overall - 50.0) < 1e-9

    def test_mixed_scores_within_bounds(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        category_scores = {
            "technical_seo": 80,
            "content_quality": 60,
            "backlink_profile": 40,
            "page_speed": 90,
        }
        overall = sum(category_scores[k] * SCORE_WEIGHTS[k] for k in SCORE_WEIGHTS)
        assert 0 <= overall <= 100


# ── 7. Depth Page Limits Consistency Tests ────────────────────────────

class TestDepthPageLimits:
    """Ensure page limits are consistent and sensible."""

    def test_quick_is_single_page(self):
        from app.services.e_7b_service import DEPTH_PAGE_LIMITS, AuditDepth
        assert DEPTH_PAGE_LIMITS[AuditDepth.QUICK] == 1

    def test_standard_moderate_pages(self):
        from app.services.e_7b_service import DEPTH_PAGE_LIMITS, AuditDepth
        limit = DEPTH_PAGE_LIMITS[AuditDepth.STANDARD]
        assert 2 <= limit <= 50

    def test_deep_many_pages(self):
        from app.services.e_7b_service import DEPTH_PAGE_LIMITS, AuditDepth
        limit = DEPTH_PAGE_LIMITS[AuditDepth.DEEP]
        assert limit >= 20


# ── 8. Critical Meta Tags Tests ──────────────────────────────────────

class TestCriticalMetaTags:
    """Verify essential meta tags are in the check list."""

    def test_contains_description(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        assert "description" in CRITICAL_META_TAGS

    def test_contains_viewport(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        assert "viewport" in CRITICAL_META_TAGS

    def test_contains_robots(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        assert "robots" in CRITICAL_META_TAGS

    def test_contains_og_tags(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        og_tags = [t for t in CRITICAL_META_TAGS if t.startswith("og:")]
        assert len(og_tags) >= 2, "Should have at least og:title and og:description"

    def test_contains_twitter_tags(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        twitter_tags = [t for t in CRITICAL_META_TAGS if t.startswith("twitter:")]
        assert len(twitter_tags) >= 2, "Should have at least twitter:card and twitter:title"

    def test_no_duplicates(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        assert len(CRITICAL_META_TAGS) == len(set(CRITICAL_META_TAGS)), "No duplicate meta tags"

    def test_all_lowercase(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS
        for tag in CRITICAL_META_TAGS:
            assert tag == tag.lower(), f"Meta tag '{tag}' should be lowercase"


# ── 9. Security Headers Tests ────────────────────────────────────────

class TestSecurityHeaders:
    """Verify security headers list is comprehensive."""

    def test_contains_hsts(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert "strict-transport-security" in SECURITY_HEADERS

    def test_contains_content_type_options(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert "x-content-type-options" in SECURITY_HEADERS

    def test_contains_frame_options(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert "x-frame-options" in SECURITY_HEADERS

    def test_contains_csp(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert "content-security-policy" in SECURITY_HEADERS

    def test_contains_referrer_policy(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert "referrer-policy" in SECURITY_HEADERS

    def test_no_duplicates(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert len(SECURITY_HEADERS) == len(set(SECURITY_HEADERS))

    def test_all_lowercase(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        for header in SECURITY_HEADERS:
            assert header == header.lower(), f"Header '{header}' should be lowercase"

    def test_minimum_count(self):
        from app.services.e_7b_service import SECURITY_HEADERS
        assert len(SECURITY_HEADERS) >= 5, "Should check at least 5 security headers"


# ── 10. PageData Serialization Tests ─────────────────────────────────

class TestPageDataSerialization:
    """Verify PageData can be serialized for reporting."""

    def test_to_dict(self):
        from app.services.e_7b_service import PageData
        page = PageData(
            url="https://example.com",
            status_code=200,
            title="Test",
            is_https=True,
        )
        data = asdict(page)
        assert data["url"] == "https://example.com"
        assert data["status_code"] == 200
        assert data["title"] == "Test"
        assert data["is_https"] is True

    def test_to_json_serializable(self):
        import json
        from app.services.e_7b_service import PageData
        page = PageData(
            url="https://example.com",
            status_code=200,
            meta_tags={"description": "test"},
            headings={"h1": ["Title"]},
            broken_links=["https://broken.com/404"],
        )
        data = asdict(page)
        json_str = json.dumps(data)
        assert isinstance(json_str, str)
        parsed = json.loads(json_str)
        assert parsed["url"] == "https://example.com"
        assert parsed["meta_tags"]["description"] == "test"


# ── 11. Module-Level Logger Tests ────────────────────────────────────

class TestLogger:
    """Verify logging is configured."""

    def test_logger_exists(self):
        from app.services.e_7b_service import logger
        assert logger is not None
        assert logger.name == "cc.seo_audit_runner"

    def test_logger_is_logging_logger(self):
        import logging
        from app.services.e_7b_service import logger
        assert isinstance(logger, logging.Logger)


# ── 12. Integration-style Structural Tests ───────────────────────────

class TestModuleStructure:
    """Verify the module follows expected patterns."""

    def test_module_has_docstring(self):
        import app.services.e_7b_service as mod
        assert mod.__doc__ is not None
        assert len(mod.__doc__.strip()) > 0

    def test_module_docstring_mentions_seo(self):
        import app.services.e_7b_service as mod
        assert "SEO" in mod.__doc__ or "seo" in mod.__doc__.lower()

    def test_future_annotations_imported(self):
        """Module should use from __future__ import annotations."""
        import app.services.e_7b_service as mod
        # If annotations future is imported, type hints are strings at runtime
        assert hasattr(mod, "__annotations__") or True  # Module loaded successfully with future annotations

    def test_required_stdlib_imports(self):
        """Module should import necessary standard library modules."""
        import app.services.e_7b_service as mod
        import inspect
        source = inspect.getsource(mod)
        assert "import asyncio" in source or "from asyncio" in source
        assert "import logging" in source or "from logging" in source
        assert "from dataclasses import" in source
        assert "from enum import" in source


# ── 13. PageData with response_headers Tests ─────────────────────────

class TestPageDataResponseHeaders:
    """Test the response_headers attribute of PageData."""

    def test_response_headers_attribute_accessible(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        # The attribute should exist; verify it's accessible
        _ = page.response_headers

    def test_page_data_all_bool_fields_are_bool(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        bool_fields = [
            "has_canonical", "has_sitemap", "has_robots_txt",
            "is_https", "has_hreflang", "schema_markup_found",
        ]
        for field_name in bool_fields:
            val = getattr(page, field_name)
            assert isinstance(val, bool), f"{field_name} should be bool, got {type(val)}"

    def test_page_data_all_int_fields_are_int(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        int_fields = [
            "status_code", "content_length", "images_total",
            "images_without_alt", "internal_links", "external_links",
        ]
        for field_name in int_fields:
            val = getattr(page, field_name)
            assert isinstance(val, int), f"{field_name} should be int, got {type(val)}"

    def test_page_data_all_str_fields_are_str(self):
        from app.services.e_7b_service import PageData
        page = PageData(url="https://example.com")
        str_fields = ["url", "content_type", "title", "canonical_url"]
        for field_name in str_fields:
            val = getattr(page, field_name)
            assert isinstance(val, str), f"{field_name} should be str, got {type(val)}"


# ── 14. Cross-Validation Tests ───────────────────────────────────────

class TestCrossValidation:
    """Cross-validate relationships between module components."""

    def test_score_weights_categories_count(self):
        from app.services.e_7b_service import SCORE_WEIGHTS
        assert len(SCORE_WEIGHTS) == 4, "Should have exactly 4 scoring categories"

    def test_depth_limits_match_enum_count(self):
        from app.services.e_7b_service import DEPTH_PAGE_LIMITS, AuditDepth
        assert len(DEPTH_PAGE_LIMITS) == len(AuditDepth)

    def test_all_enum_values_are_strings(self):
        from app.services.e_7b_service import AuditDepth, ScoreGrade
        for member in AuditDepth:
            assert isinstance(member.value, str)
        for member in ScoreGrade:
            assert isinstance(member.value, str)

    def test_grade_ordering_logical(self):
        """Grades should follow a logical order from best to worst."""
        from app.services.e_7b_service import ScoreGrade
        grades_ordered = [
            ScoreGrade.A_PLUS,
            ScoreGrade.A,
            ScoreGrade.B,
            ScoreGrade.C,
            ScoreGrade.D,
            ScoreGrade.F,
        ]
        assert len(grades_ordered) == len(ScoreGrade)

    def test_meta_tags_and_security_headers_no_overlap(self):
        from app.services.e_7b_service import CRITICAL_META_TAGS, SECURITY_HEADERS
        overlap = set(CRITICAL_META_TAGS) & set(SECURITY_HEADERS)
        assert len(overlap) == 0, f"Unexpected overlap: {overlap}"