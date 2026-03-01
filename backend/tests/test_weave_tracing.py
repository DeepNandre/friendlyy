"""
Tests for the W&B Weave tracing module.

Covers:
- log_trace and trace store
- @traced decorator contract (timing, error handling, log_fn callback)
- get_trace_ctx() context passing
- get_performance_summary() with caching
- get_improvement_data() edge cases
- get_recent_traces() filtering
- _extract_quote regex
"""

import asyncio
import pytest
from unittest.mock import patch, MagicMock

from services.weave_tracing import (
    log_trace,
    traced,
    get_trace_ctx,
    get_performance_summary,
    get_improvement_data,
    get_recent_traces,
    log_blitz_call,
    log_blitz_session,
    log_router_classification,
    log_chat_response,
    log_business_search,
    log_tts_generation,
    _trace_store,
    _summary_cache,
    MAX_TRACES,
)
from services.blitz import _extract_quote


# ==================== FIXTURES ====================


@pytest.fixture(autouse=True)
def clean_trace_store():
    """Clear trace store before each test."""
    import services.weave_tracing as wt
    wt._trace_store.clear()
    wt._summary_cache = None
    yield
    wt._trace_store.clear()
    wt._summary_cache = None


# ==================== log_trace ====================


class TestLogTrace:
    def test_basic_log(self):
        log_trace("test_op", success=True, duration_seconds=1.5)

        assert len(_trace_store) == 1
        trace = _trace_store[0]
        assert trace["operation"] == "test_op"
        assert trace["success"] is True
        assert trace["duration_seconds"] == 1.5
        assert trace["error"] is None
        assert "timestamp" in trace

    def test_log_with_error(self):
        log_trace("fail_op", success=False, error="something broke", duration_seconds=0.1)

        trace = _trace_store[0]
        assert trace["success"] is False
        assert trace["error"] == "something broke"

    def test_log_with_input_output_metadata(self):
        log_trace(
            "rich_op",
            success=True,
            input_data={"query": "plumber"},
            output_data={"count": 3},
            metadata={"source": "google"},
        )

        trace = _trace_store[0]
        assert trace["input"] == {"query": "plumber"}
        assert trace["output"] == {"count": 3}
        assert trace["metadata"] == {"source": "google"}

    def test_trim_to_max_traces(self):
        for i in range(MAX_TRACES + 50):
            log_trace(f"op_{i}", success=True)

        assert len(_trace_store) == MAX_TRACES
        # Oldest traces should be trimmed
        assert _trace_store[0]["operation"] == f"op_50"

    def test_invalidates_summary_cache(self):
        import services.weave_tracing as wt
        # Prime cache
        get_performance_summary()
        assert wt._summary_cache is not None

        log_trace("new_op", success=True)
        assert wt._summary_cache is None


# ==================== @traced decorator ====================


