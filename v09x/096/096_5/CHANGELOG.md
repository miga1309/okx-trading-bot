v096_5
- Fixed exchange stop recovery/verification flow and removed amend/cancel calls without a valid stop id.
- Treats stale/missing stop cancellation as non-fatal and attempts fresh stop placement.
- Softened initial-stop verify failure: retries recovery instead of immediate force-close.
- Fixed avg_px refresh after pyramid when live reconcile returns total position avgPx.
- Improved runtime export fallbacks for position age/sync/runtime fields.
