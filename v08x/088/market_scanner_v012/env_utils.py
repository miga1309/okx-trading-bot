from __future__ import annotations

from pathlib import Path


def load_env_file(path: str | Path = '.env') -> dict[str, str]:
    out: dict[str, str] = {}
    p = Path(path)
    if not p.exists():
        return out
    for line in p.read_text(encoding='utf-8', errors='ignore').splitlines():
        line = line.strip()
        if not line or line.startswith('#') or '=' not in line:
            continue
        key, value = line.split('=', 1)
        out[key.strip()] = value.strip().strip('"').strip("'")
    aliases = {
        'OKX_API_KEY': ['API_KEY', 'OKX_KEY'],
        'OKX_SECRET_KEY': ['SECRET_KEY', 'OKX_SECRET'],
        'OKX_PASSPHRASE': ['PASSPHRASE', 'OKX_PASS'],
        'OKX_FLAG': ['FLAG', 'DEMO_FLAG'],
    }
    for canonical, names in aliases.items():
        if out.get(canonical):
            continue
        for alias in names:
            if out.get(alias):
                out[canonical] = out[alias]
                break
    return out
