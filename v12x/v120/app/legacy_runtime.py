# Minimal compatibility facade after one-iteration legacy tail cleanup
from app.runtime_entry import install_exception_logging, main

__all__ = ['install_exception_logging', 'main']
