from __future__ import annotations

from typing import Any

NIGHT_TEST_HARD_BLOCK_INSTRUMENTS = {
    'BREV-USDT-SWAP',
    'RAVE-USDT-SWAP',
    'CRO-USDT-SWAP',
    'ADA-USDT-SWAP',
}
HIDDEN_INSTRUMENTS = set(NIGHT_TEST_HARD_BLOCK_INSTRUMENTS)
HIDDEN_PREFIXES = tuple()


def is_hidden_instrument(inst_id: object) -> bool:
    value = str(inst_id or '').upper()
    return value in HIDDEN_INSTRUMENTS or any(value.startswith(prefix) for prefix in HIDDEN_PREFIXES)


def build_scanner_universe(raw_swap_ids: list[str], blacklist: list[str] | None = None) -> dict[str, Any]:
    raw = sorted({str(x).upper() for x in raw_swap_ids if x})
    blacklist_set = {str(x).upper() for x in (blacklist or []) if x}
    hidden = sorted([x for x in raw if is_hidden_instrument(x)])
    trade_ready = sorted([x for x in raw if not is_hidden_instrument(x) and x not in blacklist_set])
    analysis_universe = sorted([x for x in raw if x not in blacklist_set])
    hidden_but_analyzed = sorted([x for x in analysis_universe if is_hidden_instrument(x)])
    excluded_only_by_blacklist = sorted([x for x in raw if x in blacklist_set])
    excluded_from_trade_ready = sorted([x for x in raw if x not in trade_ready])
    return {
        'raw_swap_universe': raw,
        'hidden_in_bot': hidden,
        'hidden_but_analyzed': hidden_but_analyzed,
        'blacklist': sorted(blacklist_set),
        'excluded_only_by_blacklist': excluded_only_by_blacklist,
        'excluded_from_trade_ready': excluded_from_trade_ready,
        'trade_ready_universe': trade_ready,
        'analysis_universe': analysis_universe,
    }
