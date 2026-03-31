# v106

- Added no-op amend guard: repeated amend to the same stop price is skipped.
- Added stop action lock/cooldown per instrument to prevent amend storms.
- Added local pending algo snapshot caching with invalidation after place/amend/cancel.
- Updated release entry point to main_v106.py and cleaned package contents.
