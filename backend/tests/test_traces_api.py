"""
Tests for the traces dashboard API endpoints.

Covers:
- GET /api/traces (dashboard)
- GET /api/traces/performance
- GET /api/traces/improvement
- GET /api/traces/recent (with filtering)
- GET /api/traces/blitz
"""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from main import app
from services.weave_tracing import (
    log_trace,
    log_blitz_call,
    log_blitz_session,
    _trace_store,
)


@pytest.fixture(autouse=True)
def clean_trace_store():
    """Clear trace store before each test."""
    import services.weave_tracing as wt
    wt._trace_store.clear()
    wt._summary_cache = None
    yield
    wt._trace_store.clear()
    wt._summary_cache = None


@pytest.fixture
def client():
    return TestClient(app)


class TestTracesDashboard:
    def test_empty_dashboard(self, client):
        resp = client.get("/api/traces")
        assert resp.status_code == 200
        data = resp.json()
        assert "performance" in data
        assert "improvement" in data
        assert "recent_traces" in data
        assert data["performance"]["total_traces"] == 0

    def test_dashboard_with_data(self, client):
        log_trace("test_op", success=True, duration_seconds=1.0)
        log_trace("test_op", success=False, error="err", duration_seconds=0.5)

        resp = client.get("/api/traces")
        data = resp.json()
        assert data["performance"]["total_traces"] == 2
        assert len(data["recent_traces"]) == 2


class TestPerformanceEndpoint:
    def test_empty(self, client):
        resp = client.get("/api/traces/performance")
        assert resp.status_code == 200
        assert resp.json()["total_traces"] == 0

    def test_with_operations(self, client):
        log_trace("alpha", success=True, duration_seconds=1.0)
        log_trace("beta", success=True, duration_seconds=2.0)

        resp = client.get("/api/traces/performance")
        data = resp.json()
        assert data["total_traces"] == 2
        assert "alpha" in data["operations"]
        assert "beta" in data["operations"]


class TestImprovementEndpoint:
    def test_insufficient_data(self, client):
        resp = client.get("/api/traces/improvement")
        assert resp.status_code == 200
        assert "message" in resp.json()

    def test_with_sessions(self, client):
        for i in range(4):
            log_blitz_session(
                session_id=f"s{i}",
                total_calls=3,
                successful_calls=i,
                total_duration=10.0 - i,
                service_type="plumber",
            )

        resp = client.get("/api/traces/improvement")
        data = resp.json()
        assert "early_sessions" in data
        assert "recent_sessions" in data
        assert data["total_sessions_analyzed"] == 4


class TestRecentEndpoint:
    def test_default_limit(self, client):
        for i in range(25):
            log_trace(f"op_{i}", success=True)

        resp = client.get("/api/traces/recent")
        assert resp.status_code == 200
        assert len(resp.json()) == 20  # Default limit

    def test_custom_limit(self, client):
        for i in range(10):
            log_trace(f"op_{i}", success=True)

        resp = client.get("/api/traces/recent?limit=5")
        assert len(resp.json()) == 5

    def test_filter_by_operation(self, client):
        log_trace("alpha", success=True)
        log_trace("beta", success=True)
        log_trace("alpha", success=False)

        resp = client.get("/api/traces/recent?operation=alpha")
        data = resp.json()
        assert len(data) == 2
        assert all(t["operation"] == "alpha" for t in data)

    def test_invalid_limit_rejected(self, client):
        resp = client.get("/api/traces/recent?limit=0")
        assert resp.status_code == 422

        resp = client.get("/api/traces/recent?limit=101")
        assert resp.status_code == 422


class TestBlitzEndpoint:
    def test_empty(self, client):
        resp = client.get("/api/traces/blitz")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_calls"] == 0
        assert data["total_sessions"] == 0

    def test_with_blitz_data(self, client):
        log_blitz_call(
            business_name="Test Co",
            business_phone="+44123",
            call_success=True,
            call_duration=5.0,
            business_responded=True,
            quote_received=95.0,
            result_text="£95",
            session_id="s1",
        )
        log_blitz_session(
            session_id="s1",
            total_calls=1,
            successful_calls=1,
            total_duration=8.0,
            service_type="plumber",
        )

        resp = client.get("/api/traces/blitz")
        data = resp.json()
        assert data["total_calls"] == 1
        assert data["total_sessions"] == 1
        assert data["blitz_insights"]["total_calls"] == 1
        assert data["blitz_insights"]["quotes_received"] == 1
