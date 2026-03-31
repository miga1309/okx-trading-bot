# v089
Date: 2026-03-19

Changes:
- replaced old Market Scanner classes/risk buckets with new binary scanner: ALLOW vs DEAD / SAW / RIPPING
- progressive scanner admission preserved: allowed pairs become trade-ready immediately during scan
- added bottom Market Scanner tab with Dead / Saw / Ripping review tables
- added manual validation states for scanner results: Не проверено / Подтверждено / Не подтверждено
- added scanner popup review dialog with live chart snapshot and metric summary
- persisted scanner validation/history logs and appended them to exported analysis archives
- updated GUI scanner counters to Total / Scanned / Allowed / Blocked / Dead / Saw / Ripping / Pending / Status