class TestTracedDecorator:
    @pytest.mark.asyncio
    async def test_basic_tracing(self):
        @traced("test_func")
        async def my_func(x):
            return x * 2

        result = await my_func(5)
        assert result == 10

        # Should have logged a generic trace
        assert len(_trace_store) == 1
        assert _trace_store[0]["operation"] == "test_func"
        assert _trace_store[0]["success"] is True
        assert _trace_store[0]["duration_seconds"] >= 0

    @pytest.mark.asyncio
    async def test_error_propagation(self):
        @traced("error_func")
        async def failing_func():
            raise ValueError("test error")

        with pytest.raises(ValueError, match="test error"):
            await failing_func()

        assert len(_trace_store) == 1
        assert _trace_store[0]["success"] is False
        assert _trace_store[0]["error"] == "test error"

    @pytest.mark.asyncio
    async def test_log_fn_callback(self):
        callback_calls = []

        def my_log_fn(*, result, duration, error, args, kwargs, ctx):
            callback_calls.append({
                "result": result,
                "duration": duration,
                "error": error,
                "args": args,
                "kwargs": kwargs,
                "ctx": ctx,
            })

        @traced("custom_logged", log_fn=my_log_fn)
        async def my_func(a, b=10):
            return a + b

        result = await my_func(5, b=20)
        assert result == 25

        assert len(callback_calls) == 1
        call = callback_calls[0]
        assert call["result"] == 25
        assert call["duration"] > 0
        assert call["error"] is None
        assert call["args"] == (5,)
        assert call["kwargs"] == {"b": 20}
        assert isinstance(call["ctx"], dict)

        # With log_fn, no generic trace should be logged
        assert len(_trace_store) == 0

    @pytest.mark.asyncio
    async def test_log_fn_receives_error(self):
        callback_calls = []

        def my_log_fn(*, result, duration, error, args, kwargs, ctx):
            callback_calls.append({"error": error, "result": result})

        @traced("err_logged", log_fn=my_log_fn)
        async def failing():
            raise RuntimeError("boom")

        with pytest.raises(RuntimeError):
            await failing()

        assert len(callback_calls) == 1
        assert callback_calls[0]["error"] == "boom"
        assert callback_calls[0]["result"] is None

    @pytest.mark.asyncio
    async def test_default_name_from_function(self):
        @traced()
        async def auto_named_func():
            return 42

        await auto_named_func()
        assert _trace_store[0]["operation"] == "auto_named_func"

    @pytest.mark.asyncio
    async def test_log_fn_crash_does_not_break(self):
        def crashing_log_fn(*, result, duration, error, args, kwargs, ctx):
            raise Exception("log_fn exploded")

        @traced("safe_func", log_fn=crashing_log_fn)
        async def my_func():
            return "ok"

        # Should not raise despite log_fn crashing
        result = await my_func()
        assert result == "ok"


# ==================== get_trace_ctx ====================


class TestTraceCtx:
    @pytest.mark.asyncio
    async def test_ctx_available_inside_traced(self):
        captured_ctx = {}

        def my_log_fn(*, result, duration, error, args, kwargs, ctx):
            captured_ctx.update(ctx)

        @traced("ctx_test", log_fn=my_log_fn)
        async def my_func():
            ctx = get_trace_ctx()
            ctx["custom_key"] = "custom_value"
            return "done"

        await my_func()
        assert captured_ctx["custom_key"] == "custom_value"

    @pytest.mark.asyncio
    async def test_ctx_isolated_between_calls(self):
        results = []

        def my_log_fn(*, result, duration, error, args, kwargs, ctx):
            results.append(dict(ctx))

        @traced("isolation_test", log_fn=my_log_fn)
        async def my_func(val):
            ctx = get_trace_ctx()
            ctx["val"] = val
            return val

        await my_func("first")
        await my_func("second")

        assert results[0]["val"] == "first"
        assert results[1]["val"] == "second"


# ==================== get_performance_summary ====================


class TestPerformanceSummary:
    def test_empty_store(self):
        summary = get_performance_summary()
        assert summary["total_traces"] == 0
        assert summary["message"] == "No traces yet"

    def test_basic_summary(self):
        log_trace("op_a", success=True, duration_seconds=1.0)
        log_trace("op_a", success=True, duration_seconds=2.0)
        log_trace("op_a", success=False, duration_seconds=0.5, error="fail")
        log_trace("op_b", success=True, duration_seconds=0.3)

        summary = get_performance_summary()
        assert summary["total_traces"] == 4

        op_a = summary["operations"]["op_a"]
        assert op_a["total"] == 3
        assert op_a["successes"] == 2
        assert op_a["failures"] == 1
        assert op_a["success_rate"] == round(2 / 3, 3)
        assert op_a["avg_duration"] == round((1.0 + 2.0 + 0.5) / 3, 3)

        op_b = summary["operations"]["op_b"]
        assert op_b["total"] == 1
        assert op_b["successes"] == 1

    def test_caching(self):
        import services.weave_tracing as wt
        log_trace("cached_op", success=True)

        s1 = get_performance_summary()
        assert wt._summary_cache is not None
        s2 = get_performance_summary()
        assert s1 is s2  # Same object, from cache

    def test_blitz_insights(self):
        log_blitz_call(
            business_name="Test Co",
            business_phone="+44123",
            call_success=True,
            call_duration=5.0,
            business_responded=True,
            quote_received=95.0,
            result_text="Available, £95",
            session_id="s1",
        )
        log_blitz_call(
            business_name="Other Co",
            business_phone="+44456",
            call_success=False,
            call_duration=15.0,
            business_responded=False,
            session_id="s1",
        )

        summary = get_performance_summary()
        insights = summary["blitz_insights"]
        assert insights["total_calls"] == 2
        assert insights["businesses_responded"] == 1
        assert insights["quotes_received"] == 1
        assert insights["response_rate"] == 0.5


