from app.runtime_support_parts.base import *

def is_hidden_instrument(inst_id: object) -> bool:
    value = str(inst_id or "").upper()
    return value in HIDDEN_INSTRUMENTS or any(value.startswith(prefix) for prefix in HIDDEN_PREFIXES)

ENTRY_CONTEXT_DIR = LOG_DIR / "entry_context"
ENTRY_CONTEXT_DIR.mkdir(exist_ok=True)
TRADE_CONTEXT_DIR = LOG_DIR / "trade_context"
TRADE_CONTEXT_DIR.mkdir(exist_ok=True)


TIMEFRAME_TO_SECONDS = {
    "1m": 60,
    "5m": 300,
    "15m": 900,
    "30m": 1800,
    "1H": 3600,
    "1D": 86400,
}

TIMEFRAME_LABELS = {
    "1m": "1 минута",
    "5m": "5 минут",
    "15m": "15 минут",
    "30m": "30 минут",
    "1H": "1 час",
    "1D": "1 день",
}


def format_clock(value: Optional[float]) -> str:
    if not value:
        return "—"
    try:
        return datetime.fromtimestamp(value).strftime("%H:%M:%S")
    except Exception:
        return "—"


def format_time_string(value: object) -> str:
    text = str(value or "").strip()
    if not text:
        return "—"
    for fmt in ("%Y-%m-%d %H:%M:%S", "%H:%M:%S", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(text, fmt).strftime("%H:%M:%S")
        except ValueError:
            continue
    if " " in text:
        tail = text.split(" ")[-1]
        if len(tail) >= 8:
            return tail[:8]
    if "T" in text:
        tail = text.split("T")[-1]
        if len(tail) >= 8:
            return tail[:8]
    return text[:8]




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


def gradient_pnl_color(pnl_pct: float) -> QColor:
    if pnl_pct >= 10:
        return QColor(10, 120, 40)
    if pnl_pct >= 5:
        return QColor(20, 145, 55)
    if pnl_pct > 2:
        return QColor(40, 165, 70)
    if pnl_pct > 0:
        return QColor(85, 180, 95)
    if pnl_pct <= -10:
        return QColor(150, 20, 20)
    if pnl_pct <= -5:
        return QColor(176, 35, 35)
    if pnl_pct < -2:
        return QColor(200, 60, 60)
    if pnl_pct < 0:
        return QColor(220, 95, 95)
    return QColor(255, 255, 255)



def detect_is_dark_theme(app: QApplication) -> bool:
    palette = app.palette()
    window = palette.color(QPalette.ColorRole.Window)
    text = palette.color(QPalette.ColorRole.WindowText)
    return window.lightness() < text.lightness()


def build_app_stylesheet(is_dark: bool) -> str:
    if is_dark:
        return """
            QMainWindow, QWidget {
                background: #050816;
                color: #e6ecff;
                font-family: Segoe UI, Inter, Arial;
            }
            QFrame#CyberHeader {
                background: qlineargradient(x1:0, y1:0, x2:1, y2:0, stop:0 #081326, stop:0.38 #14103a, stop:0.7 #1d0b35, stop:1 #071f36);
                border: 1px solid #3b82f6;
                border-radius: 22px;
            }
            QLabel#CyberHeaderTitle {
                color: #edf6ff;
                font-size: 22px;
                font-weight: 900;
                letter-spacing: 2px;
                padding: 2px 8px 0 8px;
            }
            QLabel[chip="true"] {
                background: #08111f;
                border: 1px solid #1d4ed8;
                border-radius: 16px;
                color: #87f4ff;
                font-size: 12px;
                font-weight: 800;
                padding: 7px 12px;
                min-height: 20px;
            }
            QLabel[syschip="true"] {
                background: rgba(6, 14, 28, 0.82);
                border: 1px solid #21456f;
                border-radius: 14px;
                color: #d8f6ff;
                font-size: 11px;
                font-weight: 800;
                padding: 5px 10px;
            }
            QGroupBox {
                font-weight: 800;
                color: #70e1ff;
                border: none;
                border-radius: 18px;
                margin-top: 18px;
                padding-top: 18px;
                background: transparent;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 14px;
                padding: 0 10px;
                color: #2adfff;
                background: transparent;
                font-size: 12px;
                font-weight: 900;
                text-transform: uppercase;
            }
            QLabel {
                color: #e6ecff;
                background: transparent;
            }
            QLabel[card="true"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #091321, stop:1 #0b1424);
                color: #eef6ff;
                border: 1px solid #1b3b63;
                border-radius: 16px;
                padding: 10px 12px;
            }
            QLabel[radarBadge="true"] {
                background: rgba(5, 19, 33, 0.88);
                color: #7dd3fc;
                border: 1px solid #21456f;
                border-radius: 12px;
                padding: 4px 8px;
                font-size: 10px;
                font-weight: 900;
                letter-spacing: 1px;
            }
            QLabel[metricTitle="true"] {
                color: #7dd3fc;
                font-size: 11px;
                font-weight: 900;
                letter-spacing: 1px;
                text-transform: uppercase;
            }
            QLabel[metricValue="true"] {
                color: #f8fafc;
                font-size: 24px;
                font-weight: 900;
            }
            QLabel[heroValue="true"] {
                color: #8cf6ff;
                font-size: 38px;
                font-weight: 900;
            }
            QComboBox, QLineEdit, QTextEdit, QDoubleSpinBox, QSpinBox, QTableView, QTableWidget {
                background: #08111f;
                color: #f8fafc;
                border: 1px solid #1b3b63;
                border-radius: 12px;
                selection-background-color: #ff3dd1;
                selection-color: #ffffff;
            }
            QComboBox {
                padding: 8px 34px 8px 12px;
                min-height: 18px;
                border: 1px solid #27548e;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1,stop:0 #08111f, stop:1 #101a2d);
                font-weight: 800;
            }
            QComboBox:hover {
                border: 1px solid #67e8f9;
            }
            QComboBox:focus {
                border: 1px solid #00ffa8;
            }
            QComboBox::drop-down {
                subcontrol-origin: padding;
                subcontrol-position: top right;
                width: 28px;
                border-left: 1px solid #1b3b63;
                background: rgba(12, 26, 48, 0.85);
                border-top-right-radius: 12px;
                border-bottom-right-radius: 12px;
            }
            QComboBox::down-arrow {
                width: 0px;
                height: 0px;
                border-left: 6px solid transparent;
                border-right: 6px solid transparent;
                border-top: 8px solid #67e8f9;
                margin-right: 8px;
            }
            QComboBox QAbstractItemView {
                background: #08111f;
                color: #e6ecff;
                border: 1px solid #27548e;
                border-radius: 12px;
                padding: 6px;
                selection-background-color: #10213d;
                selection-color: #00ffa8;
                outline: 0;
            }
            QScrollBar:vertical {
                background: rgba(8, 17, 31, 0.85);
                width: 12px;
                margin: 8px 2px 8px 2px;
                border: none;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #67e8f9, stop:1 #00ffa8);
                min-height: 28px;
                border-radius: 6px;
            }
            QScrollBar::handle:vertical:hover {
                background: qlineargradient(x1:0,y1:0,x2:0,y2:1, stop:0 #8cf6ff, stop:1 #24ffb3);
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
                height: 0px;
                border: none;
            }
            QTextEdit#ActivityFeed {
                background: #060d18;
                border: 1px solid #1c325a;
                color: #8be9fd;
                border-radius: 16px;
            }
            QHeaderView::section {
                background: #101a2d;
                color: #8be9fd;
                border: 1px solid #1c325a;
                padding: 9px;
                font-weight: 800;
            }
            QTabWidget::pane {
                border: 1px solid #1c325a;
                background: #08111f;
                border-radius: 14px;
                top: -1px;
            }
            QTabBar::tab {
                background: #091221;
                color: #93a7c7;
                border: 1px solid #1c325a;
                border-bottom: none;
                padding: 11px 18px;
                margin-right: 4px;
                border-top-left-radius: 12px;
                border-top-right-radius: 12px;
                font-weight: 800;
            }
            QTabBar::tab:selected {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #10213d, stop:1 #1a1240);
                color: #67e8f9;
                border-color: #8b5cf6;
            }
            QPushButton {
                padding: 9px 14px;
                border-radius: 12px;
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #0d1730, stop:1 #111d36);
                color: #f8fafc;
                border: 1px solid #26558f;
                font-weight: 800;
            }
            QPushButton:hover {
                background: #18274a;
                border-color: #67e8f9;
            }
            QFrame#MarketPulseTile {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:1, stop:0 #08111f, stop:1 #10152c);
                border: 1px solid #274986;
                border-radius: 18px;
            }
            QPushButton#toggleBotButton[running="true"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #4c0519, stop:1 #7f1d1d);
                border: 1px solid #ef4444;
                color: #ffffff;
            }
            QPushButton#toggleBotButton[running="false"] {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #03251d, stop:1 #064e3b);
                border: 1px solid #10b981;
                color: #ffffff;
            }
        """
    return """
        QMainWindow, QWidget { background: #f5f7fb; color: #111827; }
    """





class NeonPanel(QGroupBox):
    def __init__(self, title="", parent=None):
        super().__init__(title, parent)
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(55)

    def _tick(self):
        self._pulse = (self._pulse + 0.08) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 12, -1, -1)
        pulse = (math.sin(self._pulse) + 1.0) * 0.5

        bg = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg.setColorAt(0.0, QColor(7, 16, 31, 236))
        bg.setColorAt(0.58, QColor(6, 12, 24, 238))
        bg.setColorAt(1.0, QColor(8, 18, 34, 236))
        painter.setBrush(bg)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(rect, 18, 18)

        border_grad = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        border_grad.setColorAt(0.0, QColor(0, 224, 255, 180))
        border_grad.setColorAt(0.48, QColor(89, 115, 255, 125))
        border_grad.setColorAt(1.0, QColor(255, 61, 209, 170))
        for width, alpha in ((6, 20), (3, 38)):
            glow = QPen(QColor(0, 224, 255, alpha), width)
            painter.setPen(glow)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 18, 18)
        painter.setPen(QPen(QBrush(border_grad), 1.4))
        painter.drawRoundedRect(rect, 18, 18)

        corner = QColor(0, 238, 255, int(170 + pulse * 50))
        accent = QColor(255, 61, 209, int(120 + pulse * 55))
        painter.setPen(QPen(corner, 2))
        span = 26
        # top-left
        painter.drawLine(rect.left()+10, rect.top()+1, rect.left()+span, rect.top()+1)
        painter.drawLine(rect.left()+1, rect.top()+10, rect.left()+1, rect.top()+span)
        # top-right
        painter.drawLine(rect.right()-span, rect.top()+1, rect.right()-10, rect.top()+1)
        painter.drawLine(rect.right()-1, rect.top()+10, rect.right()-1, rect.top()+span)
        painter.setPen(QPen(accent, 2))
        # bottom-left
        painter.drawLine(rect.left()+1, rect.bottom()-span, rect.left()+1, rect.bottom()-10)
        painter.drawLine(rect.left()+10, rect.bottom()-1, rect.left()+span, rect.bottom()-1)
        # bottom-right
        painter.drawLine(rect.right()-span, rect.bottom()-1, rect.right()-10, rect.bottom()-1)
        painter.drawLine(rect.right()-1, rect.bottom()-span, rect.right()-1, rect.bottom()-10)

        title_rect = QRect(rect.left()+14, 0, max(180, min(rect.width()-28, 220)), 24)
        title_bg = QLinearGradient(title_rect.left(), title_rect.top(), title_rect.right(), title_rect.bottom())
        title_bg.setColorAt(0.0, QColor(4, 19, 38, 220))
        title_bg.setColorAt(1.0, QColor(15, 17, 43, 180))
        painter.setBrush(title_bg)
        painter.setPen(QPen(QColor(0, 224, 255, 120), 1))
        painter.drawRoundedRect(title_rect, 8, 8)
        painter.setPen(QColor(64, 227, 255))
        font = painter.font()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        painter.drawText(title_rect.adjusted(12,0,-12,0), int(Qt.AlignmentFlag.AlignVCenter|Qt.AlignmentFlag.AlignLeft), self.title().upper())


class AnimatedGridWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._phase = 0.0
        self._pulse = 0.0
        self._particle_phase = 0.0
        self.mode = "idle"
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(33)

    def set_mode(self, mode: str):
        self.mode = str(mode or "idle").lower()
        self.update()

    def _tick(self):
        self._phase = (self._phase + 1.6) % 64.0
        self._pulse = (self._pulse + 0.09) % (math.pi * 2.0)
        self._particle_phase = (self._particle_phase + 0.012) % 1.0
        self.update()

    def _mode_colors(self):
        if self.mode == "alert":
            return QColor(255, 77, 109, 50), QColor(255, 166, 0, 42)
        if self.mode == "trading":
            return QColor(0, 255, 163, 40), QColor(0, 224, 255, 36)
        return QColor(0, 224, 255, 24), QColor(255, 61, 209, 22)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect()

        bg = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg.setColorAt(0.0, QColor(3, 8, 20))
        bg.setColorAt(0.35, QColor(8, 11, 30))
        bg.setColorAt(0.68, QColor(20, 9, 38))
        bg.setColorAt(1.0, QColor(4, 23, 38))
        painter.fillRect(rect, bg)

        pulse = (math.sin(self._pulse) + 1.0) * 0.5
        grid_minor = QColor(40, 86, 150, int(26 + 12 * pulse))
        grid_major = QColor(30, 224, 255, int(30 + 20 * pulse))
        painter.setPen(QPen(grid_minor, 1))
        step = 28
        phase = int(self._phase)
        for x in range(-step, rect.width() + step, step):
            painter.drawLine(x + phase, 0, x + phase, rect.height())
        for y in range(-step, rect.height() + step, step):
            painter.drawLine(0, y + phase // 2, rect.width(), y + phase // 2)

        painter.setPen(QPen(grid_major, 1))
        major = step * 4
        for x in range(-major, rect.width() + major, major):
            painter.drawLine(x + phase, 0, x + phase, rect.height())
        for y in range(-major, rect.height() + major, major):
            painter.drawLine(0, y + phase // 2, rect.width(), y + phase // 2)

        c1, c2 = self._mode_colors()
        glow = QRadialGradient(QPointF(rect.width() * 0.72, rect.height() * 0.12), max(rect.width(), rect.height()) * 0.55)
        glow.setColorAt(0.0, c2)
        glow.setColorAt(0.35, c1)
        glow.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect, glow)

        painter.setPen(QPen(QColor(0, 224, 255, 22), 2))
        paths = [
            [QPointF(rect.width()*0.12, rect.height()*0.30), QPointF(rect.width()*0.38, rect.height()*0.30), QPointF(rect.width()*0.52, rect.height()*0.54), QPointF(rect.width()*0.84, rect.height()*0.54)],
            [QPointF(rect.width()*0.10, rect.height()*0.74), QPointF(rect.width()*0.36, rect.height()*0.74), QPointF(rect.width()*0.52, rect.height()*0.54), QPointF(rect.width()*0.87, rect.height()*0.86)],
        ]
        for pts in paths:
            for a,b in zip(pts, pts[1:]):
                painter.drawLine(a,b)
            for idx,(a,b) in enumerate(zip(pts, pts[1:])):
                t=(self._particle_phase*1.35+idx*0.21)%1.0
                x=a.x()+(b.x()-a.x())*t
                y=a.y()+(b.y()-a.y())*t
                color=QColor(0,255,163,190) if self.mode!="alert" else QColor(255,77,109,190)
                painter.setPen(Qt.PenStyle.NoPen)
                painter.setBrush(color)
                painter.drawEllipse(QPointF(x,y), 3.5, 3.5)

        vignette = QRadialGradient(QPointF(rect.center()), max(rect.width(), rect.height()) * 0.82)
        vignette.setColorAt(0.72, QColor(0, 0, 0, 0))
        vignette.setColorAt(1.0, QColor(0, 0, 0, 85))
        painter.fillRect(rect, vignette)


class MiniSparklineWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.values = [0.0] * 24
        self.display_values = [0.0] * 24
        self.positive = True
        self._phase = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(40)
        self.setMinimumHeight(42)

    def _animate(self):
        if not self.display_values:
            self.display_values = list(self.values)
        self._phase = (self._phase + 0.18) % (math.pi * 2.0)
        target = self.values or [0.0] * 24
        if len(self.display_values) != len(target):
            self.display_values = list(target)
        else:
            updated = []
            for idx, (cur, tgt) in enumerate(zip(self.display_values, target)):
                drift = math.sin(self._phase + idx * 0.23) * 0.015
                updated.append(cur * 0.84 + tgt * 0.16 + drift)
            self.display_values = updated
        self.update()

    def set_series(self, values, positive=True):
        vals = [float(v) for v in (values or []) if v is not None]
        if not vals:
            vals = [0.0] * 24
        self.values = vals[-24:]
        if not self.display_values or len(self.display_values) != len(self.values):
            self.display_values = list(self.values)
        self.positive = bool(positive)
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(1, 1, -1, -1)
        painter.fillRect(self.rect(), Qt.GlobalColor.transparent)
        values = self.display_values or self.values
        if not values:
            return False
        line_color = QColor(0, 255, 163) if self.positive else QColor(255, 77, 79)
        glow_color = QColor(line_color.red(), line_color.green(), line_color.blue(), 65)
        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v += 1.0
            min_v -= 1.0
        step_x = rect.width() / max(1, len(values) - 1)

        def y_of(v):
            return rect.bottom() - ((v - min_v) / (max_v - min_v)) * rect.height()

        pts = [(rect.left() + i * step_x, y_of(v)) for i, v in enumerate(values)]
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)

        area = QPainterPath(path)
        area.lineTo(rect.right(), rect.bottom())
        area.lineTo(rect.left(), rect.bottom())
        area.closeSubpath()

        grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        grad.setColorAt(0.0, glow_color)
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(area, grad)

        for width, alpha in ((7, 26), (4, 42)):
            painter.setPen(QPen(QColor(line_color.red(), line_color.green(), line_color.blue(), alpha), width))
            painter.drawPath(path)

        painter.setPen(QPen(line_color, 2))
        painter.drawPath(path)
        painter.setBrush(line_color)
        painter.setPen(Qt.PenStyle.NoPen)
        x, y = pts[-1]
        painter.drawEllipse(QPointF(x, y), 3.2, 3.2)


