# Changelog

## v086 — 2026-03-17

### Added
- breakout_id anti-loop guard and same-price reentry block
- mandatory exchange stop confirmation with emergency close if stop is not confirmed
- hard late-entry filters for oversized breakout candles and momentum-chase entries
- early invalidation exit in the first bars after entry
- loss-streak quarantine by symbol/side
- changelog moved out of the main program file

### Notes
- main launch file: `main_v086.py`
- this release keeps existing Turtle logic and pyramiding logic, but hardens entry and risk control
