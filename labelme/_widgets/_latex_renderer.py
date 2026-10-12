from __future__ import annotations

import base64
import html
import re
from pathlib import Path

from loguru import logger


class LatexRenderer:
    """Offline KaTeX renderer for LaTeX formula display.

    Loads KaTeX resources (CSS, JS, fonts) from a local directory and
    generates self-contained HTML pages that embed inline base64 font data,
    so no network access is needed.
    """

    FONT_URL_PATTERN = re.compile(r'url\(["\']?fonts/([^)"\']+\.woff2)["\']?\)')

    def __init__(self, katex_dir: str | Path) -> None:
        self._katex_dir = Path(katex_dir)
        self._katex_css: str | None = None
        self._katex_js: str | None = None
        self._auto_render_js: str | None = None

    def _load_file(self, path: Path, encoding: str = "utf-8") -> str:
        try:
            return path.read_text(encoding=encoding)
        except Exception as e:
            raise RuntimeError(f"Failed to read file: {path}\n{e}") from e

    def _embed_fonts_in_css(self, css_content: str) -> str:
        def replace_font(match: re.Match[str]) -> str:
            font_file = match.group(1)
            font_path = self._katex_dir / "fonts" / font_file
            if not font_path.exists():
                logger.warning("Font file not found: {}", font_path)
                return match.group(0)
            try:
                data = base64.b64encode(font_path.read_bytes()).decode("ascii")
                return f"url(data:font/woff2;base64,{data})"
            except Exception as e:
                logger.error("Failed to read font file {}: {}", font_path, e)
                return match.group(0)

        return self.FONT_URL_PATTERN.sub(replace_font, css_content)

    def _load_resources(self) -> None:
        if self._katex_css is None:
            css_path = self._katex_dir / "katex.min.css"
            raw_css = self._load_file(css_path)
            self._katex_css = self._embed_fonts_in_css(raw_css)

        if self._katex_js is None:
            js_path = self._katex_dir / "katex.min.js"
            self._katex_js = self._load_file(js_path)

        if self._auto_render_js is None:
            auto_render_path = self._katex_dir / "contrib" / "auto-render.min.js"
            self._auto_render_js = self._load_file(auto_render_path)

    def generate_html(
        self,
        latex_text: str,
        font_size: int = 150,
        font_family: str = "Arial",
    ) -> str:
        """Generate a self-contained HTML page with rendered LaTeX.

        Args:
            latex_text: LaTeX formula content.
            font_size: Percentage font size (50-300).
            font_family: CSS font-family value.

        Returns:
            Complete HTML string with embedded KaTeX resources.
        """
        if not latex_text or latex_text.strip() == "":
            return (
                f"<html><body><p style='color:gray;font-family:{font_family}'>"
                f"No LaTeX content</p></body></html>"
            )

        self._load_resources()

        font_size = max(50, min(font_size, 300))
        safe_latex = html.escape(latex_text)

        return f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8" />
<style>{self._katex_css}</style>
<script>{self._katex_js}</script>
<script>{self._auto_render_js}</script>
<style>
body {{
    font-family: {font_family};
    padding: 2px;
    line-height: 1.6;
}}
.formula-container {{
    margin: 0;
    padding: 2px;
    text-align: center;
}}
.katex {{
    font-size: {font_size}%;
}}
</style>
</head>
<body>
<div class="formula-container">$$
{safe_latex}
$$</div>
<script>
document.addEventListener('DOMContentLoaded', function() {{
    renderMathInElement(document.body, {{
        delimiters: [
            {{left: '$$', right: '$$', display: true}},
            {{left: '$', right: '$', display: false}}
        ],
        throwOnError: false,
        strict: false,
        output: 'html'
    }});
}});
</script>
</body>
</html>"""
