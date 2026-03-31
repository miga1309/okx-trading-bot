from __future__ import annotations


def normalize_fill(response: dict | None) -> dict:
    payload = dict(response or {})
    data = list(payload.get("data", []) or [])
    first = dict(data[0]) if data else {}
    return {
        "raw": payload,
        "ord_id": str(first.get("ordId") or ""),
        "cl_ord_id": str(first.get("clOrdId") or ""),
        "code": str(payload.get("code") or ""),
        "msg": str(payload.get("msg") or ""),
    }
