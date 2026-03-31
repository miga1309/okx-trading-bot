# v099 - 2026-03-23

- Scanner gate hardened: stale status now blocks new entries until a forced refresh succeeds.
- DEAD/RIPPING scanner results now place instruments on temporary cooldown for new entries.
- Scanner defaults tuned for faster refresh and deep checks enabled by default.
- OKX gateway now resolves posSide from account config when available.
- Market and algo stop requests now include client IDs for better traceability.
- Signal audit/export now records scanner freshness, forced refresh, cooldown, and connectivity context.
