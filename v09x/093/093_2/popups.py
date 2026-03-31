from __future__ import annotations

from datetime import datetime
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor, QPainter, QPen
from PyQt6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

def format_duration(seconds: object) -> str:
    try:
        total = int(float(seconds or 0))
    except Exception:
        return "—"
    if total <= 0:
        return "—"
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours > 0:
        return f"{hours}ч {minutes:02d}м"
    if minutes > 0:
        return f"{minutes}м {secs:02d}с"
    return f"{secs}с"

class EntryContextChartWidget(QWidget):
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.setMinimumHeight(360)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

    def _safe_float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _price_to_y(self, price: float, min_price: float, max_price: float, top: int, height: int) -> int:
        if max_price <= min_price:
            return top + height // 2
        ratio = (price - min_price) / (max_price - min_price)
        return int(top + height - ratio * height)

    def _parse_candles(self):
        parsed = []
        for candle in self.payload.get("candles") or []:
            try:
                ts = int(candle[0])
                op = float(candle[1])
                hi = float(candle[2])
                lo = float(candle[3])
                cl = float(candle[4])
                parsed.append((ts, op, hi, lo, cl))
            except Exception:
                continue
        return parsed

    def _active_side(self) -> str:
        return str(self.payload.get("side") or "long").strip().lower()

    def _entry_period(self) -> int:
        try:
            return max(1, int(self.payload.get("entry_period") or 20))
        except Exception:
            return 20

    def _build_markers(self, candles):
        markers = []
        if not candles:
            return markers
        entry_price = self._safe_float(self.payload.get("entry_price"), 0.0)
        if entry_price > 0:
            markers.append({"kind": "entry", "label": "E", "index": max(0, len(candles) - 2), "price": entry_price})
        next_pyramid = self._safe_float(self.payload.get("next_pyramid_price"), 0.0)
        if next_pyramid > 0:
            markers.append({"kind": "next", "label": "N", "index": len(candles) - 1, "price": next_pyramid})
        for item in list(self.payload.get("extra_markers") or []):
            try:
                markers.append({
                    "kind": str(item.get("kind") or "event"),
                    "label": str(item.get("label") or "*"),
                    "index": int(item.get("index") or 0),
                    "price": self._safe_float(item.get("price"), 0.0),
                })
            except Exception:
                continue
        return markers

    def _build_donchian_curve(self, candles):
        period = self._entry_period()
        side = self._active_side()
        curve = []
        if len(candles) <= 1:
            return curve
        for idx in range(len(candles)):
            start = max(0, idx - period)
            window = candles[start:idx]
            if not window:
                curve.append(None)
                continue
            try:
                value = max(float(c[2]) for c in window) if side == "long" else min(float(c[3]) for c in window)
            except Exception:
                value = None
            curve.append(value)
        return curve

    def sizeHint(self):
        return self.minimumSizeHint()

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(760, 360)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, self.palette().window())

        candles = self._parse_candles()
        if not candles:
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "Нет сохранённых свечей для отображения")
            return

        left_pad, right_pad, top_pad, bottom_pad = 58, 88, 18, 28
        plot_left = rect.left() + left_pad
        plot_top = rect.top() + top_pad
        plot_width = max(40, rect.width() - left_pad - right_pad)
        plot_height = max(40, rect.height() - top_pad - bottom_pad)
        plot_right = plot_left + plot_width
        plot_bottom = plot_top + plot_height

        scanner_mode = str(self.payload.get('chart_mode') or '').strip().lower() == 'scanner'
        donchian_curve = [] if scanner_mode else self._build_donchian_curve(candles)
        prices = []
        for _, op, hi, lo, cl in candles:
            prices.extend([hi, lo, op, cl])
        for val in donchian_curve:
            if val is not None:
                prices.append(float(val))
        for val in (
            self._safe_float(self.payload.get("entry_price"), 0.0),
            self._safe_float(self.payload.get("stop_price"), 0.0),
            self._safe_float(self.payload.get("next_pyramid_price"), 0.0),
        ):
            if val > 0:
                prices.append(val)
        min_price = min(prices)
        max_price = max(prices)
        if max_price <= min_price:
            max_price = min_price + 1.0
        pad = (max_price - min_price) * 0.08
        min_price -= pad
        max_price += pad

        frame_pen = QPen(self.palette().mid().color())
        frame_pen.setWidth(1)
        painter.setPen(frame_pen)
        painter.drawRoundedRect(rect.adjusted(1, 1, -2, -2), 10, 10)

        grid_pen = QPen(self.palette().mid().color())
        grid_pen.setStyle(Qt.PenStyle.DotLine)
        painter.setPen(grid_pen)
        for i in range(5):
            y = plot_top + int(plot_height * i / 4)
            painter.drawLine(plot_left, y, plot_right, y)
        painter.drawRect(plot_left, plot_top, plot_width, plot_height)

        label_pen = QPen(self.palette().text().color())
        painter.setPen(label_pen)
        for i in range(5):
            price = max_price - (max_price - min_price) * i / 4
            y = plot_top + int(plot_height * i / 4)
            painter.drawText(rect.left() + 4, y + 4, f"{price:.6f}")

        n = len(candles)
        step_x = plot_width / max(1, n)
        body_w = max(3, min(14, int(step_x * 0.65)))
        bull_color = QColor(40, 167, 69)
        bear_color = QColor(220, 53, 69)
        wick_color = self.palette().text().color()
        x_coords = []

        if not scanner_mode:
            highlight_period = min(self._entry_period(), len(candles))
            if highlight_period > 0:
                start_idx = max(0, len(candles) - highlight_period)
                hl_x1 = int(plot_left + step_x * start_idx)
                hl_x2 = int(plot_left + step_x * len(candles))
                shade = QColor(34, 197, 94, 28) if self._active_side() == "long" else QColor(239, 68, 68, 28)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(shade)
                painter.drawRect(hl_x1, plot_top + 1, max(8, hl_x2 - hl_x1), plot_height - 1)

        for i, candle in enumerate(candles):
            _, op, hi, lo, cl = candle
            x = int(plot_left + step_x * i + step_x / 2)
            x_coords.append(x)
            y_hi = self._price_to_y(hi, min_price, max_price, plot_top, plot_height)
            y_lo = self._price_to_y(lo, min_price, max_price, plot_top, plot_height)
            y_op = self._price_to_y(op, min_price, max_price, plot_top, plot_height)
            y_cl = self._price_to_y(cl, min_price, max_price, plot_top, plot_height)
            painter.setPen(QPen(wick_color))
            painter.drawLine(x, y_hi, x, y_lo)
            top = min(y_op, y_cl)
            h = max(2, abs(y_cl - y_op))
            body_rect_x = int(x - body_w / 2)
            painter.fillRect(body_rect_x, top, body_w, h, bull_color if cl >= op else bear_color)
            painter.drawRect(body_rect_x, top, body_w, h)

        curve_color = QColor(22, 163, 74) if self._active_side() == "long" else QColor(220, 38, 38)
        if not scanner_mode:
            curve_pen = QPen(curve_color, 2)
            curve_pen.setStyle(Qt.PenStyle.SolidLine)
            painter.setPen(curve_pen)
            prev_pt = None
            for idx, value in enumerate(donchian_curve):
                if value is None or idx >= len(x_coords):
                    prev_pt = None
                    continue
                point = (x_coords[idx], self._price_to_y(float(value), min_price, max_price, plot_top, plot_height))
                if prev_pt is not None:
                    painter.drawLine(prev_pt[0], prev_pt[1], point[0], point[1])
                prev_pt = point

        def draw_hline(price, label, color, style=Qt.PenStyle.SolidLine):
            if price <= 0:
                return
            y = self._price_to_y(float(price), min_price, max_price, plot_top, plot_height)
            pen = QPen(color)
            pen.setStyle(style)
            pen.setWidth(2)
            painter.setPen(pen)
            painter.drawLine(plot_left, y, plot_right, y)
            painter.drawText(plot_right + 6, y + 4, label)

        if not scanner_mode:
            draw_hline(self._safe_float(self.payload.get("entry_price"), 0.0), "Entry", QColor(30, 144, 255), Qt.PenStyle.DashLine)
            draw_hline(self._safe_float(self.payload.get("stop_price"), 0.0), "Stop", QColor(220, 53, 69), Qt.PenStyle.SolidLine)
            draw_hline(float(candles[-1][4]), "Now", QColor(255, 193, 7), Qt.PenStyle.DotLine)

            markers = self._build_markers(candles)
            for marker in markers:
                idx = int(marker.get("index", -1))
                if idx < 0 or idx >= len(x_coords):
                    continue
                x = x_coords[idx]
                y = self._price_to_y(float(marker.get("price", 0.0) or candles[idx][4]), min_price, max_price, plot_top, plot_height)
                kind = str(marker.get("kind") or "")
                color = QColor(30, 144, 255) if kind == "entry" else QColor(255, 193, 7)
                painter.setPen(QPen(color, 2))
                painter.setBrush(color)
                painter.drawEllipse(x - 5, y - 5, 10, 10)
                painter.setPen(label_pen)
                painter.drawText(x + 7, max(plot_top + 12, y - 8), str(marker.get("label") or ""))

            painter.setPen(curve_color)
            painter.drawText(plot_left + 8, plot_top + 16, f"Donchian {self._entry_period()} ({'верхняя' if self._active_side() == 'long' else 'нижняя'})")
            painter.setPen(label_pen)

        try:
            first_ts = candles[0][0] / 1000
            last_ts = candles[-1][0] / 1000
            painter.setPen(label_pen)
            painter.drawText(plot_left, plot_bottom + 18, datetime.fromtimestamp(first_ts).strftime("%d.%m %H:%M"))
            painter.drawText(plot_right - 80, plot_bottom + 18, datetime.fromtimestamp(last_ts).strftime("%d.%m %H:%M"))
        except Exception:
            pass