# ==================== get_improvement_data ====================


class TestImprovementData:
    def test_insufficient_data(self):
        result = get_improvement_data()
        assert "message" in result

    def test_single_session_insufficient(self):
        log_blitz_session(
            session_id="s1", total_calls=3, successful_calls=2,
            total_duration=10.0, service_type="plumber",
        )
        result = get_improvement_data()
        assert "message" in result

    def test_two_sessions_comparison(self):
        log_blitz_session(
            session_id="s1", total_calls=3, successful_calls=1,
            total_duration=15.0, service_type="plumber",
        )
        log_blitz_session(
            session_id="s2", total_calls=3, successful_calls=2,
            total_duration=10.0, service_type="plumber",
        )

        result = get_improvement_data()
        assert "early_sessions" in result
        assert "recent_sessions" in result
        assert "improvement" in result
        assert result["total_sessions_analyzed"] == 2


# ==================== get_recent_traces ====================


class TestRecentTraces:
    def test_returns_last_n(self):
        for i in range(30):
            log_trace(f"op_{i}", success=True)

        recent = get_recent_traces(limit=5)
        assert len(recent) == 5
        assert recent[-1]["operation"] == "op_29"

    def test_filter_by_operation(self):
        log_trace("alpha", success=True)
        log_trace("beta", success=True)
        log_trace("alpha", success=False)

        alpha_traces = get_recent_traces(operation="alpha")
        assert len(alpha_traces) == 2
        assert all(t["operation"] == "alpha" for t in alpha_traces)

    def test_empty_store(self):
        assert get_recent_traces() == []


# ==================== Domain log helpers ====================


class TestDomainLogHelpers:
    def test_log_router_classification(self):
        log_router_classification(
            user_message="find me a plumber",
            classified_agent="blitz",
            confidence=0.95,
            duration=0.2,
            params={"service": "plumber"},
        )
        assert len(_trace_store) == 1
        assert _trace_store[0]["operation"] == "classify_intent"

    def test_log_chat_response(self):
        log_chat_response(
            user_message="hello",
            response_text="Hi there!",
            duration=0.5,
        )
        assert _trace_store[0]["operation"] == "chat_response"

    def test_log_business_search(self):
        log_business_search(
            query="plumber",
            location="London",
            results_count=3,
            duration=1.2,
            used_fallback=True,
        )
        trace = _trace_store[0]
        assert trace["operation"] == "business_search"
        assert trace["output"]["used_fallback"] is True

    def test_log_tts_generation(self):
        log_tts_generation(
            text_length=150,
            duration=0.8,
            cache_hit=True,
            success=True,
        )
        trace = _trace_store[0]
        assert trace["operation"] == "tts_generation"
        assert trace["output"]["cache_hit"] is True


# ==================== _extract_quote ====================


class TestExtractQuote:
    def test_pound_sign(self):
        assert _extract_quote("Available, £95 call-out fee") == 95.0

    def test_dollar_sign(self):
        assert _extract_quote("Price is $120.50") == 120.50

    def test_pound_with_space(self):
        assert _extract_quote("Total: £ 85") == 85.0

    def test_no_currency_symbol_returns_none(self):
        assert _extract_quote("call 3 businesses") is None

    def test_plain_number_returns_none(self):
        assert _extract_quote("Found 5 options for you") is None

    def test_none_input(self):
        assert _extract_quote(None) is None

    def test_empty_string(self):
        assert _extract_quote("") is None

    def test_no_match(self):
        assert _extract_quote("No price given") is None

    def test_decimal_precision(self):
        assert _extract_quote("£99.99 per hour") == 99.99

    def test_first_match_wins(self):
        assert _extract_quote("£50 or £100") == 50.0
