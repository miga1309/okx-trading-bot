from app.runtime_support import *

class NeonRadarWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(180, 180)
        self._angle = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(35)

    def _animate(self):
        self._angle = (self._angle + 2.5) % 360.0
        self._pulse = (self._pulse + 0.11) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        rect = self.rect().adjusted(10, 10, -10, -10)
        center = QPointF(rect.center())
        radius = min(rect.width(), rect.height()) / 2
        painter.fillRect(self.rect(), QColor(0, 0, 0, 0))

        pulse = (math.sin(self._pulse) + 1.0) * 0.5
        for i, alpha in enumerate((120, 92, 66, 40)):
            r = radius * (1.0 - i * 0.18)
            grad = QRadialGradient(center, r)
            grad.setColorAt(0.0, QColor(70, 255, 231, alpha // 2))
            grad.setColorAt(0.55, QColor(54, 110, 255, alpha))
            grad.setColorAt(1.0, QColor(255, 67, 214, 0))
            painter.setBrush(QBrush(grad))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(center, int(r), int(r))

        painter.setBrush(Qt.BrushStyle.NoBrush)
        for frac, color, w in ((1.00, QColor(65, 185, 255, 130), 2), (0.78, QColor(0, 255, 191, 120), 1), (0.56, QColor(255, 67, 214, 120), 1), (0.34, QColor(105, 245, 255, 120), 1)):
            r = radius * frac
            painter.setPen(QPen(color, w))
            painter.drawEllipse(center, int(r), int(r))

        painter.setPen(QPen(QColor(77, 170, 255, 70), 1))
        for angle in range(0, 360, 30):
            rad = math.radians(angle)
            x2 = center.x() + math.cos(rad) * radius
            y2 = center.y() + math.sin(rad) * radius
            painter.drawLine(center, QPointF(x2, y2))

        sweep_angle = math.radians(self._angle)
        sweep = QPolygon([
            QPoint(int(center.x()), int(center.y())),
            QPoint(int(center.x() + math.cos(sweep_angle - 0.20) * radius), int(center.y() + math.sin(sweep_angle - 0.20) * radius)),
            QPoint(int(center.x() + math.cos(sweep_angle + 0.20) * radius), int(center.y() + math.sin(sweep_angle + 0.20) * radius)),
        ])
        sweep_grad = QRadialGradient(center, radius)
        sweep_grad.setColorAt(0.0, QColor(0, 255, 191, int(48 + 30 * pulse)))
        sweep_grad.setColorAt(1.0, QColor(0, 255, 191, 0))
        painter.setBrush(QBrush(sweep_grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawPolygon(sweep)

        painter.setPen(QPen(QColor(19, 255, 175, 170), 2))
        dynamic_angles = (
            (26 + self._angle * 0.35, 0.88),
            (141 + self._angle * 0.22, 0.62),
            (224 + self._angle * 0.18, 0.48),
        )
        for angle, frac in dynamic_angles:
            rad = math.radians(angle % 360.0)
            x2 = center.x() + math.cos(rad) * radius * frac
            y2 = center.y() + math.sin(rad) * radius * frac
            painter.drawLine(center, QPointF(x2, y2))
            painter.setBrush(QColor(19, 255, 175, 220))
            painter.setPen(Qt.PenStyle.NoPen)
            painter.drawEllipse(QPoint(int(x2), int(y2)), 5, 5)
            painter.setPen(QPen(QColor(19, 255, 175, 170), 2))

        painter.setBrush(QColor(255, 67, 214, 190))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 7, 7)


class NeonGlyphWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(150, 150)
        self._angle = 0.0
        self._pulse = 0.0
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._animate)
        self._timer.start(40)

    def _animate(self):
        self._angle = (self._angle + 1.8) % 360.0
        self._pulse = (self._pulse + 0.12) % (math.pi * 2.0)
        self.update()

    def paintEvent(self, event) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        outer = self.rect().adjusted(8, 8, -8, -8)
        center = QPointF(outer.center())
        radius = min(outer.width(), outer.height()) / 2
        pulse = (math.sin(self._pulse) + 1.0) * 0.5

        grad = QRadialGradient(center, radius)
        grad.setColorAt(0.0, QColor(0, 231, 255, int(65 + pulse * 24)))
        grad.setColorAt(0.45, QColor(23, 96, 255, 108))
        grad.setColorAt(0.78, QColor(255, 67, 214, 48))
        grad.setColorAt(1.0, QColor(255, 67, 214, 0))
        painter.setBrush(QBrush(grad))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawRoundedRect(outer, 28, 28)

        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.setPen(QPen(QColor(76, 227, 255, 190), 2))
        painter.drawEllipse(center, int(radius * 0.74), int(radius * 0.74))
        painter.setPen(QPen(QColor(255, 67, 214, 150), 2))
        painter.drawEllipse(center, int(radius * 0.52), int(radius * 0.52))

        painter.save()
        painter.translate(center)
        painter.rotate(self._angle)
        painter.setPen(QPen(QColor(88, 157, 255, 150), 1))
        for angle in range(0, 360, 45):
            rad = math.radians(angle)
            x1 = math.cos(rad) * radius * 0.20
            y1 = math.sin(rad) * radius * 0.20
            x2 = math.cos(rad) * radius * 0.88
            y2 = math.sin(rad) * radius * 0.88
            painter.drawLine(QPointF(x1, y1), QPointF(x2, y2))
        painter.restore()

        shell = QPainterPath()
        shell.addEllipse(QPointF(center.x(), center.y()+radius*0.02), radius*0.32, radius*0.24)
        painter.setPen(QPen(QColor(0, 242, 255, 220), 2))
        painter.drawPath(shell)

        painter.setPen(QPen(QColor(0, 242, 255, 210), 2))
        painter.drawArc(int(center.x()-radius*0.22), int(center.y()-radius*0.10), int(radius*0.44), int(radius*0.32), 30*16, 120*16)
        painter.drawArc(int(center.x()-radius*0.18), int(center.y()-radius*0.02), int(radius*0.36), int(radius*0.22), 210*16, 120*16)
        painter.drawArc(int(center.x()-radius*0.14), int(center.y()-radius*0.11), int(radius*0.28), int(radius*0.20), 330*16, 120*16)

        painter.setPen(QPen(QColor(255, 67, 214, 190), 2))
        head = QPainterPath()
        head.addEllipse(QPointF(center.x(), center.y()-radius*0.30), radius*0.11, radius*0.08)
        painter.drawPath(head)
        painter.drawLine(QPointF(center.x(), center.y()-radius*0.23), QPointF(center.x(), center.y()-radius*0.08))
        for dx,dy in ((-0.23,-0.02),(0.23,-0.02),(-0.18,0.22),(0.18,0.22)):
            painter.drawLine(QPointF(center.x()+radius*(dx*0.6), center.y()+radius*(dy*0.6)), QPointF(center.x()+radius*dx, center.y()+radius*dy))

        painter.setBrush(QColor(0, 242, 255, int(160 + pulse * 50)))
        painter.setPen(Qt.PenStyle.NoPen)
        painter.drawEllipse(center, 8, 8)
