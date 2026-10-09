"""Lightweight OpenTelemetry-compatible tracing and telemetry bridge for guardrail events."""

import contextlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)


class OtelTracerAudit:
    """Lightweight telemetry collector tracking proposal spans, MTTA, and guardrail latency."""

    def __init__(self) -> None:
        self._active_spans: dict[str, dict[str, Any]] = {}
        self._latencies_ms: list[float] = []
        self._approval_durations_s: list[float] = []

    @contextlib.contextmanager
    def trace_span(self, name: str, attributes: dict[str, Any] | None = None):
        """Context manager tracking execution duration and span attributes."""
        attrs = attributes or {}
        start_time = time.perf_counter()
        span_data = {
            "name": name,
            "attributes": attrs,
            "start_time": start_time,
            "status": "IN_PROGRESS",
        }
        span_id = f"{name}_{id(span_data)}"
        self._active_spans[span_id] = span_data
        try:
            yield span_data
            span_data["status"] = "OK"
        except Exception as exc:
            span_data["status"] = "ERROR"
            span_data["error"] = str(exc)
            raise
        finally:
            elapsed_ms = (time.perf_counter() - start_time) * 1000.0
            span_data["elapsed_ms"] = elapsed_ms
            self._latencies_ms.append(elapsed_ms)
            logger.debug("OTel Span '%s' finished in %.2fms (status=%s)", name, elapsed_ms, span_data["status"])

    def record_approval_latency(self, duration_seconds: float) -> None:
        """Record Mean Time to Approve (MTTA) metric for human-in-the-loop decisions."""
        self._approval_durations_s.append(duration_seconds)

    def get_metrics_summary(self) -> dict[str, Any]:
        """Return aggregated telemetry metrics summary."""
        total_spans = len(self._latencies_ms)
        avg_latency = sum(self._latencies_ms) / total_spans if total_spans > 0 else 0.0
        avg_mtta = (
            sum(self._approval_durations_s) / len(self._approval_durations_s)
            if self._approval_durations_s
            else 0.0
        )
        return {
            "total_spans_recorded": total_spans,
            "avg_latency_ms": round(avg_latency, 2),
            "total_approvals_measured": len(self._approval_durations_s),
            "avg_mtta_seconds": round(avg_mtta, 2),
        }

    def clear(self) -> None:
        """Reset telemetry collector metrics."""
        self._active_spans.clear()
        self._latencies_ms.clear()
        self._approval_durations_s.clear()


# Default global telemetry instance
default_otel_tracer = OtelTracerAudit()

# Natural alias
AuditTracerOtel = OtelTracerAudit
