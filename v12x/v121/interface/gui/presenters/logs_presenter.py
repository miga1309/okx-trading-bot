from __future__ import annotations


class LogsPresenter:
    def present(self, lines: list[str] | None) -> dict:
        normalized = [str(line) for line in list(lines or [])]
        return {
            'count': len(normalized),
            'tail': normalized[-20:],
        }
