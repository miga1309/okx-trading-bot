from app.runtime_support import *

class AnalysisExportDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle('Сдать анализы')
        self.setModal(True)
        self.setMinimumSize(420, 260)
        self.selected_mode = ''
        self.setStyleSheet(
            "QDialog { background:#07111f; color:#e6ecff; }"
            "QLabel#title { color:#8cf6ff; font-size:18px; font-weight:900; }"
            "QLabel#subtitle { color:#a9c6e8; font-size:11px; }"
            "QPushButton.modeBtn { text-align:left; padding:14px 16px; border-radius:14px; background:#0b1628; border:1px solid #24548d; color:#f8fafc; font-weight:800; }"
            "QPushButton.modeBtn:hover { border:1px solid #67e8f9; background:#13213a; }"
            "QPushButton.secondary { padding:8px 12px; border-radius:12px; background:#0b1628; border:1px solid #24548d; color:#f8fafc; font-weight:700; }"
        )
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(10)
        lbl_title = QLabel('Сдать анализы')
        lbl_title.setObjectName('title')
        layout.addWidget(lbl_title)
        lbl_sub = QLabel('Экспорт данных текущего запуска бота для анализа')
        lbl_sub.setObjectName('subtitle')
        layout.addWidget(lbl_sub)
        buttons = [
            ('quick', 'Быстрый отчёт', 'Короткая сводка по текущему запуску'),
            ('full', 'Глубокий разбор', 'Полный диагностический экспорт одним архивом'),
            ('hourly', 'Ночной разбор (по часам)', 'Полный экспорт с разбивкой по 1 часу'),
        ]
        for mode, title, hint in buttons:
            btn = QPushButton(f'{title}\n{hint}')
            btn.setProperty('class', 'modeBtn')
            btn.setProperty('className', 'modeBtn')
            btn.setObjectName('modeBtn')
            btn.setMinimumHeight(54)
            btn.clicked.connect(lambda _=False, m=mode: self._select(m))
            btn.setStyleSheet('text-align:left; padding:14px 16px; border-radius:14px; background:#0b1628; border:1px solid #24548d; color:#f8fafc; font-weight:800;')
            layout.addWidget(btn)
        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.btn_open = QPushButton('Открыть папку экспорта')
        self.btn_open.setProperty('class', 'secondary')
        self.btn_close = QPushButton('Закрыть')
        self.btn_close.setProperty('class', 'secondary')
        self.btn_close.clicked.connect(self.reject)
        bottom.addWidget(self.btn_open)
        bottom.addWidget(self.btn_close)
        layout.addStretch(1)
        layout.addLayout(bottom)

    def _select(self, mode: str):
        self.selected_mode = mode
        self.accept()