class MarketPulseTile(QFrame):
    def __init__(self, title="SCAN", parent=None):
        super().__init__(parent)
        self.setObjectName("MarketPulseTile")
        self.setMinimumHeight(112)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 10, 12, 10)
        layout.setSpacing(6)

        top = QHBoxLayout()
        top.setContentsMargins(0, 0, 0, 0)
        top.setSpacing(8)
        self.lbl_symbol = QLabel(title)
        self.lbl_symbol.setStyleSheet("font-size: 16px; font-weight: 900; color: #dbeafe;")
        self.lbl_status = QLabel("WATCH")
        self.lbl_status.setProperty("radarBadge", "true")
        top.addWidget(self.lbl_symbol, 1)
        top.addWidget(self.lbl_status, 0)
        layout.addLayout(top)

        mid = QHBoxLayout()
        mid.setContentsMargins(0, 0, 0, 0)
        mid.setSpacing(8)
        self.lbl_change = QLabel("+0.00%")
        self.lbl_change.setStyleSheet("font-size: 18px; font-weight: 900; color: #00ffa3;")
        self.lbl_score = QLabel("Score: 0")
        self.lbl_score.setStyleSheet("font-size: 11px; font-weight: 700; color: #93c5fd;")
        mid.addWidget(self.lbl_change)
        mid.addStretch(1)
        mid.addWidget(self.lbl_score)
        layout.addLayout(mid)

        self.lbl_reason = QLabel("Ожидание валидного сигнала")
        self.lbl_reason.setWordWrap(True)
        self.lbl_reason.setStyleSheet("font-size: 11px; color: #9dd8ff; min-height: 30px;")
        layout.addWidget(self.lbl_reason)

        self.spark = MiniSparklineWidget()
        self.spark.setMinimumHeight(28)
        layout.addWidget(self.spark)

    def set_data(self, symbol: str, change_pct: float, values=None, status: str="WATCH", score: float=0.0, reason: str=""):
        symbol = str(symbol or "SCAN")
        short = symbol.replace("-USDT-SWAP", "").replace("-SWAP", "")
        status_text = str(status or "WATCH").upper()
        self.lbl_symbol.setText(short)
        self.lbl_status.setText(status_text)
        self.lbl_change.setText(f"{float(change_pct or 0.0):+,.2f}%")
        self.lbl_score.setText(f"Score: {float(score or 0.0):.0f}")
        reason_text = str(reason or "Ожидание валидного сигнала").strip()
        self.lbl_reason.setText(reason_text[:82])

        if status_text in {"LONG", "LONG CANDIDATE", "RUNNING"}:
            accent = "#00ffa3"
        elif status_text in {"SHORT", "SHORT CANDIDATE", "FILTERED", "RISK"}:
            accent = "#ff6b8a" if status_text.startswith("SHORT") else "#ffb347"
        else:
            accent = "#7dd3fc"

        self.lbl_status.setStyleSheet(
            f"background: rgba(5, 19, 33, 0.88); color: {accent}; border: 1px solid #21456f; border-radius: 12px; padding: 4px 8px; font-size: 10px; font-weight: 900; letter-spacing: 1px;"
        )
        change_color = "#00ffa3" if float(change_pct or 0.0) >= 0 else "#ff4d6d"
        self.lbl_change.setStyleSheet(f"font-size: 18px; font-weight: 900; color: {change_color};")
        series = values or [float(change_pct or 0.0)] * 18
        self.spark.set_series(series, positive=float(change_pct or 0.0) >= 0)


class GlowBandWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.series_a = [0.0] * 48
        self.series_b = [0.0] * 48
        self._offset = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(55)
        self.setMinimumHeight(28)

    def _animate(self):
        self._offset = (self._offset + 1.8) % 320.0
        self.update()

    def set_series(self, series_a=None, series_b=None):
        a = [float(v) for v in (series_a or []) if v is not None]
        b = [float(v) for v in (series_b or []) if v is not None]
        self.series_a = (a or [0.0] * 48)[-48:]
        self.series_b = (b or [0.0] * 48)[-48:]
        self.update()

    def _draw_line(self, painter, rect, values, line_color):
        if not values:
            return False
        min_v = min(values)
        max_v = max(values)
        if abs(max_v - min_v) < 1e-9:
            max_v += 1.0
            min_v -= 1.0
        step_x = rect.width() / max(1, len(values) - 1)

        def y_of(v):
            return rect.bottom() - ((v - min_v) / (max_v - min_v)) * rect.height()

        pts = [(rect.left() + i * step_x, y_of(v)) for i, v in enumerate(values)]
        path = QPainterPath()
        path.moveTo(pts[0][0], pts[0][1])
        for x, y in pts[1:]:
            path.lineTo(x, y)
        fill = QPainterPath(path)
        fill.lineTo(rect.right(), rect.bottom())
        fill.lineTo(rect.left(), rect.bottom())
        fill.closeSubpath()
        grad = QLinearGradient(rect.left(), rect.top(), rect.left(), rect.bottom())
        grad.setColorAt(0.0, QColor(line_color.red(), line_color.green(), line_color.blue(), 96))
        grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillPath(fill, grad)
        painter.setPen(QPen(QColor(line_color.red(), line_color.green(), line_color.blue(), 40), 6))
        painter.drawPath(path)
        painter.setPen(QPen(line_color, 2))
        painter.drawPath(path)

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = self.rect().adjusted(8, 8, -8, -8)
        bg = QLinearGradient(rect.left(), rect.top(), rect.right(), rect.bottom())
        bg.setColorAt(0.0, QColor(7, 12, 24))
        bg.setColorAt(0.5, QColor(11, 15, 34))
        bg.setColorAt(1.0, QColor(6, 18, 30))
        painter.setBrush(bg)
        painter.setPen(QPen(QColor(47, 80, 147), 1))
        painter.drawRoundedRect(rect, 18, 18)

        scan_grad = QLinearGradient(rect.left() - 140 + self._offset, rect.top(), rect.left() + self._offset, rect.top())
        scan_grad.setColorAt(0.0, QColor(0, 0, 0, 0))
        scan_grad.setColorAt(0.5, QColor(0, 224, 255, 32))
        scan_grad.setColorAt(1.0, QColor(0, 0, 0, 0))
        painter.fillRect(rect.adjusted(1, 1, -1, -1), scan_grad)

        plot = rect.adjusted(12, 10, -12, -14)
        painter.setPen(QPen(QColor(39, 57, 88), 1, Qt.PenStyle.DashLine))
        for frac in (0.2, 0.5, 0.8):
            y = int(plot.top() + plot.height() * frac)
            painter.drawLine(plot.left(), y, plot.right(), y)
        self._draw_line(painter, plot, self.series_a, QColor(255, 61, 209))
        self._draw_line(painter, plot, self.series_b, QColor(0, 224, 255))
        painter.setPen(QColor(125, 211, 252))
        painter.drawText(rect.adjusted(16, 6, -16, -6), int(Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignLeft), 'NEON FLOW BAND')
