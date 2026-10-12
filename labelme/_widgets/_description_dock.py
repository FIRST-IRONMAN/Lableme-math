from __future__ import annotations

import json
from pathlib import Path

from PySide6 import QtCore, QtWidgets
from PySide6.QtCore import Qt, Signal
from loguru import logger


class ZoomableTextArea(QtWidgets.QScrollArea):
    """Scroll area that supports Ctrl+Wheel font scaling for its child widget."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWidgetResizable(True)

    def wheelEvent(self, event: QtCore.QWheelEvent) -> None:
        if event.modifiers() & Qt.ControlModifier:
            widget = self.widget()
            if isinstance(widget, QtWidgets.QLabel):
                font = widget.font()
                delta = event.angleDelta().y()
                if delta > 0:
                    font.setPointSize(font.pointSize() + 1)
                elif delta < 0:
                    font.setPointSize(max(1, font.pointSize() - 1))
                widget.setFont(font)
                event.accept()
                return
        super().wheelEvent(event)


class DescriptionEditWidget(QtWidgets.QWidget):
    """Double-click editable description display.

    Shows text in a QLabel; double-click switches to QTextEdit for editing.
    Ctrl+Enter or focus-out commits the edit.
    """

    editingFinished = Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._label = QtWidgets.QLabel()
        self._label.setWordWrap(True)
        self._label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        self._label.setStyleSheet("""
            QLabel {
                color: #000000;
                background-color: #ffffff;
                font-family: "Cascadia Code", "Fira Code", "Microsoft YaHei", monospace;
                font-weight: normal;
                border: 1px solid #000000;
                padding: 5px;
                margin: 0px;
            }
        """)
        font = self._label.font()
        font.setPointSize(25)
        self._label.setFont(font)

        self._editor = QtWidgets.QTextEdit()
        self._editor.setStyleSheet(self._label.styleSheet())
        self._editor.setFont(self._label.font())
        self._editor.hide()

        layout.addWidget(self._label)
        layout.addWidget(self._editor)

        self._label.installEventFilter(self)

    def eventFilter(
        self, obj: QtCore.QObject, event: QtCore.QEvent
    ) -> bool:
        if obj is self._label and event.type() == QtCore.QEvent.MouseButtonDblClick:
            self._start_editing()
            return True
        if obj is self._editor and event.type() == QtCore.QEvent.FocusOut:
            self._finish_editing()
            return True
        return super().eventFilter(obj, event)

    def _start_editing(self) -> None:
        self._editor.setPlainText(self._label.text())
        self._label.hide()
        self._editor.show()
        self._editor.setFocus()
        self._editor.installEventFilter(self)
        self._editor.keyPressEvent = self._editor_key_press  # type: ignore[method-assign]

    def _editor_key_press(self, event: QtCore.QKeyEvent) -> None:
        if (
            event.key() == Qt.Key_Return
            and event.modifiers() == Qt.ControlModifier
        ):
            self._finish_editing()
        else:
            QtWidgets.QTextEdit.keyPressEvent(self._editor, event)

    def _finish_editing(self) -> None:
        new_text = self._editor.toPlainText()
        self._label.setText(new_text)
        self._editor.hide()
        self._label.show()
        self.editingFinished.emit(new_text)

    def setText(self, text: str) -> None:
        self._label.setText(text)
        if not self._editor.isHidden():
            self._editor.setPlainText(text)

    def text(self) -> str:
        return self._label.text()


class DescriptionDockWidget(QtWidgets.QDockWidget):
    """Dock widget for displaying and editing per-image description text.

    Reads description from:
      - JSON annotation file (shapes[0].description)
      - or a .txt file with the same base name as the image.

    Emits descriptionChanged when the user edits the text directly.
    """

    descriptionChanged = Signal(str)

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(
            parent.tr("Description") if parent else "Description", parent
        )
        self.setObjectName("Description")

        self._scroll = ZoomableTextArea()
        self._edit_widget = DescriptionEditWidget()
        self._scroll.setWidget(self._edit_widget)
        self._scroll.setWidgetResizable(True)
        self.setWidget(self._scroll)

        self._edit_widget.editingFinished.connect(self._on_description_edited)

        self._apply_style()

    def show_description(self, image_path: str | None) -> None:
        """Load and display description for the given image path."""
        if not image_path:
            logger.debug("show_description: no image path provided")
            self._edit_widget.setText("")
            return

        try:
            base_name, _ext = image_path.rsplit(".", 1)
        except ValueError:
            logger.warning("Unexpected filename format: {}", image_path)
            self._edit_widget.setText("")
            return

        description: str | None = None

        # Try JSON annotation file first
        json_filename = base_name + ".json"
        if self._file_exists(json_filename):
            try:
                with open(json_filename, encoding="utf-8") as f:
                    data = json.load(f)
                description = data.get("shapes", [{}])[0].get("description")
            except Exception:
                description = None

        # Fall back to .txt file
        if description is None:
            txt_filename = base_name + ".txt"
            if self._file_exists(txt_filename):
                try:
                    with open(txt_filename, encoding="utf-8") as f:
                        description = f.read().strip()
                except Exception:
                    description = None

        self._edit_widget.setText(description or "")

    def set_description_text(self, text: str) -> None:
        """Set description text directly (e.g. from a selected shape)."""
        self._edit_widget.setText(text)

    # ---- private -------------------------------------------------------------

    @staticmethod
    def _file_exists(path: str) -> bool:
        import os
        return os.path.exists(path)

    def _on_description_edited(self, new_text: str) -> None:
        self.descriptionChanged.emit(new_text)

    def _apply_style(self) -> None:
        style_sheet = """
            QLabel {
                color: #000000;
                background-color: #ffffff;
                font-family: "Cascadia Code", "Fira Code", "Microsoft YaHei", monospace;
                font-weight: normal;
                border: 1px solid #000000;
                padding: 5px;
                margin: 0px;
            }
        """
        font = self._edit_widget.font()
        font.setPointSize(25)
        self._edit_widget.setStyleSheet(style_sheet)
        self._edit_widget.setFont(font)
