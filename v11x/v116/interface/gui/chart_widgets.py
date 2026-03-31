from app.runtime_support import *

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
        self.points: List[dict] = []
        self.markers: List[dict] = []
        self.step_code = "1m"
        self.dark_theme = False
        self.setMinimumHeight(200)

    def update_points(self, points: List[dict], step_code: Optional[str] = None, markers: Optional[List[dict]] = None) -> None:
        self.points = points or []
        if markers is not None:
            self.markers = markers or []
        if step_code:
            self.step_code = step_code
        self.update()

    def set_step(self, step_code: str) -> None:
        self.step_code = step_code or "1m"
        self.update()

    def set_dark_theme(self, is_dark: bool) -> None:
        self.dark_theme = bool(is_dark)
        self.update()

    def _parse_dt(self, value: object) -> Optional[datetime]:
        text = str(value or "").strip()
        if not text:
            return None
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%dT%H:%M:%S", "%H:%M:%S"):
            try:
                dt = datetime.strptime(text, fmt)
                if fmt == "%H:%M:%S":
                    now = datetime.now()
                    dt = dt.replace(year=now.year, month=now.month, day=now.day)
                return dt
            except ValueError:
                continue
        return None

    def _bucket_points(self) -> List[dict]:
        if not self.points:
            return []
        step_sec = self.STEP_SECONDS.get(self.step_code, 60)
        parsed: List[Tuple[datetime, dict]] = []
        for point in self.points:
            dt = self._parse_dt(point.get("time"))
            if dt is None:
                continue
            parsed.append((dt, point))
        if not parsed:
            return []
        parsed.sort(key=lambda item: item[0])
        buckets: List[dict] = []
        bucket_start = None
        bucket_values: List[float] = []
        last_dt: Optional[datetime] = None
        for dt, point in parsed:
            ts = int(dt.timestamp())
            aligned_ts = ts - (ts % step_sec)
            aligned = datetime.fromtimestamp(aligned_ts)
            if bucket_start is None:
                bucket_start = aligned
            if aligned != bucket_start:
                if bucket_values:
                    buckets.append({
                        "time": bucket_start.strftime("%H:%M:%S" if self.step_code not in {"1D"} else "%m-%d"),
                        "value": bucket_values[-1],
                        "open": bucket_values[0],
                        "close": bucket_values[-1],
                        "high": max(bucket_values),
                        "low": min(bucket_values),
                        "samples": len(bucket_values),
                    })
                bucket_start = aligned
                bucket_values = []
            bucket_values.append(float(point.get("balance_total", 0.0)))
            last_dt = dt
        if bucket_values and bucket_start is not None:
            buckets.append({
                "time": bucket_start.strftime("%H:%M:%S" if self.step_code not in {"1D"} else "%m-%d"),
                "value": bucket_values[-1],
                "open": bucket_values[0],
                "close": bucket_values[-1],
                "high": max(bucket_values),
                "low": min(bucket_values),
                "samples": len(bucket_values),
            })
        if len(buckets) == 1 and last_dt is not None:
            buckets[0]["time"] = last_dt.strftime("%H:%M:%S" if self.step_code not in {"1D"} else "%m-%d")
        return buckets

    def _display_equity_slots(self) -> Tuple[List[float], int, float, float, float, str]:
        bucketed = self._bucket_points()
        actual_count = len(bucketed)
        if actual_count <= 0:
            return [0.0], 0, 0.0, 0.0, 0.0, "ожидание"
        raw_values = [float(point.get("value", 0.0)) for point in bucketed]
        current_balance = raw_values[-1] if raw_values else 0.0
        session_change = (raw_values[-1] - raw_values[0]) if len(raw_values) >= 2 else 0.0
        session_change_pct = (session_change / raw_values[0] * 100.0) if raw_values and abs(raw_values[0]) > 1e-12 else 0.0
        last_label = str(bucketed[-1].get("time", "—"))
        return raw_values, actual_count, current_balance, session_change, session_change_pct, last_label

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect()
        rect = outer.adjusted(8, 8, -8, -8)

        bg_color = QColor(6, 12, 24) if self.dark_theme else QColor(255, 255, 255)
        border_color = QColor(33, 78, 142) if self.dark_theme else QColor(225, 228, 235)
        muted_color = QColor(124, 132, 145) if self.dark_theme else QColor(128, 128, 128)
        neon_green = QColor(0, 255, 168)
        pos_color = neon_green
        neg_color = QColor(239, 68, 68)
        grid_color = QColor(38, 45, 56) if self.dark_theme else QColor(234, 236, 240)

        if self.dark_theme:
            bg_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
            bg_grad.setColorAt(0.0, QColor(5, 15, 30))
            bg_grad.setColorAt(1.0, QColor(12, 9, 28))
            painter.fillRect(outer, bg_grad)
            for width, alpha in ((8, 18), (4, 30)):
                painter.setPen(QPen(QColor(0, 224, 255, alpha), width))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawRoundedRect(rect, 16, 16)
        else:
            painter.fillRect(outer, bg_color)
        painter.setPen(QPen(border_color, 1))
        painter.drawRoundedRect(rect, 14, 14)

        bucketed = self._bucket_points()
        equity_values, actual_count, current_balance, session_change, session_change_pct, last_label = self._display_equity_slots()
        visible_offset = max(0, len(equity_values) - len(bucketed))

        # OKX-like header
        header_rect = rect.adjusted(14, 10, -14, -rect.height() + 46)
        pnl_color = pos_color if session_change >= 0 else neg_color
        painter.setPen(pnl_color)
        header_font = painter.font()
        header_font.setPointSize(14)
        header_font.setBold(True)
        painter.setFont(header_font)
        painter.drawText(header_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"{current_balance:.2f} USDT")

        sub_rect = rect.adjusted(14, 30, -14, -rect.height() + 60)
        sub_font = painter.font()
        sub_font.setPointSize(9)
        sub_font.setBold(False)
        painter.setFont(sub_font)
        tail = last_label if actual_count > 0 else "ожидание данных"
        painter.drawText(sub_rect, int(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop), f"Сессия {session_change:+.2f} USDT ({session_change_pct:+.2f}%)  ·  {tail}")

        plot = rect.adjusted(14, 64, -14, -18)

        min_val = min(equity_values)
        max_val = max(equity_values)
        span = max_val - min_val
        pad = max(span * 0.18, 0.5)
        min_plot = min_val - pad
        max_plot = max_val + pad
        if abs(max_plot - min_plot) < 1e-12:
            max_plot += 1.0
            min_plot -= 1.0

        def value_to_y(value: float) -> int:
            return int(plot.bottom() - ((value - min_plot) / (max_plot - min_plot)) * plot.height())

        baseline_value = equity_values[0] if equity_values else 0.0
        zero_y = value_to_y(baseline_value)

        painter.setPen(QPen(grid_color, 1, Qt.PenStyle.DashLine))
        y_marks = []
        for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
            y = int(plot.top() + plot.height() * frac)
            value = max_plot - (max_plot - min_plot) * frac
            y_marks.append((y, value))
            painter.drawLine(plot.left(), y, plot.right(), y)

        painter.setPen(muted_color)
        for y, value in y_marks:
            painter.drawText(plot.right() - 64, y - 2, f"{value:.2f}")

        painter.setPen(QPen(QColor(110, 118, 132), 1, Qt.PenStyle.DashLine))
        painter.drawLine(plot.left(), zero_y, plot.right(), zero_y)

        step_x = plot.width() / max(1, (len(equity_values) - 1))
        x_positions = [plot.left() + i * step_x for i in range(len(equity_values))]
        line_points = [(int(x), value_to_y(val)) for x, val in zip(x_positions, equity_values)]
        line_color = pos_color if session_change >= 0 else neg_color
        area_color = QColor(line_color.red(), line_color.green(), line_color.blue(), 70)

        area = QPolygon()
        area.append(QPoint(line_points[0][0], zero_y))
        for x, y in line_points:
            area.append(QPoint(x, y))
        area.append(QPoint(line_points[-1][0], zero_y))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(area_color)
        painter.drawPolygon(area)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(line_color, 2))
        for i in range(1, len(line_points)):
            painter.drawLine(line_points[i - 1][0], line_points[i - 1][1], line_points[i][0], line_points[i][1])

        last_x, last_y = line_points[-1]
        painter.setPen(Qt.PenStyle.NoPen)
        glow = QRadialGradient(last_x, last_y, 14)
        glow.setColorAt(0.0, QColor(line_color.red(), line_color.green(), line_color.blue(), 180))
        glow.setColorAt(1.0, QColor(line_color.red(), line_color.green(), line_color.blue(), 0))
        painter.setBrush(glow)
        painter.drawEllipse(last_x - 14, last_y - 14, 28, 28)
        painter.setBrush(line_color)
        painter.drawEllipse(last_x - 4, last_y - 4, 8, 8)

        # Маркеры закрытых сделок
        marker_index = {str(point.get("time")): visible_offset + i for i, point in enumerate(bucketed)}
        for marker in self.markers[-200:]:
            idx = marker_index.get(str(marker.get("bucket_time")))
            if idx is None or idx < 0 or idx >= len(line_points):
                continue
            x, y = line_points[idx]
            pnl = float(marker.get("pnl", 0.0))
            color = pos_color if pnl >= 0 else neg_color
            painter.setBrush(color)
            painter.drawEllipse(x - 2, y - 9, 4, 4)

        # Нижние подписи X
        painter.setPen(muted_color)
        if bucketed:
            raw_indices = [0, len(bucketed) // 2, len(bucketed) - 1]
            show_indices = []
            for raw_idx in raw_indices:
                shifted_idx = visible_offset + raw_idx
                if 0 <= shifted_idx < len(line_points):
                    show_indices.append((shifted_idx, raw_idx))
            for shifted_idx, raw_idx in show_indices:
                x = line_points[shifted_idx][0]
                label = str(bucketed[raw_idx].get("time", "—"))
                painter.drawText(x - 22, plot.bottom() + 16, label)
