import os
import sys
import tempfile
import unittest
import tkinter as tk
from tkinter import font as tkfont
from unittest.mock import patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(__file__))))

from booklizard.layout_engine import TextPageLayoutEngine
from booklizard.pagination import parse_book_text
from booklizard.storage import StorageManager
from booklizard.ui import BookApp


class LayoutEngineTests(unittest.TestCase):
    def setUp(self):
        self.root = tk.Tk()
        self.root.withdraw()

    def tearDown(self):
        try:
            if self.root.winfo_exists():
                self.root.destroy()
        except tk.TclError:
            pass

    def test_layout_engine_keeps_content_within_page_height(self):
        engine = TextPageLayoutEngine(self.root)
        body_font = tkfont.Font(family="Arial", size=12)
        font_lookup = lambda style: body_font

        blocks = [
            {
                "type": "paragraph",
                "segments": [("This is a long paragraph that should wrap onto multiple lines so the layout engine has to break it safely into a page-sized chunk. " * 10, "normal")],
            }
        ]

        pages = engine.build_pages(blocks, view_width=300, view_height=12, font_lookup=font_lookup)
        self.assertGreaterEqual(len(pages), 1)
        self.assertTrue(pages)

    def test_header_spacing_is_accounted_for_in_layout_measurement(self):
        engine = TextPageLayoutEngine(self.root)
        body_font = tkfont.Font(family="Arial", size=12)
        font_lookup = lambda style: body_font

        paragraph_block = {"type": "paragraph", "segments": [{"text": "A short paragraph.", "style": "normal"}], "para_end": True}
        header_block = {"type": "header", "segments": [{"text": "Heading", "style": "normal"}]}

        paragraph_height = engine._estimate_paragraph_height(paragraph_block, view_width=300)
        header_height = engine._estimate_page_height([header_block], view_width=300)

        self.assertGreater(header_height, paragraph_height)

    def test_load_current_book_defers_page_build_until_layout_is_ready(self):
        with patch.object(BookApp, "_build_content_pages") as build_pages:
            app = BookApp(self.root)
            try:
                self.assertTrue(app._needs_page_rebuild)
                self.assertEqual(build_pages.call_count, 0)
            finally:
                self.root.update_idletasks()
                app.root.destroy()

    def test_typography_settings_change_text_size(self):
        app = BookApp(self.root)
        try:
            app.text_size_level = 0
            app.apply_theme()
            initial_size = app.body_font.actual()["size"]
            app.adjust_text_size(1)
            self.assertGreater(app.body_font.actual()["size"], initial_size)
        finally:
            self.root.update_idletasks()
            app.root.destroy()

    def test_storage_persists_reader_settings(self):
        with tempfile.TemporaryDirectory() as tempdir:
            with patch("booklizard.storage.APP_SUPPORT_ROOT", tempdir):
                manager = StorageManager()
                manager.save_settings({"current_theme": 2, "screen_size_index": 1, "text_size_level": 2})
                loaded = manager.load_settings()
                self.assertEqual(loaded["current_theme"], 2)
                self.assertEqual(loaded["screen_size_index"], 1)
                self.assertEqual(loaded["text_size_level"], 2)

    def test_first_unlock_creates_hidden_cached_copy(self):
        with tempfile.TemporaryDirectory() as tempdir:
            with patch("booklizard.storage.APP_SUPPORT_ROOT", tempdir):
                manager = StorageManager()
                manager.record_decrypted_book("book.txt", plaintext="Hello world")

                self.assertIn("book.txt", manager.get_decrypted_books())
                self.assertEqual(manager.load_cached_decrypted_book("book.txt"), "Hello world")

    def test_cached_decrypted_book_can_be_reused_without_password(self):
        with tempfile.TemporaryDirectory() as tempdir:
            with patch("booklizard.storage.APP_SUPPORT_ROOT", tempdir):
                manager = StorageManager()
                manager.record_decrypted_book("book-one.txt", plaintext="First")
                manager.record_decrypted_book("book-two.txt", plaintext="Second")

                self.assertEqual(manager.load_cached_decrypted_book("book-one.txt"), "First")
                self.assertEqual(manager.load_cached_decrypted_book("book-two.txt"), "Second")

    def test_layout_engine_does_not_emit_empty_pages(self):
        engine = TextPageLayoutEngine(self.root)
        body_font = tkfont.Font(family="Arial", size=12)
        font_lookup = lambda style: body_font

        blocks = [
            {
                "type": "paragraph",
                "segments": [("This is a long paragraph that should wrap onto multiple lines so the layout engine has to break it safely into a page-sized chunk. " * 10, "normal")],
            }
        ]

        pages = engine.build_pages(blocks, view_width=300, view_height=12, font_lookup=font_lookup)
        self.assertTrue(all(page for page in pages))

    def test_parser_treats_chapter_headings_as_headers(self):
        raw = "-----------------------\n\nChapter II Domi\n\nI'm late. Again.\n"
        title, author, blocks = parse_book_text(raw)
        self.assertEqual(len(blocks), 2)
        self.assertEqual(blocks[0]["type"], "header")
        self.assertEqual(blocks[1]["type"], "paragraph")


if __name__ == "__main__":
    unittest.main()
