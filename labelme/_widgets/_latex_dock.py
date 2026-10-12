from __future__ import annotations

import json
from pathlib import Path

from PySide6 import QtWidgets
from PySide6.QtCore import Qt, Signal
from PySide6.QtWebEngineWidgets import QWebEngineView
from loguru import logger

from ._latex_renderer import LatexRenderer


class LatexEditDialog(QtWidgets.QDialog):
    """Dialog for editing LaTeX formula content."""

    def __init__(self, initial_text: str = "", parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(self.tr("Edit LaTeX"))
        self.resize(600, 300)

        layout = QtWidgets.QVBoxLayout(self)

        self._text_edit = QtWidgets.QPlainTextEdit()
        self._text_edit.setPlainText(initial_text)
        layout.addWidget(self._text_edit)

        btn_layout = QtWidgets.QHBoxLayout()
        save_btn = QtWidgets.QPushButton(self.tr("Save"))
        cancel_btn = QtWidgets.QPushButton(self.tr("Cancel"))
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

        save_btn.clicked.connect(self.accept)
        cancel_btn.clicked.connect(self.reject)

    def get_text(self) -> str:
        return self._text_edit.toPlainText()


class LatexDockWidget(QtWidgets.QDockWidget):
    """Dock widget for LaTeX formula display and editing.

    Displays LaTeX formulas using KaTeX in a QWebEngineView.
    Supports editing via a dialog and reads content from:
      - JSON annotation file (shapes[0].description)
      - or a .txt file with the same base name as the image.

    Emits latexEdited when the user edits LaTeX content so the
    Description dock can stay in sync.
    """

    latexEdited = Signal(str)

    _LATEX_DEFAULTS = object()

    def __init__(
        self,
        katex_dir: str | Path,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent.tr("LaTeX") if parent else "LaTeX", parent)
        self.setObjectName("LaTeX")

        self._renderer = LatexRenderer(str(katex_dir) if isinstance(katex_dir, Path) else katex_dir)
        self._current_file: str | None = None

        # Build UI
        container = QtWidgets.QWidget()
        layout = QtWidgets.QVBoxLayout(container)
        layout.setContentsMargins(2, 2, 2, 2)

        self._edit_btn = QtWidgets.QPushButton(self.tr("Edit LaTeX"))
        self._edit_btn.clicked.connect(self._on_edit)
        layout.addWidget(self._edit_btn)

        self._web_view = QWebEngineView()
        layout.addWidget(self._web_view)

        self.setWidget(container)

    # ---- public API ----------------------------------------------------------

    def show_latex(self, image_path: str | None) -> None:
        """Load and render LaTeX content for the given image path.

        Reads from the JSON annotation file first (shapes[0].description),
        then falls back to a same-basename .txt file.
        """
        if not image_path:
            logger.debug("show_latex: no image path provided")
            self._web_view.setHtml("")
            return

        try:
            base_name, _ext = image_path.rsplit(".", 1)
        except ValueError:
            logger.warning("Unexpected filename format: {}", image_path)
            self._web_view.setHtml("")
            return

        content: str | None = None

        # Try JSON annotation file first
        json_filename = base_name + ".json"
        if self._file_exists(json_filename):
            try:
                with open(json_filename, encoding="utf-8") as f:
                    data = json.load(f)
                content = data.get("shapes", [{}])[0].get("description")
            except Exception:
                content = None

        # Fall back to .txt file
        if not content:
            txt_filename = base_name + ".txt"
            if self._file_exists(txt_filename):
                try:
                    with open(txt_filename, encoding="utf-8") as f:
                        content = f.read().strip()
                except Exception:
                    content = None

        if content:
            self._current_file = (
                json_filename if self._file_exists(json_filename) else txt_filename
            )
            self._web_view.setHtml(self._renderer.generate_html(content))
        else:
            self._web_view.setHtml("")

    # ---- private -------------------------------------------------------------

    @staticmethod
    def _file_exists(path: str) -> bool:
        import os
        return os.path.exists(path)

    def _on_edit(self) -> None:
        if not self._current_file or not self._file_exists(self._current_file):
            QtWidgets.QMessageBox.warning(
                self, self.tr("Error"), self.tr("No valid LaTeX file loaded.")
            )
            return

        try:
            with open(self._current_file, encoding="utf-8") as f:
                content = f.read()
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, self.tr("Error"), self.tr("Failed to read file: {}").format(e)
            )
            return

        dlg = LatexEditDialog(content, self)
        if dlg.exec() == QtWidgets.QDialog.DialogCode.Accepted:
            new_text = dlg.get_text()
            try:
                with open(self._current_file, "w", encoding="utf-8") as f:
                    f.write(new_text)
                self._web_view.setHtml(self._renderer.generate_html(new_text))
                self.latexEdited.emit(new_text)
            except Exception as e:
                QtWidgets.QMessageBox.warning(
                    self, self.tr("Error"), self.tr("Failed to save file: {}").format(e)
                )

    def set_latex_text(self, text: str) -> None:
        """Render arbitrary LaTeX text directly (e.g. from shape description)."""
        self._web_view.setHtml(self._renderer.generate_html(text))
