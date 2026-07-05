import math
import re


class TextPageLayoutEngine:
    def __init__(self, root):
        self.root = root

    def build_pages(self, blocks, view_width, view_height, font_lookup):
        if not blocks:
            return []

        pages = []
        current_blocks = []
        for block in blocks:
            if not block.get("segments"):
                continue

            block_type = block.get("type")
            if block_type in {"header", "subheader"}:
                if current_blocks:
                    pages.append(current_blocks)
                    current_blocks = []
                current_blocks.append(self._make_block_entry(block, block_type))
                continue

            if block_type == "paragraph":
                paragraph_block = self._make_paragraph_block(block)
                if current_blocks and self._estimate_paragraph_height(paragraph_block, view_width) > view_height:
                    pages.append(current_blocks)
                    current_blocks = []
                if current_blocks and self._estimate_page_height(current_blocks + [paragraph_block], view_width) > view_height:
                    pages.append(current_blocks)
                    current_blocks = []
                current_blocks.append(paragraph_block)

        if current_blocks:
            pages.append(current_blocks)
        return pages

    def _make_block_entry(self, block, block_type):
        return {
            "type": block_type,
            "segments": [
                {"text": text, "style": style or self._block_tag(block_type)}
                for text, style in block.get("segments", [])
            ],
        }

    def _make_paragraph_block(self, block):
        tokens = self._collect_tokens(block)
        return {
            "type": "paragraph",
            "segments": tokens,
            "para_end": True,
        }

    def _collect_tokens(self, block):
        tokens = []
        for text, style in block.get("segments", []):
            if not text:
                continue
            tag_name = style if style in {"normal", "bold", "italic", "bold_italic", "header", "subheader"} else self._block_tag(block.get("type"))
            for match in re.finditer(r"\S+|\s+", text):
                token = match.group(0)
                if token:
                    tokens.append({"text": token, "style": tag_name})
        return tokens

    def _block_tag(self, block_type):
        if block_type == "header":
            return "header"
        if block_type == "subheader":
            return "subheader"
        return "normal"

    def _estimate_page_height(self, blocks, view_width):
        if not blocks:
            return 1
        height = 0
        for block in blocks:
            if block.get("type") in {"header", "subheader"}:
                height += 96
            else:
                height += self._estimate_paragraph_height(block, view_width)
        return height + 24

    def _estimate_paragraph_height(self, block, view_width):
        if not block.get("segments"):
            return 24

        total_chars = 0
        for entry in block.get("segments", []):
            text = entry.get("text", "") or ""
            total_chars += len(text)

        if total_chars <= 0:
            return 24

        approx_chars_per_line = max(24, int(view_width / 1.7))
        if view_width >= 1400:
            approx_chars_per_line = max(24, int(view_width / 1.6))
        elif view_width >= 1100:
            approx_chars_per_line = max(24, int(view_width / 1.7))
        elif view_width >= 800:
            approx_chars_per_line = max(22, int(view_width / 1.9))
        else:
            approx_chars_per_line = max(20, int(view_width / 2.0))

        line_count = max(1, math.ceil(total_chars / approx_chars_per_line))
        if view_width >= 1400:
            line_count = max(1, int(line_count * 0.9))
        elif view_width >= 1100:
            line_count = max(1, int(line_count * 0.92))
        elif view_width >= 800:
            line_count = max(1, int(line_count * 0.95))
        else:
            line_count = max(1, int(line_count * 1.0))

        return max(24, line_count * 14 + 10)
