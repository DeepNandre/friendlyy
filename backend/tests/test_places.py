"""
Tests for Google Places service.
"""

import pytest
import respx
from httpx import Response

from services.places import (
    search_businesses,
    _get_fallback_businesses,
    FALLBACK_BUSINESSES,
)


class TestPlacesSearch:
    """Test Google Places API integration."""

    @pytest.mark.asyncio
    async def test_search_returns_businesses(self, mock_settings, mock_places_api):
        """Test successful search returns businesses with phones."""
        # Mock text search
        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
        ).mock(
            return_value=Response(
                200,
                json={
                    "results": [
                        {"place_id": "place1", "name": "Test Plumber 1"},
                        {"place_id": "place2", "name": "Test Plumber 2"},
                    ]
                },
            )
        )

        # Mock details for each place
        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/details/json"
        ).mock(
            return_value=Response(
                200,
                json={
                    "result": {
                        "name": "Test Plumber",
                        "international_phone_number": "+441234567890",
                        "formatted_address": "123 Test St",
                        "rating": 4.5,
                    }
                },
            )
        )

        businesses = await search_businesses(
            query="plumber",
            location="London",
            max_results=3,
        )

        assert len(businesses) >= 1
        assert businesses[0].phone is not None

    @pytest.mark.asyncio
    async def test_fallback_on_no_api_key(self, monkeypatch):
        """Test fallback to hardcoded businesses when no API key."""
        monkeypatch.setenv("GOOGLE_PLACES_API_KEY", "")
        from core.config import get_settings
        get_settings.cache_clear()

        businesses = await search_businesses(
            query="plumber",
            location="London",
            max_results=3,
        )

        assert len(businesses) >= 1
        # Should be from fallback list
        assert any("Pimlico" in b.name or "fallback" in b.id for b in businesses)

    @pytest.mark.asyncio
    async def test_fallback_on_api_error(self, mock_settings, mock_places_api):
        """Test fallback on API error."""
        mock_places_api.get(
            "https://maps.googleapis.com/maps/api/place/textsearch/json"
        ).mock(return_value=Response(500, json={"error": "Server error"}))

        businesses = await search_businesses(
            query="plumber",
            location="London",
            max_results=3,
        )

        assert len(businesses) >= 1


class TestFallbackBusinesses:
    """Test fallback business selection."""

    def test_fallback_exact_match(self):
        """Test fallback returns correct businesses for exact service match."""
        businesses = _get_fallback_businesses("plumber", 3)

        assert len(businesses) == 3
        assert all("plumber" in b.id.lower() or "Plumber" in b.name for b in businesses)

    def test_fallback_partial_match(self):
        """Test fallback handles partial matches."""
        businesses = _get_fallback_businesses("emergency plumber", 3)

        # Should match "plumber"
        assert len(businesses) >= 1

    def test_fallback_default(self):
        """Test fallback returns default for unknown service."""
        businesses = _get_fallback_businesses("random_service_xyz", 3)

        # Should return default fallback
        assert len(businesses) >= 1
        assert all(b.phone is not None for b in businesses)

    def test_fallback_respects_max_results(self):
        """Test fallback respects max_results parameter."""
        businesses = _get_fallback_businesses("plumber", 1)

        assert len(businesses) == 1
