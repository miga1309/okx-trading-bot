from pathlib import Path
import re

SOURCE_FILE = "main_v021_balanced.py"
TARGET_FILE = "main_v021_balanced_ui.py"


def must_replace(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        raise RuntimeError(f"Не найден блок для замены: {label}")
    return text.replace(old, new, 1)


def patch() -> None:
    src = Path(SOURCE_FILE)
    if not src.exists():
        raise FileNotFoundError(f"Не найден исходный файл: {SOURCE_FILE}")

    text = src.read_text(encoding="utf-8")

    text = re.sub(
        r'APP_VERSION\s*=\s*"[^"]+"',
        'APP_VERSION = "v021b-ui"',
        text,
        count=1,
    )

    # 1) Чуть компактнее базовый layout окна
    text = must_replace(
        text,
        '        layout = QVBoxLayout(root)\n',
        '        layout = QVBoxLayout(root)\n'
        '        layout.setContentsMargins(8, 8, 8, 8)\n'
        '        layout.setSpacing(6)\n',
        'main root layout compact',
    )

    # 2) Сжать StartWindow по высоте
    text = must_replace(
        text,
        '        self.start_window = StartWindow()\n'
        '        self.start_window.start_requested.connect(self.set_pending_config)\n'
        '        layout.addWidget(self.start_window)\n',
        '        self.start_window = StartWindow()\n'
        '        self.start_window.start_requested.connect(self.set_pending_config)\n'
        '        self.start_window.setMaximumHeight(165)\n'
        '        layout.addWidget(self.start_window, stretch=0)\n',
        'start_window compact height',
    )

    # 3) Уменьшить вертикальные зазоры верхних панелей
    text = must_replace(
        text,
        '        top_panels = QHBoxLayout()\n',
        '        top_panels = QHBoxLayout()\n'
        '        top_panels.setSpacing(6)\n',
        'top_panels spacing',
    )

    # 4) Уплотнить карточки статистики: 3 колонки вместо 2
    text = must_replace(
        text,
        '        for idx, lbl in enumerate(labels):\n'
        '            lbl.setProperty("card", "true")\n'
        '            metrics_layout.addWidget(lbl, idx // 2, idx % 2)\n',
        '        metrics_layout.setContentsMargins(6, 6, 6, 6)\n'
        '        metrics_layout.setHorizontalSpacing(6)\n'
        '        metrics_layout.setVerticalSpacing(4)\n'
        '        for idx, lbl in enumerate(labels):\n'
        '            lbl.setProperty("card", "true")\n'
        '            lbl.setMinimumHeight(24)\n'
        '            lbl.setMaximumHeight(30)\n'
        '            metrics_layout.addWidget(lbl, idx // 3, idx % 3)\n',
        'metrics 3 columns',
    )

    # 5) Баланс-график сделать компактнее
    text = must_replace(
        text,
        '        metrics_layout.addLayout(balance_chart_header, 8, 0, 1, 2)\n'
        '        self.balance_chart = BalanceChartWidget()\n'
        '        metrics_layout.addWidget(self.balance_chart, 9, 0, 1, 2)\n'
        '        metrics_layout.setRowStretch(9, 1)\n'
        '        top_panels.addWidget(metrics_box, 4)\n',
        '        metrics_layout.addLayout(balance_chart_header, 5, 0, 1, 3)\n'
        '        self.balance_chart = BalanceChartWidget()\n'
        '        self.balance_chart.setMinimumHeight(110)\n'
        '        self.balance_chart.setMaximumHeight(150)\n'
        '        metrics_layout.addWidget(self.balance_chart, 6, 0, 1, 3)\n'
        '        top_panels.addWidget(metrics_box, 3)\n',
        'compact chart block',
    )

    # 6) Аналитический блок тоже уплотнить
    text = must_replace(
        text,
        '        for idx, lbl in enumerate(analytics_labels):\n'
        '            lbl.setProperty("card", "true")\n'
        '            analytics_layout.addWidget(lbl, idx // 2, idx % 2)\n'
        '        self.lbl_position_map.setProperty("card", "true")\n'
        '        analytics_layout.addWidget(self.lbl_position_map, 4, 0, 1, 2)\n'
        '        top_panels.addWidget(analytics_box, 2)\n'
        '        layout.addLayout(top_panels)\n',
        '        analytics_layout.setContentsMargins(6, 6, 6, 6)\n'
        '        analytics_layout.setHorizontalSpacing(6)\n'
        '        analytics_layout.setVerticalSpacing(4)\n'
        '        for idx, lbl in enumerate(analytics_labels):\n'
        '            lbl.setProperty("card", "true")\n'
        '            lbl.setMinimumHeight(24)\n'
        '            lbl.setMaximumHeight(30)\n'
        '            analytics_layout.addWidget(lbl, idx // 2, idx % 2)\n'
        '        self.lbl_position_map.setProperty("card", "true")\n'
        '        self.lbl_position_map.setMaximumHeight(52)\n'
        '        analytics_layout.addWidget(self.lbl_position_map, 4, 0, 1, 2)\n'
        '        top_panels.addWidget(analytics_box, 1)\n'
        '        layout.addLayout(top_panels, stretch=0)\n',
        'compact analytics block',
    )

    # 7) Фильтры меньше по высоте
    text = must_replace(
        text,
        '        layout.addWidget(filter_box)\n',
        '        filter_box.setMaximumHeight(64)\n'
        '        layout.addWidget(filter_box, stretch=0)\n',
        'compact filter box',
    )

    # 8) Кнопки тоже компактнее
    text = must_replace(
        text,
        '        button_row = QHBoxLayout()\n',
        '        button_row = QHBoxLayout()\n'
        '        button_row.setSpacing(6)\n',
        'button row spacing',
    )

    text = must_replace(
        text,
        '        layout.addLayout(button_row)\n',
        '        layout.addLayout(button_row, stretch=0)\n',
        'button row no stretch',
    )

    # 9) Главное: вкладкам больше места
    text = must_replace(
        text,
        '        layout.addWidget(self.tabs, stretch=6)\n',
        '        self.tabs.setDocumentMode(True)\n'
        '        layout.addWidget(self.tabs, stretch=14)\n',
        'tabs bigger area',
    )

    # 10) Немного уменьшить paddings у кнопок и input в stylesheet
    text = text.replace(
        'padding: 8px 12px;',
        'padding: 6px 10px;'
    )
    text = text.replace(
        'padding: 4px 8px;',
        'padding: 3px 7px;'
    )
    text = text.replace(
        'min-height: 28px;',
        'min-height: 24px;'
    )

    Path(TARGET_FILE).write_text(text, encoding="utf-8")
    print(f"Готово: {TARGET_FILE}")


if __name__ == "__main__":
    patch()