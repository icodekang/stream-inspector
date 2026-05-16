import json
import os
from PyQt6.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QComboBox, QPushButton,
                              QLabel, QDialog, QListWidget, QListWidgetItem, QLineEdit,
                              QDialogButtonBox, QMessageBox)
from PyQt6.QtCore import Qt, pyqtSignal
from ..protocol.factory import PROTOCOL_MAP, get_protocol_name


CONFIG_DIR = os.path.join(os.path.expanduser("~"), ".stream-inspector")
CONFIG_FILE = os.path.join(CONFIG_DIR, "addresses.json")


def _load_addresses() -> list[str]:
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("addresses", [])
    except Exception:
        pass
    return []


def _save_addresses(addresses: list[str]):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump({"addresses": list(addresses)}, f, indent=2)


class ControlBar(QWidget):
    connect_clicked = pyqtSignal(str)
    disconnect_clicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self._addresses = _load_addresses()
        self._setup_ui()
        self._connected = False

    def _setup_ui(self):
        self.setObjectName("controlBar")
        self.setFixedHeight(90)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(6)

        addr_layout = QHBoxLayout()
        addr_layout.setSpacing(8)

        addr_label = QLabel("取流地址:")
        addr_label.setObjectName("controlLabel")
        addr_label.setFixedWidth(60)

        self.addr_combo = QComboBox()
        self.addr_combo.setObjectName("addrCombo")
        self.addr_combo.setEditable(True)
        self.addr_combo.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)
        self.addr_combo.setMinimumWidth(400)
        self._refresh_combo()

        self.addr_combo.currentTextChanged.connect(self._on_address_changed)

        self.add_btn = QPushButton("+ 添加")
        self.add_btn.setObjectName("addButton")
        self.add_btn.clicked.connect(self._open_manager)

        addr_layout.addWidget(addr_label)
        addr_layout.addWidget(self.addr_combo, 1)
        addr_layout.addWidget(self.add_btn)

        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(12)

        self.protocol_label = QLabel("协议: 自动识别")
        self.protocol_label.setObjectName("protocolLabel")

        self.status_indicator = QLabel("●")
        self.status_indicator.setObjectName("statusDot")
        self.status_text = QLabel("未连接")
        self.status_text.setObjectName("statusText")

        bottom_layout.addWidget(self.protocol_label)
        bottom_layout.addStretch()

        self.connect_btn = QPushButton("▶ 连接")
        self.connect_btn.setObjectName("connectButton")
        self.connect_btn.clicked.connect(self._on_connect)

        self.disconnect_btn = QPushButton("■ 断开")
        self.disconnect_btn.setObjectName("disconnectButton")
        self.disconnect_btn.clicked.connect(self._on_disconnect)
        self.disconnect_btn.setVisible(False)

        bottom_layout.addWidget(self.status_indicator)
        bottom_layout.addWidget(self.status_text)
        bottom_layout.addSpacing(16)
        bottom_layout.addWidget(self.connect_btn)
        bottom_layout.addWidget(self.disconnect_btn)

        layout.addLayout(addr_layout)
        layout.addLayout(bottom_layout)

    def _refresh_combo(self):
        current = self.addr_combo.currentText()
        self.addr_combo.blockSignals(True)
        self.addr_combo.clear()
        for addr in self._addresses:
            self.addr_combo.addItem(addr)
        if current:
            idx = self.addr_combo.findText(current)
            if idx >= 0:
                self.addr_combo.setCurrentIndex(idx)
            else:
                self.addr_combo.setCurrentText(current)
        self.addr_combo.blockSignals(False)

    def _on_address_changed(self, text: str):
        if "://" in text:
            scheme = text.split("://")[0].lower()
            if scheme in PROTOCOL_MAP:
                name = get_protocol_name(scheme)
                self.protocol_label.setText(f"协议: {name}")
            else:
                self.protocol_label.setText(f"协议: 未知 ({scheme})")
        else:
            self.protocol_label.setText("协议: 自动识别")

    def _open_manager(self):
        current = self.addr_combo.currentText().strip()
        dialog = AddressManagerDialog(self._addresses, current, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._addresses = dialog.get_addresses()
            _save_addresses(self._addresses)
            self._refresh_combo()

    def _on_connect(self):
        url = self.addr_combo.currentText().strip()
        if not url:
            QMessageBox.warning(self, "地址为空", "请输入取流地址")
            return
        if "://" not in url:
            QMessageBox.warning(self, "格式错误", "请输入完整URL，如 rtsp://192.168.1.100:554/stream")
            return
        scheme = url.split("://")[0].lower()
        if scheme not in PROTOCOL_MAP:
            QMessageBox.warning(self, "不支持的协议", f"协议 '{scheme}' 当前不支持。")
            return
        self.connect_clicked.emit(url)

    def _on_disconnect(self):
        self.disconnect_clicked.emit()

    def set_connecting(self):
        self._connected = False
        self.connect_btn.setVisible(False)
        self.disconnect_btn.setVisible(True)
        self.addr_combo.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.status_text.setText("连接中...")

    def set_connected(self):
        self._connected = True
        self.connect_btn.setVisible(False)
        self.disconnect_btn.setVisible(True)
        self.addr_combo.setEnabled(False)
        self.add_btn.setEnabled(False)
        self.status_text.setText("已连接")

    def set_disconnected(self):
        self._connected = False
        self.connect_btn.setVisible(True)
        self.disconnect_btn.setVisible(False)
        self.addr_combo.setEnabled(True)
        self.add_btn.setEnabled(True)
        self.status_text.setText("未连接")
        self.protocol_label.setText("协议: 自动识别")

    def current_url(self) -> str:
        return self.addr_combo.currentText().strip()


class AddressManagerDialog(QDialog):
    def __init__(self, addresses: list[str], current: str = "", parent=None):
        super().__init__(parent)
        self._addresses = list(addresses)
        self._current = current
        self._setup_ui()

    def _setup_ui(self):
        self.setWindowTitle("取流地址管理")
        self.setObjectName("addressManagerDialog")
        self.setMinimumSize(520, 360)

        layout = QVBoxLayout(self)
        layout.setSpacing(12)

        self.list_widget = QListWidget()
        self.list_widget.setObjectName("addressList")
        self._refresh_list()

        add_layout = QHBoxLayout()
        self.new_addr_input = QLineEdit()
        self.new_addr_input.setObjectName("addrInput")
        self.new_addr_input.setPlaceholderText("输入新地址，如 rtsp://192.168.1.100:554/stream")
        self.new_addr_input.returnPressed.connect(self._add_item)

        add_item_btn = QPushButton("+ 添加")
        add_item_btn.setObjectName("addButton")
        add_item_btn.clicked.connect(self._add_item)

        add_layout.addWidget(self.new_addr_input, 1)
        add_layout.addWidget(add_item_btn)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok |
                                     QDialogButtonBox.StandardButton.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout.addWidget(self.list_widget, 1)
        layout.addLayout(add_layout)
        layout.addWidget(buttons)

    def _refresh_list(self):
        self.list_widget.clear()
        for addr in self._addresses:
            item = QListWidgetItem(addr)
            item.setToolTip(addr)
            self.list_widget.addItem(item)
        if self._current and self._current not in self._addresses:
            self.new_addr_input.setText(self._current)

    def _add_item(self):
        text = self.new_addr_input.text().strip()
        if text and text not in self._addresses:
            self._addresses.append(text)
            self._refresh_list()
            self.new_addr_input.clear()
        self.new_addr_input.setFocus()

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Delete:
            current = self.list_widget.currentItem()
            if current:
                addr = current.text()
                self._addresses.remove(addr)
                self._refresh_list()
        else:
            super().keyPressEvent(event)

    def get_addresses(self) -> list[str]:
        return self._addresses
