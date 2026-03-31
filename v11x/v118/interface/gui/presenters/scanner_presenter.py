from __future__ import annotations


class ScannerPresenter:
    def present(self, snapshot: dict | None) -> dict:
        payload = dict(snapshot or {})
        scanner = dict(payload.get('scanner', {}) or {})
        summary = dict(scanner.get('summary', {}) or {})
        summary.setdefault('total', 0)
        summary.setdefault('ready', 0)
        summary.setdefault('admitted', 0)
        summary.setdefault('blocked', 0)
        summary.setdefault('pending', 0)
        summary.setdefault('failed', 0)
        return {
            'summary': summary,
            'status_age_sec': float(scanner.get('status_age_sec', 0.0) or 0.0),
            'last_cycle_id': int(payload.get('engine', {}).get('scan_cycle_seq', 0) or 0),
        }
