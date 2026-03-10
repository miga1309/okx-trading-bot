from PyQt6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PyQt6.QtGui import QColor

from app_core import ClosedTrade, PositionState, format_time_string, gradient_pnl_color

class PositionTableModel(QAbstractTableModel):
    HEADERS = [
        "Инструмент",
        "Сторона",
        "Qty",
        "Средняя цена",
        "Последняя цена",
        "PnL",
        "PnL %",
        "ATR",
        "ATR %",
        "Стоп",
        "До стопа %",
        "След. добор",
        "До добора %",
        "Юнитов",
        "Вход",
        "Система",
    ]

    def __init__(self):
        super().__init__()
        self.rows: list[PositionState] = []

    def update_rows(self, rows: list[PositionState]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        col = index.column()

        pnl_pct = 0.0
        if row.avg_px > 0:
            if row.side == "long":
                pnl_pct = (row.last_px - row.avg_px) / row.avg_px * 100.0
            else:
                pnl_pct = (row.avg_px - row.last_px) / row.avg_px * 100.0

        atr_pct = (row.atr / row.last_px * 100.0) if row.last_px > 0 else 0.0
        stop_dist_pct = abs((row.last_px - row.stop_price) / row.last_px * 100.0) if row.last_px > 0 else 0.0
        pyramid_dist_pct = abs((row.next_pyramid_price - row.last_px) / row.last_px * 100.0) if row.last_px > 0 and row.next_pyramid_price > 0 else 0.0

        values = [
            row.inst_id,
            row.side,
            f"{row.qty:.8f}",
            f"{row.avg_px:.6f}",
            f"{row.last_px:.6f}",
            f"{row.unrealized_pnl:.4f}",
            f"{pnl_pct:.2f}",
            f"{row.atr:.6f}",
            f"{atr_pct:.2f}",
            f"{row.stop_price:.6f}",
            f"{stop_dist_pct:.2f}",
            f"{row.next_pyramid_price:.6f}" if row.next_pyramid_price > 0 else "-",
            f"{pyramid_dist_pct:.2f}" if row.next_pyramid_price > 0 else "-",
            str(row.units),
            format_time_string(row.entry_time),
            row.system_name or "-",
        ]

        if role == Qt.ItemDataRole.DisplayRole:
            return values[col]

        if role == Qt.ItemDataRole.BackgroundRole:
            return gradient_pnl_color(pnl_pct)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        return None


class ClosedTradesTableModel(QAbstractTableModel):
    HEADERS = [
        "Время",
        "Инструмент",
        "Сторона",
        "Qty",
        "Вход",
        "Выход",
        "PnL",
        "PnL %",
        "Юнитов",
        "Система",
        "Причина",
        "Длительность",
    ]

    def __init__(self):
        super().__init__()
        self.rows: list[ClosedTrade] = []

    def update_rows(self, rows: list[ClosedTrade]) -> None:
        self.beginResetModel()
        self.rows = list(rows)
        self.endResetModel()

    def rowCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.rows)

    def columnCount(self, parent=QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.HEADERS)

    def headerData(self, section, orientation, role=Qt.ItemDataRole.DisplayRole):
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation == Qt.Orientation.Horizontal:
            return self.HEADERS[section]
        return section + 1

    def data(self, index, role=Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        row = self.rows[index.row()]
        col = index.column()

        values = [
            format_time_string(row.time),
            row.inst_id,
            row.side,
            f"{row.qty:.8f}",
            f"{row.entry_px:.6f}",
            f"{row.exit_px:.6f}",
            f"{row.pnl:.4f}",
            f"{row.pnl_pct:.2f}",
            str(row.units),
            row.system_name or "-",
            row.reason,
            format_duration(row.duration_sec),
        ]

        if role == Qt.ItemDataRole.DisplayRole:
            return values[col]

        if role == Qt.ItemDataRole.BackgroundRole:
            return gradient_pnl_color(row.pnl_pct)

        if role == Qt.ItemDataRole.TextAlignmentRole:
            return Qt.AlignmentFlag.AlignCenter

        return None