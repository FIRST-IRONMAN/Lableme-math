from __future__ import annotations

import subprocess
from pathlib import Path

from loguru import logger


class ExternalEditorAction:
    """Launch an external image editor with the current image.

    Searches for a portable editor executable relative to the package directory.
    """

    def __init__(
        self,
        editor_name: str = "Pinta",
        editor_dir: str | Path | None = None,
    ) -> None:
        self._editor_name = editor_name
        if editor_dir is None:
            editor_dir = Path(__file__).resolve().parent / editor_name
        self._editor_dir = Path(editor_dir) if isinstance(editor_dir, str) else editor_dir
        self._exe_path: Path | None = self._find_exe()

    def _find_exe(self) -> Path | None:
        candidates = [
            self._editor_dir / f"{self._editor_name}.exe",
            self._editor_dir / "bin" / f"{self._editor_name}.exe",
        ]
        for path in candidates:
            if path.exists():
                return path
        return None

    @property
    def is_available(self) -> bool:
        return self._exe_path is not None

    @property
    def editor_path(self) -> Path | None:
        return self._exe_path

    def open_image(self, image_path: str | None) -> bool:
        """Launch the editor with the given image path.

        Returns:
            True if the editor was launched successfully.
        """
        if not self._exe_path:
            logger.warning("External editor not found: {}", self._editor_name)
            return False
        if not image_path:
            logger.warning("No image path to open in external editor")
            return False

        try:
            subprocess.Popen([str(self._exe_path), image_path])
            logger.info("Launched {} with {}", self._editor_name, image_path)
            return True
        except OSError as e:
            logger.error("Failed to launch {}: {}", self._editor_name, e)
            return False
