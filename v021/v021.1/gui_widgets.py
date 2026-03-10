from datetime import datetime
from typing import List, Tuple

from PyQt6.QtCore import QObject, QPoint, Qt, QThread, pyqtSignal
from PyQt6.QtGui import QColor, QPainter, QPen, QPolygon
from PyQt6.QtWidgets import QWidget

from app_core import format_duration

class BalanceChartWidget(QWidget):
    STEP_SECONDS = {
        "1m": 60,
        "5m": 300,
        "15m": 900,
        "30m": 1800,
        "1H": 3600,
        "1D": 86400,
    }

    def __init__(self):
        super().__init__()
        self.points: List[Tuple[str, float]] = []
        self.setMinimumHeight(180)
        self.hover_index: int | None = None
        self.hover_pos = QPoint()

    def set_points(self, points: List[Tuple[str, float]]) -> None:
        self.points = list(points)
        self.update()

    def _is_dark_theme(self) -> bool:
        pal = self.palette()
        return pal.window().color().lightness() < 128

    def _colors(self):
        if self._is_dark_theme():
            return {
                "bg": QColor(30, 30, 30),
                "grid": QColor(65, 65, 65),
                "line": QColor(120, 180, 255),
                "fill": QColor(120, 180, 255, 50),
                "text": QColor(225, 225, 225),
                "accent": QColor(160, 255, 160),
                "tooltip_bg": QColor(35, 35, 35, 230),
                "tooltip_border": QColor(85, 85, 85),
            }
        return {
            "bg": QColor(255, 255, 255),
            "grid": QColor(220, 225, 232),
            "line": QColor(60, 120, 220),
            "fill": QColor(60, 120, 220, 45),
            "text": QColor(32, 33, 36),
            "accent": QColor(40, 160, 80),
            "tooltip_bg": QColor(255, 255, 255, 240),
            "tooltip_border": QColor(180, 188, 198),
        }

    def mouseMoveEvent(self, event):
        if not self.points:
            self.hover_index = None
            self.update()
            return
        self.hover_pos = event.position().toPoint()
        rect = self.rect().adjusted(50, 10, -10, -30)
        if rect.width() <= 0 or rect.height() <= 0:
            self.hover_index = None
            self.update()
            return
        n = len(self.points)
        if n == 1:
            self.hover_index = 0
        else:
            x = min(max(self.hover_pos.x(), rect.left()), rect.right())
            rel = (x - rect.left()) / max(1, rect.width())
            idx = round(rel * (n - 1))
            self.hover_index = max(0, min(n - 1, idx))
        self.update()

    def leaveEvent(self, event):
        self.hover_index = None
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        c = self._colors()
        painter.fillRect(self.rect(), c["bg"])

        rect = self.rect().adjusted(50, 10, -10, -30)
        if rect.width() <= 0 or rect.height() <= 0:
            return

        if not self.points:
            painter.setPen(c["text"])
            painter.drawText(rect, Qt.AlignmentFlag.AlignCenter, "Нет данных для графика PnL")
            return

        vals = [v for _, v in self.points]
        mn = min(vals)
        mx = max(vals)
        if abs(mx - mn) < 1e-12:
            mx += 1.0
            mn -= 1.0

        steps = 5
        painter.setPen(QPen(c["grid"], 1))
        for i in range(steps + 1):
            y = rect.top() + i * rect.height() / steps
            painter.drawLine(rect.left(), int(y), rect.right(), int(y))
            value = mx - (mx - mn) * i / steps
            painter.setPen(c["text"])
            painter.drawText(5, int(y) + 4, f"{value:.2f}")
            painter.setPen(QPen(c["grid"], 1))

        n = len(self.points)
        pts = []
        for i, (_, v) in enumerate(self.points):
            x = rect.left() if n == 1 else rect.left() + i * rect.width() / (n - 1)
            y = rect.bottom() - (v - mn) / (mx - mn) * rect.height()
            pts.append((int(x), int(y)))

        poly = QPolygon([QPoint(x, y) for x, y in pts] + [QPoint(rect.right(), rect.bottom()), QPoint(rect.left(), rect.bottom())])
        painter.setBrush(c["fill"])
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(poly)

        painter.setPen(QPen(c["line"], 2))
        for i in range(1, len(pts)):
            painter.drawLine(pts[i - 1][0], pts[i - 1][1], pts[i][0], pts[i][1])

        painter.setBrush(c["line"])
        for x, y in pts:
            painter.drawEllipse(QPoint(x, y), 3, 3)

        if self.hover_index is not None and 0 <= self.hover_index < len(pts):
            x, y = pts[self.hover_index]
            painter.setPen(QPen(c["accent"], 1, Qt.PenStyle.DashLine))
            painter.drawLine(x, rect.top(), x, rect.bottom())
            painter.setBrush(c["accent"])
            painter.drawEllipse(QPoint(x, y), 5, 5)

            ts, val = self.points[self.hover_index]
            text = f"{ts}\nБаланс: {val:.2f}"
            tooltip_rect = painter.boundingRect(rect, Qt.AlignmentFlag.AlignLeft, text).adjusted(-8, -6, 8, 6)
            tooltip_rect.moveTopLeft(QPoint(min(max(10, x + 12), self.width() - tooltip_rect.width() - 10), max(10, y - tooltip_rect.height() - 12)))
            painter.setPen(QPen(c["tooltip_border"], 1))
            painter.setBrush(c["tooltip_bg"])
            painter.drawRoundedRect(tooltip_rect, 6, 6)
            painter.setPen(c["text"])
            painter.drawText(tooltip_rect.adjusted(6, 4, -6, -4), Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter, text)


class WorkerThread(QThread):
    def __init__(self, engine):
        super().__init__()
        self.engine = engine

    def run(self):
        self.engine.run()