"""Convert Markdown-style content to WeChat-compatible HTML.

Style: body 17px, opening quotes gray 15px, section titles bold, short paragraphs.
"""

import re


def _escape_html(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _wrap_inline(text: str) -> str:
    """Bold, italic, inline code."""
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    text = re.sub(r"\*(.+?)\*", r"<em>\1</em>", text)
    text = re.sub(r"`(.+?)`", r"<code>\1</code>", text)
    return text


def _is_pull_quote(text: str) -> bool:
    """Check if a line is a standalone pull quote (just **bold** text)."""
    stripped = text.strip()
    # Must contain ** ** and nothing else besides maybe quotes/punctuation
    if re.match(r"^[「『""]?\*\*.+\*\*[」』""]?$", stripped):
        return True
    return False


def _parse_paragraph(para: str, is_first_blockquote: bool = False) -> str:
    """Parse a single paragraph block (separated by blank lines)."""
    stripped_lines = [l.strip() for l in para.strip().split("\n") if l.strip()]
    if not stripped_lines:
        return ""

    first = stripped_lines[0]

    # Horizontal rule
    if re.match(r"^---+\s*$", first):
        return '<hr style="border: none; border-top: 1px solid #e0e0e0; margin: 28px 0;" />'

    # Section title: ## text
    if first.startswith("## "):
        content = _wrap_inline(_escape_html(first[3:]))
        # Multi-line content: join with line breaks
        if len(stripped_lines) > 1:
            rest = "".join(
                _wrap_inline(_escape_html(l)) for l in stripped_lines[1:]
            )
            content += "<br/>" + rest
        return (
            f'<section style="margin: 28px 0 12px 0; padding-left: 12px; '
            f'border-left: 3px solid #d33; font-size: 17px; font-weight: bold; '
            f'color: #222222; line-height: 1.6;">{content}</section>'
        )

    # Sub-section: ### text
    if first.startswith("### "):
        content = _wrap_inline(_escape_html(first[4:]))
        return (
            f'<p style="font-size: 17px; font-weight: bold; margin: 20px 0 8px 0; '
            f'color: #333333; line-height: 1.6;">{content}</p>'
        )

    # Blockquote
    if first.startswith("> "):
        content_lines = []
        for line in stripped_lines:
            if line.startswith("> "):
                content_lines.append(line[2:])
            else:
                content_lines.append(line)
        content_text = "".join(content_lines)
        content = _wrap_inline(_escape_html(content_text))

        if is_first_blockquote:
            # Opening hook — gray, 15px, smaller feel
            return (
                f'<blockquote style="border-left: 3px solid #cccccc; '
                f'padding: 8px 0 8px 16px; margin: 16px 0 24px 0; '
                f'font-size: 15px; color: #888888; line-height: 1.8; '
                f'font-style: normal;">{content}</blockquote>'
            )
        else:
            # Standard blockquote
            return (
                f'<blockquote style="border-left: 3px solid #d33; '
                f'padding: 8px 0 8px 16px; margin: 20px 0; '
                f'font-size: 17px; color: #555555; line-height: 1.8; '
                f'font-style: normal;">{content}</blockquote>'
            )

    # Pull quote: standalone bold sentence
    if _is_pull_quote(stripped_lines[0]) and len(stripped_lines) < 3:
        content = _wrap_inline(_escape_html(first.strip()))
        return (
            f'<section style="text-align: center; padding: 18px 10px; '
            f'margin: 24px 0; '
            f'border-top: 1px solid #e8e8e8; '
            f'border-bottom: 1px solid #e8e8e8; '
            f'font-size: 17px; line-height: 1.7; color: #222222;">'
            f'{content}</section>'
        )

    # Ordered list
    if re.match(r"^\d+\.\s", first):
        items = []
        for line in stripped_lines:
            m = re.match(r"\d+\.\s(.+)", line)
            if m:
                items.append(
                    f'<li style="margin: 4px 0; line-height: 1.8; color: #333333; '
                    f'font-size: 17px;">{_wrap_inline(_escape_html(m.group(1)))}</li>'
                )
        return (
            f'<ol style="padding-left: 20px; margin: 12px 0 12px 0;">'
            + "".join(items)
            + "</ol>"
        )

    # Unordered list
    if re.match(r"^[\-\*]\s", first):
        items = []
        for line in stripped_lines:
            m = re.match(r"^[\-\*]\s(.+)", line)
            if m:
                items.append(
                    f'<li style="margin: 4px 0; line-height: 1.8; color: #333333; '
                    f'font-size: 17px;">{_wrap_inline(_escape_html(m.group(1)))}</li>'
                )
        return (
            f'<ul style="padding-left: 20px; margin: 12px 0 12px 0; '
            f'list-style-type: disc;">'
            + "".join(items)
            + "</ul>"
        )

    # Regular paragraph
    content = "<br/>".join(
        _wrap_inline(_escape_html(l)) for l in stripped_lines
    )
    return (
        f'<p style="font-size: 17px; line-height: 1.75; margin: 14px 0; '
        f'color: #333333;">{content}</p>'
    )


def markdown_to_wechat_html(markdown_text: str) -> str:
    """Convert markdown to WeChat-compatible HTML.

    Style rules:
    - Body: 17px, line-height 1.75, #333, no indent
    - Opening blockquote: gray 15px
    - Section titles (##): bold 17px, red left border
    - Pull quotes (**sentence** standalone): centered with borders
    - Short paragraphs with generous spacing
    """
    text = markdown_text.strip()
    # Split by double newlines to get paragraph blocks
    blocks = re.split(r"\n\s*\n", text)

    html_parts = ['<section style="padding: 4px 0;">']

    blockquote_count = 0

    for i, block in enumerate(blocks):
        stripped = block.strip()
        if not stripped:
            continue

        is_bq = stripped.startswith("> ")
        if is_bq:
            blockquote_count += 1
            is_first = blockquote_count == 1
            html_parts.append(_parse_paragraph(block, is_first_blockquote=is_first))
        else:
            html_parts.append(_parse_paragraph(block))

    html_parts.append("</section>")

    return "\n".join(html_parts)
