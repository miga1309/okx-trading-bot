from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import QDialog, QHBoxLayout, QLabel, QPushButton, QTextEdit, QVBoxLayout, QWidget


def _fmt_num(value: float, digits: int = 6) -> str:
    try:
        return f"{float(value):,.{digits}f}"
    except Exception:
        return str(value)


class ManualAddUnitDialog(QDialog):
    def __init__(self, preview: dict, parent=None) -> None:
        super().__init__(parent)
        self.preview = dict(preview or {})
        self.setWindowTitle("Ручной добор юнита")
        self.setModal(True)
        self.resize(760, 520)
        self.setStyleSheet(
            "QDialog { background:#07111f; color:#e6ecff; }"
            "QLabel#Title { font-size:18px; font-weight:800; color:#8be9fd; }"
            "QWidget#Card { background:#0b1628; border:1px solid #19324d; border-radius:12px; }"
            "QLabel#CardTitle { font-size:15px; font-weight:800; color:#00ffa3; }"
            "QTextEdit { background:#08111d; color:#e6ecff; border:1px solid #223a55; border-radius:10px; }"
            "QPushButton { min-width:120px; padding:8px 14px; border-radius:10px; font-weight:800; }"
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel(
            f"{self.preview.get('inst_id', '—')} | {str(self.preview.get('side', '')).upper()} | Повышаем?"
        )
        title.setObjectName("Title")
        layout.addWidget(title)

        subtitle = QLabel(
            f"Текущий stop mode: {self.preview.get('active_stop_mode', '—')} | "
            f"Текущий PnL: {_fmt_num(self.preview.get('unrealized_pnl', 0.0), 2)} USDT "
            f"({_fmt_num(self.preview.get('pnl_pct', 0.0), 2)}%)"
        )
        subtitle.setWordWrap(True)
        layout.addWidget(subtitle)

        cards = QHBoxLayout()
        cards.setSpacing(12)
        cards.addWidget(self._build_card(
            "Текущее состояние",
            [
                f"Юнитов: {int(self.preview.get('current_units', 0) or 0)}",
                f"Qty: {_fmt_num(self.preview.get('current_qty', 0.0), 4)}",
                f"Notional: {_fmt_num(self.preview.get('current_notional_usdt', 0.0), 2)} USDT",
                f"Avg Px: {_fmt_num(self.preview.get('avg_px', 0.0), 6)}",
                f"Last Px: {_fmt_num(self.preview.get('last_px', 0.0), 6)}",
                f"Stop Px: {_fmt_num(self.preview.get('stop_price', 0.0), 6)}",
                f"След. добор: {_fmt_num(self.preview.get('next_pyramid_price', 0.0), 6)}",
            ],
        ))
        cards.addWidget(self._build_card(
            "После добавления",
            [
                f"Добавляем юнитов: {int(self.preview.get('extra_units', 1) or 1)}",
                f"Добавка Qty: {_fmt_num(self.preview.get('add_qty', 0.0), 4)}",
                f"Юнитов станет: {int(self.preview.get('projected_units', 0) or 0)}",
                f"Qty станет: {_fmt_num(self.preview.get('projected_qty', 0.0), 4)}",
                f"Notional станет: {_fmt_num(self.preview.get('projected_notional_usdt', 0.0), 2)} USDT",
                f"Оцен. fill: {_fmt_num(self.preview.get('estimated_fill_px', 0.0), 6)}",
                f"Avg Px станет: {_fmt_num(self.preview.get('projected_avg_px', 0.0), 6)}",
            ],
        ))
        layout.addLayout(cards)

        question = QLabel("Подтверждение действия: добавить ещё юнит к позиции сверх стандартного лимита 4?")
        question.setWordWrap(True)
        question.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(question)

        buttons = QHBoxLayout()
        buttons.addStretch(1)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_yes = QPushButton("Да")
        btn_yes.setStyleSheet("QPushButton { background:#157347; color:white; } QPushButton:hover { background:#198754; }")
        btn_yes.clicked.connect(self.accept)
        buttons.addWidget(btn_cancel)
        buttons.addWidget(btn_yes)
        layout.addLayout(buttons)

    def _build_card(self, title: str, lines: list[str]) -> QWidget:
        card = QWidget()
        card.setObjectName("Card")
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        title_lbl = QLabel(title)
        title_lbl.setObjectName("CardTitle")
        body = QTextEdit()
        body.setReadOnly(True)
        body.setMinimumHeight(220)
        body.setPlainText("\n".join(lines))
        layout.addWidget(title_lbl)
        layout.addWidget(body)
        return card
