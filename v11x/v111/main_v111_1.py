# === CHANGELOG HEADER ===
# Version: v111_1
# Date: 2026-03-26
# Changes: hotfix for same-request bootstrap-stop entry rejection; removed custom attachAlgoClOrdId from entry attached stops, kept same-request stop attachment, and added one-time retry without custom attached stop id if the exchange rejects algoClOrdId.
# === END CHANGELOG HEADER ===

import os

os.environ.setdefault("OKX_TURTLE_RUNTIME_VERSION", "v111_1")

from bootstrap import build_application


def main() -> None:
    app = build_application(app_version='v111_1', entry_module='main_v111_1')
    app.run()


if __name__ == '__main__':
    main()
