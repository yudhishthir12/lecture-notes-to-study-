"""PDF export service for LectureForge AI study packs using Markdown and WeasyPrint.

Converts structured study packs into beautifully formatted, publication-grade academic
PDF documents featuring custom typography, title pages, headers, footers, and page numbers.
Gracefully handles missing WeasyPrint native dependencies on environments without GTK/Cairo.
"""

from __future__ import annotations

import logging
from pathlib import Path

import markdown

from app.exporters.markdown_exporter import MarkdownExporter
from app.schemas.study_pack import StudyPackContent

logger = logging.getLogger(__name__)

# Academic stylesheet tailored for print and digital PDF study packs
PDF_CSS = """
@page {
    size: letter portrait;
    margin: 20mm 15mm 20mm 15mm;
    @top-right {
        content: "LectureForge AI";
        font-size: 8pt;
        color: #718096;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
    @bottom-center {
        content: "Page " counter(page) " of " counter(pages);
        font-size: 9pt;
        color: #718096;
        font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    }
}

@page :first {
    margin-top: 30mm;
    @top-right { content: normal; }
    @bottom-center { content: normal; }
}

body {
    font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Helvetica Neue", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.6;
    color: #2d3748;
    background-color: #ffffff;
}

h1, h2, h3, h4, h5, h6 {
    color: #1a202c;
    font-weight: 700;
    line-height: 1.25;
    page-break-after: avoid;
    break-after: avoid;
}

h1 {
    font-size: 24pt;
    color: #2b6cb0;
    margin-bottom: 8pt;
    border-bottom: 2pt solid #e2e8f0;
    padding-bottom: 6pt;
}

h2 {
    font-size: 16pt;
    color: #2c5282;
    margin-top: 18pt;
    margin-bottom: 8pt;
    border-bottom: 1pt solid #edf2f7;
    padding-bottom: 4pt;
}

h3 {
    font-size: 13pt;
    color: #2d3748;
    margin-top: 14pt;
    margin-bottom: 6pt;
}

h4 {
    font-size: 11.5pt;
    color: #4a5568;
    margin-top: 10pt;
    margin-bottom: 4pt;
}

p {
    margin-top: 0;
    margin-bottom: 8pt;
}

blockquote {
    border-left: 3pt solid #4299e1;
    margin: 8pt 0;
    padding: 6pt 12pt;
    background-color: #ebf8ff;
    color: #2b6cb0;
    font-style: italic;
    border-radius: 2pt;
}

code {
    font-family: "SFMono-Regular", Consolas, "Liberation Mono", Menlo, Courier, monospace;
    font-size: 9.5pt;
    background-color: #edf2f7;
    padding: 1.5pt 4pt;
    border-radius: 3pt;
    color: #c53030;
}

pre {
    background-color: #f7fafc;
    border: 1pt solid #e2e8f0;
    border-radius: 4pt;
    padding: 8pt 10pt;
    overflow-x: auto;
    margin-bottom: 10pt;
    page-break-inside: avoid;
    break-inside: avoid;
}

pre code {
    background-color: transparent;
    padding: 0;
    color: #2d3748;
    font-size: 9pt;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin: 12pt 0;
    page-break-inside: avoid;
    break-inside: avoid;
    font-size: 10pt;
}

th, td {
    padding: 6pt 8pt;
    text-align: left;
    border: 1pt solid #cbd5e0;
}

th {
    background-color: #edf2f7;
    font-weight: 600;
    color: #2d3748;
}

tr:nth-child(even) td {
    background-color: #f7fafc;
}

ul, ol {
    margin-top: 0;
    margin-bottom: 8pt;
    padding-left: 18pt;
}

li {
    margin-bottom: 3pt;
}

.title-page {
    page-break-after: always;
    break-after: page;
    text-align: center;
    padding-top: 50mm;
}

.title-page h1 {
    font-size: 28pt;
    color: #1a365d;
    border-bottom: none;
    margin-bottom: 12pt;
}

.title-page .meta {
    font-size: 12pt;
    color: #4a5568;
    margin-top: 15pt;
}

hr {
    border: none;
    border-top: 1pt solid #e2e8f0;
    margin: 14pt 0;
}
"""


class PDFExporter:
    """Renders structured StudyPackContent into styled PDF documents."""

    def __init__(self, markdown_exporter: MarkdownExporter | None = None) -> None:
        """Initialize PDFExporter."""
        self.md_exporter = markdown_exporter or MarkdownExporter()

    def export(self, study_pack: StudyPackContent, output_path: str) -> str:
        """Export study pack to a styled PDF file at output_path.

        If WeasyPrint or its native runtime libraries are unavailable, saves
        the styled HTML representation alongside output_path and returns an
        informative error message.

        Args:
            study_pack: The StudyPackContent to render.
            output_path: File system path where the PDF should be generated.

        Returns:
            The resolved output_path on success, or an error message string if WeasyPrint is unavailable.
        """
        # Ensure parent directory exists
        out_file = Path(output_path).resolve()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        # 1. Generate Markdown content
        md_text = self.md_exporter.export(study_pack)

        # 2. Convert Markdown to HTML
        html_body = markdown.markdown(
            md_text,
            extensions=[
                "extra",
                "tables",
                "fenced_code",
                "toc",
                "sane_lists",
            ],
        )

        # 3. Assemble complete HTML with CSS styling and Title Page
        topic = study_pack.metadata.topic or "Lecture Study Pack"
        date_str = study_pack.metadata.generated_at.strftime("%B %d, %Y")
        pages_str = (
            ", ".join(str(p) for p in study_pack.metadata.source_pages)
            if study_pack.metadata.source_pages
            else "All"
        )

        full_html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>{topic} - Study Pack</title>
    <style>
{PDF_CSS}
    </style>
</head>
<body>
    <div class="title-page">
        <h1>{topic}</h1>
        <div class="meta">
            <p><strong>LectureForge AI Comprehensive Study Pack</strong></p>
            <p>Source Pages: {pages_str} | Date: {date_str}</p>
        </div>
    </div>
    <div class="content">
{html_body}
    </div>
</body>
</html>
"""

        # 4. Attempt rendering via WeasyPrint
        try:
            from weasyprint import HTML

            logger.info("Rendering PDF with WeasyPrint: %s", str(out_file))
            HTML(string=full_html).write_pdf(str(out_file))
            logger.info("PDF export successful: %s", str(out_file))
            return str(out_file)

        except (ImportError, OSError, Exception) as exc:
            # WeasyPrint native libraries (pango/cairo) missing on system
            html_fallback_path = str(out_file.with_suffix(".html"))
            try:
                with open(html_fallback_path, "w", encoding="utf-8") as f:
                    f.write(full_html)
                logger.warning(
                    "WeasyPrint unavailable (%s). Saved rendered HTML fallback to %s",
                    exc,
                    html_fallback_path,
                )
            except Exception as write_err:
                logger.error("Failed to write HTML fallback: %s", write_err)

            error_msg = (
                f"PDF export unavailable: WeasyPrint native dependencies are not installed or failed ({exc}). "
                f"Styled HTML report was saved to: {html_fallback_path}"
            )
            return error_msg
