from datetime import datetime
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QCheckBox, QPlainTextEdit, QFileDialog
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import QFont, QTextCursor, QColor, QTextCharFormat


class DebugPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._auto_scroll = True
        self._hide_rtp = False

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        header = QWidget()
        header.setObjectName("panelTitleBar")
        header.setFixedHeight(32)
        header_layout = QHBoxLayout(header)
        header_layout.setContentsMargins(8, 4, 8, 4)

        title = QLabel("调试信息")
        title.setObjectName("panelTitle")

        self.auto_scroll_cb = QCheckBox("自动滚动")
        self.auto_scroll_cb.setChecked(True)
        self.auto_scroll_cb.toggled.connect(self._on_auto_scroll)

        self.hide_rtp_cb = QCheckBox("隐藏RTP")
        self.hide_rtp_cb.setChecked(False)
        self.hide_rtp_cb.toggled.connect(self._on_hide_rtp)

        self.clear_btn = QPushButton("清空")
        self.clear_btn.setObjectName("toolButton")
        self.clear_btn.clicked.connect(self.clear)

        self.export_btn = QPushButton("导出")
        self.export_btn.setObjectName("toolButton")
        self.export_btn.clicked.connect(self._export)

        header_layout.addWidget(title)
        header_layout.addStretch()
        header_layout.addWidget(self.auto_scroll_cb)
        header_layout.addWidget(self.hide_rtp_cb)
        header_layout.addWidget(self.clear_btn)
        header_layout.addWidget(self.export_btn)

        self.text_edit = QPlainTextEdit()
        self.text_edit.setReadOnly(True)
        self.text_edit.setObjectName("debugText")
        font = QFont("Consolas", 11)
        font.setStyleHint(QFont.StyleHint.Monospace)
        if not font.exactMatch():
            font = QFont("Courier New", 11)
            font.setStyleHint(QFont.StyleHint.Monospace)
        self.text_edit.setFont(font)
        self.text_edit.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)

        layout.addWidget(header)
        layout.addWidget(self.text_edit, 1)

    def _on_auto_scroll(self, checked: bool):
        self._auto_scroll = checked

    def _on_hide_rtp(self, checked: bool):
        self._hide_rtp = checked

    def append_debug(self, direction: str, message: str):
        if self._hide_rtp and "[RTP" in message:
            return
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        time_fmt = QTextCharFormat()
        time_fmt.setForeground(QColor("#6c7086"))

        dir_fmt = QTextCharFormat()
        if direction == "->":
            dir_fmt.setForeground(QColor("#5b9cf5"))
        elif direction == "<-":
            dir_fmt.setForeground(QColor("#46d4a3"))
        elif "error" in message.lower() or "fail" in message.lower():
            dir_fmt.setForeground(QColor("#f05060"))
        else:
            dir_fmt.setForeground(QColor("#f0c060"))

        msg_fmt = QTextCharFormat()
        msg_fmt.setForeground(QColor("#cdd6f4"))

        cursor.insertText(f"{now}  ", time_fmt)
        cursor.insertText(f"{direction}  ", dir_fmt)
        cursor.insertText(f"{message}\n", msg_fmt)

        cursor.insertText("─" * 80 + "\n", time_fmt)

        if self._auto_scroll:
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def append_info(self, message: str):
        self.append_debug("--", message)

    def append_error(self, message: str):
        cursor = self.text_edit.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        now = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        time_fmt = QTextCharFormat()
        time_fmt.setForeground(QColor("#6c7086"))

        err_fmt = QTextCharFormat()
        err_fmt.setForeground(QColor("#f05060"))

        cursor.insertText(f"{now}  ", time_fmt)
        cursor.insertText(f"!!  {message}\n", err_fmt)
        cursor.insertText("─" * 80 + "\n", time_fmt)

        if self._auto_scroll:
            self.text_edit.setTextCursor(cursor)
            self.text_edit.ensureCursorVisible()

    def clear(self):
        self.text_edit.clear()

    def _export(self):
        filepath, _ = QFileDialog.getSaveFileName(
            self, "导出调试信息", "debug_log.txt", "Text Files (*.txt);;All Files (*)"
        )
        if filepath:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(self.text_edit.toPlainText())
