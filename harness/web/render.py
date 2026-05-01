"""Markdown to HTML for run reports (trusted local content)."""

from __future__ import annotations

import markdown


def md_to_html(text: str) -> str:
    if not text.strip():
        return "<p>(empty)</p>"
    return markdown.markdown(
        text,
        extensions=["fenced_code", "tables", "nl2br"],
        output_format="html5",
    )