class EntryContextDialog(QDialog):
    def __init__(self, payload: dict, context_file: str, parent=None, live_state: Optional[dict] = None):
        super().__init__(parent)
        self.payload = payload or {}
        self.context_file = context_file
        self.live_state = live_state or {}
        self.setWindowTitle(f"Позиция — {self.payload.get('inst_id', 'позиция')}")
        self.resize(1080, 820)
        self.setStyleSheet("""
            QDialog { background: #050816; color: #e6ecff; }
            QLabel { color: #e6ecff; }
            QFrame.sectionCard {
                background: #08111f;
                border: 1px solid #1b3b63;
                border-radius: 16px;
            }
            QFrame.metricCard {
                background: #091427;
                border: 1px solid #16365d;
                border-radius: 14px;
            }
            QLabel.sectionTitle {
                color: #9dd8ff;
                font-size: 12px;
                font-weight: 800;
                letter-spacing: 0.8px;
            }
            QLabel.metricTitle {
                color: #8bb5d9;
                font-size: 11px;
                font-weight: 700;
            }
            QLabel.metricValue {
                color: #f8fbff;
                font-size: 16px;
                font-weight: 900;
            }
            QLabel.metricHint {
                color: #8aa6c2;
                font-size: 10px;
            }
            QPushButton {
                padding: 9px 16px;
                border-radius: 12px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1730, stop:1 #111d36);
                color: #f8fafc;
                border: 1px solid #26558f;
                font-weight: 800;
            }
            QPushButton:hover { border-color: #67e8f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 14, 14, 14)
        layout.setSpacing(10)

        side_value = str(self.payload.get('side', '—')).lower()
        side_text = 'LONG' if side_value == 'long' else ('SHORT' if side_value == 'short' else str(self.payload.get('side', '—')).upper())
        side_color = '#00FFA8' if side_value == 'long' else ('#FF3A5E' if side_value == 'short' else '#64748b')

        header_row = QHBoxLayout()
        header_row.setContentsMargins(0, 0, 0, 0)
        header_row.setSpacing(8)

        title = QLabel(f"{self.payload.get('inst_id', '—')} · {self.payload.get('system_name', '—')} · {self.payload.get('timeframe', '—')}")
        title.setStyleSheet("font-size: 17px; font-weight: 900; color: #edf6ff;")
        header_row.addWidget(title, 1)

        side_badge = QLabel(side_text)
        side_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_badge.setMinimumWidth(110)
        side_badge.setStyleSheet(
            f"font-size: 15px; font-weight: 900; color: #06111f; background: {side_color}; border: 1px solid #d6fff6; border-radius: 14px; padding: 7px 14px;"
        )
        header_row.addWidget(side_badge, 0)

        status_badge = QLabel("ACTIVE")
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setMinimumWidth(110)
        status_badge.setStyleSheet("font-size: 14px; font-weight: 900; color: #e8f7ff; background: #123657; border: 1px solid #3b82f6; border-radius: 14px; padding: 7px 14px;")
        header_row.addWidget(status_badge, 0)
        layout.addLayout(header_row)

        summary = self._build_summary_row()
        layout.addLayout(summary)

        body_row = QHBoxLayout()
        body_row.setContentsMargins(0, 0, 0, 0)
        body_row.setSpacing(10)

        candles = self.payload.get("candles") or []
        chart_box = QFrame(self)
        chart_box.setObjectName("chartBox")
        chart_box.setProperty("class", "sectionCard")
        chart_box.setFrameShape(QFrame.Shape.StyledPanel)
        chart_box.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(6)

        chart_mode_label = "Текущий график" if bool(self.payload.get("live_chart")) else "График входа"
        chart_title = QLabel(f"{chart_mode_label} · свечей: {len(candles)}")
        chart_title.setProperty("class", "sectionTitle")
        chart_title.setStyleSheet("font-size: 13px; font-weight: 700;")
        chart_layout.addWidget(chart_title)

        chart = EntryContextChartWidget(self.payload, chart_box)
        chart_layout.addWidget(chart, 1)
        body_row.addWidget(chart_box, 3)

        right_col = QVBoxLayout()
        right_col.setContentsMargins(0, 0, 0, 0)
        right_col.setSpacing(10)
        right_col.addWidget(self._build_entry_context_card())
        right_col.addWidget(self._build_live_status_card())
        right_col.addWidget(self._build_management_card())
        right_col.addStretch(1)
        body_row.addLayout(right_col, 2)
        layout.addLayout(body_row, 1)

        footer_mode = "LIVE chart + entry context" if bool(self.payload.get("live_chart")) else "ENTRY snapshot"
        footer = QLabel(f"Контекст: {self.context_file}  |  {footer_mode}")
        footer.setStyleSheet("color: #6f8baa; font-size: 11px;")
        layout.addWidget(footer)

        close_btn = QPushButton("Закрыть")
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _build_summary_row(self):
        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(10)
        entry_price = self._num(self.payload.get('entry_price'))
        current_price = self._num(self.live_state.get('last_px')) or entry_price
        pnl_value = self._num(self.live_state.get('unrealized_pnl'))
        pnl_pct = self._num(self.live_state.get('pnl_pct'))
        units = int(self._num(self.live_state.get('units') or self.payload.get('units') or 1))
        duration = self._duration_from_times(self.payload.get('saved_at'), self.live_state.get('entry_time'))
        tiles = [
            ('Entry', self._fmt(entry_price), self._time_only(self.payload.get('saved_at'))),
            ('Current', self._fmt(current_price), f"PnL {self._fmt_signed(pnl_pct, suffix='%') }"),
            ('PnL', self._fmt_signed(pnl_value), self._fmt_signed(pnl_pct, suffix='%')),
            ('Units', str(units), f"Added {max(0, units-1)}"),
            ('Duration', duration, self._time_only(self.live_state.get('entry_time'))),
        ]
        for title, value, hint in tiles:
            row.addWidget(self._metric_card(title, value, hint), 1)
        return row

    def _build_entry_context_card(self):
        entry_period = self.payload.get('entry_period', '—')
        breakout_type = f"Turtle {entry_period}" if str(entry_period).isdigit() else str(self.payload.get('system_name', '—'))
        if breakout_type == 'Turtle —':
            breakout_type = str(self.payload.get('system_name', '—'))
        rows = [
            ('Вход', self._fmt(self.payload.get('entry_price'))),
            ('Время входа', self._fmt_dt(self.payload.get('saved_at'))),
            ('Пробой', breakout_type),
            ('ATR на входе', self._fmt(self.payload.get('atr'))),
            ('Стартовый стоп', self._fmt(self.payload.get('initial_stop_price') or self.payload.get('stop_price'))),
            ('След. добор', self._fmt(self.payload.get('next_pyramid_price'))),
            ('Канал', f"{self._fmt(self.payload.get('channel_low'))} → {self._fmt(self.payload.get('channel_high'))}"),
        ]
        return self._section_card('ENTRY CONTEXT', rows)

    def _build_live_status_card(self):
        last_px = self._num(self.live_state.get('last_px'))
        pnl = self._num(self.live_state.get('unrealized_pnl'))
        pnl_pct = self._num(self.live_state.get('pnl_pct'))
        rows = [
            ('Текущая цена', self._fmt(last_px)),
            ('PnL', self._fmt_signed(pnl)),
            ('PnL %', self._fmt_signed(pnl_pct, suffix='%')),
            ('Текущий стоп', self._fmt(self.live_state.get('stop_price'))),
            ('До стопа', self._fmt_signed(self.live_state.get('stop_distance_pct'), suffix='%')),
            ('ATR сейчас', self._fmt(self.live_state.get('atr'))),
            ('Сила движения', f"{self._num(self.live_state.get('trend_strength_atr')):.2f} ATR" if self.live_state else '—'),
        ]
        return self._section_card('LIVE STATUS', rows)

    def _build_management_card(self):
        rows = [
            ('Юнитов', str(int(self._num(self.live_state.get('units') or 1)))),
            ('Добавлено', str(max(0, int(self._num(self.live_state.get('units') or 1)) - 1))),
            ('Следующий добор', self._fmt(self.live_state.get('next_pyramid_price') or self.payload.get('next_pyramid_price'))),
            ('До добора', self._fmt_signed(self.live_state.get('pyramid_distance_pct'), suffix='%')),
            ('Риск сделки', self._fmt(self.payload.get('risk_amount_usdt'))),
            ('Номинал позиции', self._fmt(self.payload.get('position_notional_usdt'))),
            ('Режим', str(self.payload.get('trade_mode', '—'))),
        ]
        return self._section_card('TRADE MANAGEMENT', rows)

    def _section_card(self, title: str, rows: list[tuple[str, str]]):
        card = QFrame(self)
        card.setProperty('class', 'sectionCard')
        layout = QVBoxLayout(card)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)
        lbl = QLabel(title)
        lbl.setProperty('class', 'sectionTitle')
        layout.addWidget(lbl)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (name, value) in enumerate(rows):
            name_lbl = QLabel(name)
            name_lbl.setStyleSheet('color: #86a9c9; font-size: 11px; font-weight: 700;')
            val_lbl = QLabel(value if str(value).strip() else '—')
            val_lbl.setStyleSheet('color: #f8fbff; font-size: 12px; font-weight: 800;')
            val_lbl.setWordWrap(True)
            grid.addWidget(name_lbl, i, 0)
            grid.addWidget(val_lbl, i, 1)
        grid.setColumnStretch(1, 1)
        layout.addLayout(grid)
        return card

    def _metric_card(self, title: str, value: str, hint: str = ''):
        card = QFrame(self)
        card.setProperty('class', 'metricCard')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setProperty('class', 'metricTitle')
        v = QLabel(value if str(value).strip() else '—')
        v.setProperty('class', 'metricValue')
        h = QLabel(hint if str(hint).strip() else ' ')
        h.setProperty('class', 'metricHint')
        lay.addWidget(t)
        lay.addWidget(v)
        lay.addWidget(h)
        return card

    @staticmethod
    def _num(value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @classmethod
    def _fmt(cls, value) -> str:
        try:
            return f"{float(value):.6f}"
        except Exception:
            return '—'

    @classmethod
    def _fmt_signed(cls, value, suffix: str = '') -> str:
        try:
            num = float(value)
            if suffix == '%':
                return f"{num:+.2f}%"
            return f"{num:+.4f}{suffix}"
        except Exception:
            return '—'

    @staticmethod
    def _fmt_dt(value) -> str:
        txt = str(value or '').strip()
        if not txt:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(txt, fmt).strftime('%d.%m.%Y %H:%M:%S')
            except Exception:
                continue
        return txt

    @staticmethod
    def _time_only(value) -> str:
        txt = str(value or '').strip()
        if not txt:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(txt, fmt).strftime('%H:%M:%S')
            except Exception:
                continue
        return txt[-8:]

    def _duration_from_times(self, entry_saved_at, live_entry_time) -> str:
        base = str(live_entry_time or entry_saved_at or '').strip()
        if not base:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                started = datetime.strptime(base, fmt)
                return format_duration(max(0, int((datetime.now() - started).total_seconds())))
            except Exception:
                continue
        return '—'

class TradeLifecycleChartWidget(QWidget):
    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.setMinimumHeight(420)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setAutoFillBackground(True)

    def _safe_float(self, value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    def _parse_candles(self):
        parsed = []
        for candle in self.payload.get("candles") or []:
            try:
                ts = int(candle[0]); op = float(candle[1]); hi = float(candle[2]); lo = float(candle[3]); cl = float(candle[4])
                parsed.append((ts, op, hi, lo, cl))
            except Exception:
                continue
        return parsed

    def _price_to_y(self, price: float, min_price: float, max_price: float, top: int, height: int) -> int:
        if max_price <= min_price:
            return top + height // 2
        ratio = (price - min_price) / (max_price - min_price)
        return int(top + height - ratio * height)

    def minimumSizeHint(self):
        from PyQt6.QtCore import QSize
        return QSize(860, 420)

    def sizeHint(self):
        return self.minimumSizeHint()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()
        painter.fillRect(rect, self.palette().window())
        candles = self._parse_candles()
        if not candles:
            painter.setPen(self.palette().text().color())
            painter.drawText(rect, int(Qt.AlignmentFlag.AlignCenter), "Нет сохранённых свечей по жизненному циклу сделки")
            return
        left_pad, right_pad, top_pad, bottom_pad = 60, 110, 22, 34
        plot_left = rect.left() + left_pad
        plot_top = rect.top() + top_pad
        plot_width = max(60, rect.width() - left_pad - right_pad)
        plot_height = max(60, rect.height() - top_pad - bottom_pad)
        plot_right = plot_left + plot_width
        plot_bottom = plot_top + plot_height
        prices=[]
        for _,op,hi,lo,cl in candles:
            prices.extend([op,hi,lo,cl])
        entry_price=self._safe_float(self.payload.get("entry_price"),0.0)
        exit_price=self._safe_float(self.payload.get("exit_price"),0.0)
        final_stop=self._safe_float(self.payload.get("final_stop_price"),0.0)
        for p in (entry_price,exit_price,final_stop):
            if p>0: prices.append(p)
        min_price=min(prices); max_price=max(prices)
        if max_price<=min_price: max_price=min_price+1.0
        pad=(max_price-min_price)*0.08
        min_price-=pad; max_price+=pad
        frame_pen = QPen(self.palette().mid().color()); frame_pen.setWidth(1); painter.setPen(frame_pen)
        painter.drawRoundedRect(rect.adjusted(1,1,-2,-2),10,10)
        grid_pen=QPen(self.palette().mid().color()); grid_pen.setStyle(Qt.PenStyle.DotLine); painter.setPen(grid_pen)
        for i in range(5):
            y=plot_top+int(plot_height*i/4); painter.drawLine(plot_left,y,plot_right,y)
        painter.drawRect(plot_left,plot_top,plot_width,plot_height)
        text_pen=QPen(self.palette().text().color()); painter.setPen(text_pen)
        for i in range(5):
            price=max_price-(max_price-min_price)*i/4; y=plot_top+int(plot_height*i/4); painter.drawText(rect.left()+4,y+4,f"{price:.6f}")
        n=len(candles); step_x=plot_width/max(1,n); body_w=max(3,min(14,int(step_x*0.65)))
        bull_color=QColor(40,167,69); bear_color=QColor(220,53,69); wick_color=self.palette().text().color()
        markers=list(self.payload.get("markers") or [])
        x_coords=[]
        entry_idx=next((int(m.get("index",-1)) for m in markers if str(m.get("kind"))=="entry"),-1)
        exit_idx=next((int(m.get("index",-1)) for m in markers if str(m.get("kind"))=="exit"),-1)
        if 0<=entry_idx<n and 0<=exit_idx<n and exit_idx>=entry_idx:
            start_x=int(plot_left+step_x*entry_idx); end_x=int(plot_left+step_x*(exit_idx+1))
            painter.setPen(Qt.PenStyle.NoPen); painter.setBrush(QColor(59,130,246,28)); painter.drawRect(start_x, plot_top+1, max(8,end_x-start_x), plot_height-1)
        for i,candle in enumerate(candles):
            _,op,hi,lo,cl=candle; x=int(plot_left+step_x*i+step_x/2); x_coords.append(x)
            y_hi=self._price_to_y(hi,min_price,max_price,plot_top,plot_height); y_lo=self._price_to_y(lo,min_price,max_price,plot_top,plot_height)
            y_op=self._price_to_y(op,min_price,max_price,plot_top,plot_height); y_cl=self._price_to_y(cl,min_price,max_price,plot_top,plot_height)
            painter.setPen(QPen(wick_color)); painter.drawLine(x,y_hi,x,y_lo)
            top=min(y_op,y_cl); h=max(2,abs(y_cl-y_op)); body_rect_x=int(x-body_w/2)
            painter.fillRect(body_rect_x, top, body_w, h, bull_color if cl>=op else bear_color); painter.drawRect(body_rect_x, top, body_w, h)
        def draw_hline(price,label,color,style=Qt.PenStyle.SolidLine):
            if price<=0: return
            y=self._price_to_y(price,min_price,max_price,plot_top,plot_height)
            pen=QPen(color); pen.setStyle(style); pen.setWidth(2); painter.setPen(pen); painter.drawLine(plot_left,y,plot_right,y); painter.drawText(plot_right+6,y+4,label)
        draw_hline(entry_price,'Entry',QColor(30,144,255),Qt.PenStyle.DashLine)
        draw_hline(final_stop,'Stop',QColor(220,53,69),Qt.PenStyle.SolidLine)
        if exit_price>0: draw_hline(exit_price,'Exit',QColor(255,193,7),Qt.PenStyle.DotLine)
        for marker in markers:
            idx=int(marker.get("index",-1))
            if idx<0 or idx>=len(x_coords): continue
            x=x_coords[idx]; price=self._safe_float(marker.get("price"),0.0); y=self._price_to_y(price if price>0 else candles[idx][4], min_price,max_price,plot_top,plot_height)
            kind=str(marker.get("kind") or '').lower(); label=str(marker.get("label") or '')
            color=QColor(32,201,151) if kind.startswith('add') else (QColor(255,193,7) if kind=='exit' else QColor(30,144,255))
            painter.setPen(QPen(color,2)); painter.setBrush(color); painter.drawEllipse(x-5,y-5,10,10); painter.setPen(text_pen); painter.drawText(x+7,max(plot_top+12,y-8),label)
        try:
            first_ts=candles[0][0]/1000; last_ts=candles[-1][0]/1000; painter.setPen(text_pen)
            painter.drawText(plot_left,plot_bottom+18,datetime.fromtimestamp(first_ts).strftime('%d.%m %H:%M'))
            painter.drawText(plot_right-84,plot_bottom+18,datetime.fromtimestamp(last_ts).strftime('%d.%m %H:%M'))
        except Exception:
            pass

class TradeLifecycleDialog(QDialog):
    def __init__(self, payload: dict, context_file: str, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self.context_file = context_file
        self.setWindowTitle(f"Сделка — {self.payload.get('inst_id', 'сделка')}")
        self.resize(1120, 820)
        self.setStyleSheet("""
            QDialog { background: #050816; color: #e6ecff; }
            QLabel { color: #e6ecff; }
            QFrame.sectionCard {
                background: #08111f;
                border: 1px solid #1b3b63;
                border-radius: 16px;
            }
            QFrame.metricCard {
                background: #091427;
                border: 1px solid #16365d;
                border-radius: 14px;
            }
            QPushButton {
                padding: 9px 16px;
                border-radius: 12px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1730, stop:1 #111d36);
                color: #f8fafc;
                border: 1px solid #26558f;
                font-weight: 800;
            }
            QPushButton:hover { border-color: #67e8f9; }
        """)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        side_value = str(self.payload.get('side', '—')).lower()
        side_text = 'LONG' if side_value == 'long' else ('SHORT' if side_value == 'short' else str(self.payload.get('side', '—')).upper())
        side_color = '#00FFA8' if side_value == 'long' else ('#FF3A5E' if side_value == 'short' else '#64748b')

        header_row = QHBoxLayout()
        title = QLabel(f"{self.payload.get('inst_id', '—')} · {self.payload.get('system_name', '—')} · {self.payload.get('timeframe', '—')}")
        title.setStyleSheet("font-size: 17px; font-weight: 900; color: #edf6ff;")
        header_row.addWidget(title, 1)
        side_badge = QLabel(side_text)
        side_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        side_badge.setMinimumWidth(110)
        side_badge.setStyleSheet(f"font-size: 15px; font-weight: 900; color: #06111f; background: {side_color}; border: 1px solid #d6fff6; border-radius: 14px; padding: 7px 14px;")
        header_row.addWidget(side_badge)
        status_badge = QLabel("CLOSED")
        status_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        status_badge.setMinimumWidth(110)
        status_badge.setStyleSheet("font-size: 14px; font-weight: 900; color: #fff6e5; background: #473217; border: 1px solid #f59e0b; border-radius: 14px; padding: 7px 14px;")
        header_row.addWidget(status_badge)
        layout.addLayout(header_row)

        summary = QHBoxLayout()
        summary.setSpacing(10)
        for title_text, value_text, hint_text in [
            ('Entry', self._fmt(self.payload.get('entry_price')), self._time_only(self.payload.get('entry_time'))),
            ('Exit', self._fmt(self.payload.get('exit_price')), self._time_only(self.payload.get('exit_time'))),
            ('PnL', self._fmt_signed(self.payload.get('pnl')), self._fmt_signed(self.payload.get('pnl_pct'), suffix='%')),
            ('Units', str(int(self._num(self.payload.get('units') or 1))), f"Adds {max(0, int(self._num(self.payload.get('units') or 1)) - 1)}"),
            ('Duration', format_duration(self._num(self.payload.get('duration_sec'), 0)), str(self.payload.get('reason', '—'))),
        ]:
            summary.addWidget(self._metric_card(title_text, value_text, hint_text), 1)
        layout.addLayout(summary)

        body_row = QHBoxLayout()
        body_row.setSpacing(10)

        chart_box = QFrame(self)
        chart_box.setProperty('class', 'sectionCard')
        chart_layout = QVBoxLayout(chart_box)
        chart_layout.setContentsMargins(10, 10, 10, 10)
        chart_layout.setSpacing(6)
        chart_title = QLabel(f"График сделки · свечей: {len(self.payload.get('candles') or [])}")
        chart_title.setStyleSheet('color: #9dd8ff; font-size: 13px; font-weight: 700;')
        chart_layout.addWidget(chart_title)
        chart_layout.addWidget(TradeLifecycleChartWidget(self.payload, chart_box), 1)
        body_row.addWidget(chart_box, 3)

        right_col = QVBoxLayout()
        right_col.setSpacing(10)
        right_col.addWidget(self._section_card('RESULT', [
            ('Вход', self._fmt(self.payload.get('entry_price'))),
            ('Выход', self._fmt(self.payload.get('exit_price'))),
            ('PnL', self._fmt_signed(self.payload.get('pnl'))),
            ('PnL %', self._fmt_signed(self.payload.get('pnl_pct'), suffix='%')),
            ('Причина', str(self.payload.get('reason', '—'))),
            ('Длительность', format_duration(self._num(self.payload.get('duration_sec'), 0))),
        ]))
        right_col.addWidget(self._section_card('ENTRY CONTEXT', [
            ('Пробой', str(self.payload.get('system_name', '—'))),
            ('ATR на входе', self._fmt(self.payload.get('entry_atr'))),
            ('Стартовый стоп', self._fmt(self.payload.get('start_stop_price'))),
            ('Канал выхода', self._fmt(self.payload.get('channel_exit_level'))),
            ('MFE / MAE', f"{self._fmt_signed(self.payload.get('mfe_pct'), suffix='%')} / {self._fmt_signed(self.payload.get('mae_pct'), suffix='%')}"),
            ('R multiple', self._fmt_signed(self.payload.get('mfe_r'))),
        ]))
        markers = self.payload.get('markers') or []
        marker_lines = []
        for marker in markers[:8]:
            label = str(marker.get('label') or '•')
            tm = str(marker.get('time') or '—')
            px = self._fmt(marker.get('price'))
            marker_lines.append((label, f"{tm} @ {px}"))
        right_col.addWidget(self._section_card('TIMELINE', marker_lines or [('События', 'нет сохранённых событий')]))
        right_col.addStretch(1)
        body_row.addLayout(right_col, 2)
        layout.addLayout(body_row, 1)

        footer_mode = "LIVE chart + entry context" if bool(self.payload.get("live_chart")) else "ENTRY snapshot"
        footer = QLabel(f"Контекст: {self.context_file}  |  {footer_mode}")
        footer.setStyleSheet('color: #6f8baa; font-size: 11px;')
        layout.addWidget(footer)

        close_btn = QPushButton('Закрыть')
        close_btn.clicked.connect(self.accept)
        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_row.addWidget(close_btn)
        layout.addLayout(btn_row)

    def _section_card(self, title: str, rows: list[tuple[str, str]]):
        card = QFrame(self)
        card.setProperty('class', 'sectionCard')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)
        hdr = QLabel(title)
        hdr.setStyleSheet('color: #9dd8ff; font-size: 12px; font-weight: 800;')
        lay.addWidget(hdr)
        grid = QGridLayout()
        grid.setHorizontalSpacing(10)
        grid.setVerticalSpacing(6)
        for i, (name, value) in enumerate(rows):
            a = QLabel(name)
            a.setStyleSheet('color: #86a9c9; font-size: 11px; font-weight: 700;')
            b = QLabel(value if str(value).strip() else '—')
            b.setStyleSheet('color: #f8fbff; font-size: 12px; font-weight: 800;')
            b.setWordWrap(True)
            grid.addWidget(a, i, 0)
            grid.addWidget(b, i, 1)
        grid.setColumnStretch(1, 1)
        lay.addLayout(grid)
        return card

    def _metric_card(self, title: str, value: str, hint: str = ''):
        card = QFrame(self)
        card.setProperty('class', 'metricCard')
        lay = QVBoxLayout(card)
        lay.setContentsMargins(12, 10, 12, 10)
        lay.setSpacing(2)
        t = QLabel(title)
        t.setStyleSheet('color: #8bb5d9; font-size: 11px; font-weight: 700;')
        v = QLabel(value if str(value).strip() else '—')
        v.setStyleSheet('color: #f8fbff; font-size: 16px; font-weight: 900;')
        h = QLabel(hint if str(hint).strip() else ' ')
        h.setStyleSheet('color: #8aa6c2; font-size: 10px;')
        lay.addWidget(t); lay.addWidget(v); lay.addWidget(h)
        return card

    @staticmethod
    def _num(value, default=0.0) -> float:
        try:
            return float(value)
        except Exception:
            return float(default)

    @classmethod
    def _fmt(cls, value) -> str:
        try:
            return f"{float(value):.6f}"
        except Exception:
            return '—'

    @classmethod
    def _fmt_signed(cls, value, suffix: str = '') -> str:
        try:
            num = float(value)
            if suffix == '%':
                return f"{num:+.2f}%"
            return f"{num:+.4f}{suffix}"
        except Exception:
            return '—'

    @staticmethod
    def _time_only(value) -> str:
        txt = str(value or '').strip()
        if not txt:
            return '—'
        for fmt in ('%Y-%m-%d %H:%M:%S', '%Y-%m-%d %H:%M'):
            try:
                return datetime.strptime(txt, fmt).strftime('%H:%M:%S')
            except Exception:
                continue
        return txt[-8:]

class ScannerReviewDialog(QDialog):
    REVIEW_TAGS = ["хороший", "пила", "мертвый", "рваный", "плохой"]

    def __init__(self, payload: dict, parent=None):
        super().__init__(parent)
        self.payload = payload or {}
        self._saved = False
        self._tag_buttons = {}
        self.setWindowTitle(f"Проверка фильтра — {self.payload.get('inst_id', '—')}")
        self.resize(1080, 760)
        root = QVBoxLayout(self)
        root.setContentsMargins(12, 12, 12, 12)
        root.setSpacing(8)

        filter_label = {'DEAD': 'Мёртвый рынок', 'SAW': 'Пила', 'RIPPING': 'Рваный рынок', 'GOOD': 'Хорошие позиции'}.get(str(self.payload.get('scanner_filter_type') or '').upper(), str(self.payload.get('scanner_filter_type', '—')))
        title = QLabel(f"{self.payload.get('inst_id', '—')} · {filter_label} · TF {self.payload.get('timeframe', '—')}")
        title.setStyleSheet("font-size:18px;font-weight:700;")
        root.addWidget(title)

        reason = QLabel(str(self.payload.get('scanner_reason') or ''))
        reason.setWordWrap(True)
        reason.setStyleSheet("color:#9fe7ff;")
        root.addWidget(reason)

        tags_row = QHBoxLayout()
        tags_row.setSpacing(8)
        tags_lbl = QLabel("Тэги:")
        tags_lbl.setStyleSheet("font-weight:600;")
        tags_row.addWidget(tags_lbl)
        preset_tags = self._normalize_tags(self.payload.get('scanner_review_tags') or self.payload.get('scanner_user_verdict'))
        for tag in self.REVIEW_TAGS:
            btn = QPushButton(tag.capitalize())
            btn.setCheckable(True)
            btn.setChecked(tag in preset_tags)
            btn.clicked.connect(self._apply_tag_styles)
            self._tag_buttons[tag] = btn
            tags_row.addWidget(btn)
        tags_row.addStretch(1)
        root.addLayout(tags_row)

        comment_row = QHBoxLayout()
        comment_row.setSpacing(8)
        comment_lbl = QLabel("Комментарий:")
        comment_lbl.setStyleSheet("font-weight:600;")
        comment_row.addWidget(comment_lbl)
        self.comment_edit = QLineEdit(self)
        self.comment_edit.setPlaceholderText("Комментарий (необязательно)")
        self.comment_edit.setText(str(self.payload.get('scanner_user_comment') or ''))
        comment_row.addWidget(self.comment_edit, 1)
        root.addLayout(comment_row)

        chart = EntryContextChartWidget(self.payload, self)
        chart.setMinimumHeight(460)
        root.addWidget(chart, 1)

        btn_row = QHBoxLayout()
        btn_row.addStretch(1)
        btn_cancel = QPushButton("Отмена")
        btn_cancel.clicked.connect(self.reject)
        btn_row.addWidget(btn_cancel)
        btn_save = QPushButton("Сохранить")
        btn_save.clicked.connect(self._accept_and_save)
        btn_row.addWidget(btn_save)
        root.addLayout(btn_row)

        self._apply_tag_styles()

    def _normalize_tags(self, value) -> list[str]:
        if isinstance(value, str):
            parts = [part.strip().lower() for part in value.replace(';', ',').split(',')]
        elif isinstance(value, (list, tuple, set)):
            parts = [str(part).strip().lower() for part in value]
        else:
            parts = []
        legacy_map = {'подтверждено': 'хороший', 'не подтверждено': 'плохой'}
        result = []
        for part in parts:
            part = legacy_map.get(part, part)
            if part in self.REVIEW_TAGS and part not in result:
                result.append(part)
        return result

    def _tag_style(self, tag: str, checked: bool) -> str:
        colors = {
            'хороший': ('#1d7f4e', '#2be28c'),
            'пила': ('#795548', '#d7a86e'),
            'мертвый': ('#394867', '#8aa4d6'),
            'рваный': ('#7b3f00', '#ffb347'),
            'плохой': ('#a52a36', '#ff7080'),
        }
        bg, border = colors.get(tag, ('#334155', '#94a3b8'))
        if checked:
            return f"QPushButton {{ background:{bg}; color:#f8fbff; border:1px solid {border}; border-radius:10px; padding:6px 12px; font-weight:600; }}"
        return "QPushButton { background:#0f172a; color:#cbd5e1; border:1px solid #334155; border-radius:10px; padding:6px 12px; }"

    def _apply_tag_styles(self) -> None:
        for tag, btn in self._tag_buttons.items():
            btn.setStyleSheet(self._tag_style(tag, btn.isChecked()))

    def _accept_and_save(self) -> None:
        self._saved = True
        self.accept()

    def selected_verdict(self) -> str:
        tags = self.selected_tags()
        return ', '.join(tags) if tags else 'Не проверено'

    def selected_tags(self) -> list[str]:
        return [tag for tag, btn in self._tag_buttons.items() if btn.isChecked()]

    def selected_comment(self) -> str:
        return str(self.comment_edit.text() or '').strip()

    def was_saved(self) -> bool:
        return bool(self._saved)
