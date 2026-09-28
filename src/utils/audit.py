"""CMN-C1-735 — S-4 audit trace helper (platform logger + stderr fallback).

Nodes import the canonical ``shared.utils.audit_logger.emit_trace_event`` first
and fall back to this wrapper in test environments where the platform package is
unavailable (same idiom as the server.py framework shim). Payloads carry only
aggregate counts / codes — never PII, dataset contents, or credentials (S-4/S-5).
"""

from __future__ import annotations

import json
import sys
from typing import Any

try:
    from shared.utils.audit_logger import emit_trace_event as _platform_emit
except Exception:  # pragma: no cover - platform package absent in a local stub env
    _platform_emit = None

_TEMPLATE_ID = "CMN-C1-735"


def emit_trace_event(event_type: str, payload: dict[str, Any], state: dict[str, Any] | None = None) -> None:
    """Emit a domain audit event (best-effort, never raises)."""
    if _platform_emit is not None:
        try:
            _platform_emit(event_type, payload, state)
            return
        except Exception:  # pragma: no cover - defensive
            pass
    record = {
        "template_id": _TEMPLATE_ID,
        "event_type": event_type,
        "payload": payload,
        "session_id": (state or {}).get("session_id"),
    }
    try:
        print(json.dumps(record, ensure_ascii=False), file=sys.stderr)
    except Exception:  # pragma: no cover - defensive
        pass
