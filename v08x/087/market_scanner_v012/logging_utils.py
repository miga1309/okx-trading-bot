
from __future__ import annotations

import logging
from pathlib import Path


def build_logger(path: Path) -> logging.Logger:
    logger = logging.getLogger(f'market_collector:{path}')
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    path.parent.mkdir(parents=True, exist_ok=True)

    formatter = logging.Formatter('%(asctime)s | %(levelname)s | %(message)s')

    fh = logging.FileHandler(path, encoding='utf-8')
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    sh = logging.StreamHandler()
    sh.setFormatter(formatter)
    logger.addHandler(sh)

    logger.propagate = False
    return logger
