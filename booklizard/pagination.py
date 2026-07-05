import re

TITLE_MARKER = "!#"
AUTHOR_MARKER = "~#"
HEADER_MARKER = "!##"
SUBHEADER_MARKER = "!###"
ITALIC_START = "@#"
ITALIC_END = "$#"
ITALIC_END_ALT = "#$"
BOLD_START = "@@#"
BOLD_END = "$$#"
CHAPTER_PATTERN = re.compile(r'^(Chapter|CHAPTER|Prologue|PROLOGUE|Epilogue|EPILOGUE|Book|BOOK)\b')
SEPARATOR_PATTERN = re.compile(r'^[\s\-_*=]{3,}$')


def parse_book_text(raw_text):
    if raw_text is None:
        return None, None, []

    title = None
    author = None
    blocks = []
    paragraph_lines = []

    def flush_paragraph():
        nonlocal paragraph_lines
        if not paragraph_lines:
            paragraph_lines = []
            return
        paragraph_text = " ".join(line.strip() for line in paragraph_lines if line.strip())
        paragraph_lines = []
        if paragraph_text:
            blocks.append({
                "type": "paragraph",
                "segments": parse_inline_markers(paragraph_text),
            })

    def _strip_heading_marker(line, marker):
        text = line[len(marker):].strip()
        suffix = marker[::-1]
        if text.endswith(suffix):
            text = text[: -len(suffix)].strip()
        return text

    for line in raw_text.splitlines():
        stripped = line.strip()
        if SEPARATOR_PATTERN.match(stripped):
            flush_paragraph()
            continue

        if not paragraph_lines and CHAPTER_PATTERN.match(stripped):
            flush_paragraph()
            blocks.append({
                "type": "header",
                "segments": parse_inline_markers(stripped),
            })
            continue

        if stripped.startswith(SUBHEADER_MARKER):
            flush_paragraph()
            blocks.append({
                "type": "subheader",
                "segments": parse_inline_markers(_strip_heading_marker(stripped, SUBHEADER_MARKER)),
            })
            continue

        if stripped.startswith(HEADER_MARKER):
            flush_paragraph()
            blocks.append({
                "type": "header",
                "segments": parse_inline_markers(_strip_heading_marker(stripped, HEADER_MARKER)),
            })
            continue

        if stripped.startswith(TITLE_MARKER) and not stripped.startswith(HEADER_MARKER):
            title = _strip_heading_marker(stripped, TITLE_MARKER)
            continue

        if stripped.startswith(AUTHOR_MARKER):
            author = stripped[len(AUTHOR_MARKER):].strip()
            continue

        if stripped == "":
            flush_paragraph()
            continue

        paragraph_lines.append(line)

    flush_paragraph()
    return title, author, blocks


def parse_inline_markers(text):
    segments = []
    buffer = ""
    bold = False
    italic = False
    last_pos = 0

    def current_style():
        if bold and italic:
            return "bold_italic"
        if bold:
            return "bold"
        if italic:
            return "italic"
        return "normal"

    def flush_buffer():
        nonlocal buffer
        if buffer:
            segments.append((buffer, current_style()))
            buffer = ""

    pattern = re.compile(r"(@@#|\$\$#|@#|\$#|#\$)")
    for match in pattern.finditer(text):
        buffer += text[last_pos:match.start()]
        flush_buffer()
        token = match.group(0)
        if token == BOLD_START:
            bold = True
        elif token == BOLD_END:
            bold = False
        elif token == ITALIC_START:
            italic = True
        elif token in {ITALIC_END, ITALIC_END_ALT}:
            italic = False
        last_pos = match.end()

    buffer += text[last_pos:]
    flush_buffer()
    return segments
