import os
import re
import tkinter as tk
from tkinter import font as tkfont
from tkinter import filedialog, simpledialog

from .config import ICON_FILENAME, WIDTH, HEIGHT, MARGIN, INTRO_TEXT, SCREEN_PRESETS
from .pagination import parse_book_text
from .storage import StorageManager
from .themes import THEMES
from .utils import resource_path
from .layout_engine import TextPageLayoutEngine


class BookApp:
    def __init__(self, root):
        self.root = root
        self.root.title("BookLizard")
        self.storage = StorageManager()
        self.screen_presets = SCREEN_PRESETS
        self.settings = self.storage.load_settings()
        self.current_size_index = int(self.settings.get("screen_size_index", 0))
        self.current_size_index = max(0, min(self.current_size_index, len(self.screen_presets) - 1))
        self.root.geometry(f"{self.screen_presets[self.current_size_index]['width']}x{self.screen_presets[self.current_size_index]['height']}")
        self.root.minsize(760, 600)
        # Window size is locked to a known preset instead of freely
        # resizing -- pagination is computed once for whichever fixed
        # size is active, rather than live-recalculating while dragging
        # a resize handle (which is what was causing wrap bugs).
        self.root.resizable(False, False)

        self.books = []
        self.book_entries = []
        self.current_book = None
        self.book_blocks = []
        self.pages = []
        self.current_page = 0
        self.current_theme = int(self.settings.get("current_theme", 1))
        self.current_theme = max(1, min(self.current_theme, len(THEMES)))
        self.menu_open = True
        self.menu_page = 0
        self.text_size_level = int(self.settings.get("text_size_level", 0))
        self.debug_mode = False
        self.current_title = None
        self.current_author = None
        self._resize_pending = False
        self._needs_page_rebuild = True

        self.toolbar = tk.Frame(self.root, height=44)
        self.toolbar.pack(fill="x", side="top")

        self.content_container = tk.Frame(self.root)
        self.content_container.pack(fill="both", expand=True)

        self.canvas = tk.Canvas(self.content_container, highlightthickness=0, bd=0, relief="flat")
        self.text_widget = tk.Text(
            self.content_container,
            wrap="word",
            state="disabled",
            bd=0,
            padx=8,
            pady=8,
            highlightthickness=0,
        )
        self.scrollbar = tk.Scrollbar(self.content_container, orient="vertical")
        self.text_widget.configure(yscrollcommand=self.scrollbar.set)
        self.scrollbar.configure(command=self.text_widget.yview)

        self._build_toolbar()
        self._build_notification()
        self.apply_theme()
        self._apply_app_icon()
        self.load_book_list()
        self.load_current_book()
        self._setup_drag_drop()
        self.root.after(0, self._initialize_layout)

        self.root.bind("<Right>", self.on_right)
        self.root.bind("<Left>", self.on_left)
        self.root.bind("<Escape>", self.toggle_menu)
        self.root.bind("<F3>", self.toggle_debug_mode)
        self.root.bind("<Key>", self.handle_keys)
        self.root.bind("<Configure>", self.on_resize)

        self.text_widget.bind("<MouseWheel>", self._on_mousewheel)
        self.text_widget.bind("<Button-4>", self._on_mousewheel)
        self.text_widget.bind("<Button-5>", self._on_mousewheel)
        self.text_widget.bind("<Shift-MouseWheel>", self._on_mousewheel)

        self.draw_page()

    def _build_toolbar(self):
        self.add_button = tk.Button(self.toolbar, text="Browse & Add", command=self.add_book_files, padx=12, pady=6)
        self.add_button.pack(side="left", padx=8, pady=4)

        self.menu_button = tk.Button(self.toolbar, text="Menu", command=self.toggle_menu, padx=12, pady=6)
        self.menu_button.pack(side="left", padx=8, pady=4)

        self.page_label = tk.Label(self.toolbar, text="", anchor="e")
        self.page_label.pack(side="right", padx=4, pady=4)
        self.page_arrow = tk.Label(self.toolbar, text="", anchor="e")
        self.page_arrow.pack(side="right", padx=4, pady=4)

    def _build_notification(self):
        self.notification_frame = tk.Frame(self.root, bd=1, relief="solid")
        self.notification_label = tk.Label(self.notification_frame, text="", padx=10, pady=6)
        self.notification_label.pack()
        self.notification_frame.place_forget()
        self._notification_job = None

    def show_notification(self, message, kind="info"):
        if not message:
            return
        if self._notification_job is not None:
            self.root.after_cancel(self._notification_job)
        bg = "#2b2b2b"
        fg = "#f5f5f5"
        if kind == "error":
            bg = "#7f1d1d"
        elif kind == "success":
            bg = "#1f5f3d"
        self.notification_frame.configure(bg=bg)
        self.notification_label.configure(bg=bg, fg=fg, text=message)
        self.notification_frame.place(relx=0.5, rely=0.03, anchor="n")
        self.notification_frame.lift()
        self._notification_job = self.root.after(2200, self._hide_notification)

    def _hide_notification(self):
        self.notification_frame.place_forget()
        self._notification_job = None

    def apply_theme(self):
        theme = THEMES.get(self.current_theme, THEMES[1])
        self.bg = theme["bg"]
        self.fg = theme["fg"]
        font_family = self._resolve_font_family(theme["font"])

        self.root.configure(bg=self.bg)
        self.toolbar.configure(bg=self.bg)
        self.content_container.configure(bg=self.bg)
        self.canvas.configure(bg=self.bg, highlightbackground=self.bg, highlightcolor=self.bg)
        self.text_widget.configure(bg=self.bg, fg=self.fg, insertbackground=self.fg, selectbackground=self.fg, selectforeground=self.bg)
        self.scrollbar.configure(bg=self.bg, troughcolor=self.bg, activebackground=self.fg)
        self.page_label.configure(bg=self.bg, fg=self.fg)
        self.page_arrow.configure(bg=self.bg, fg=self.fg)

        button_font = self._make_font(font_family, 12, weight="bold")
        self.add_button.configure(bg=self.bg, fg=self.fg, activebackground=self.fg, activeforeground=self.bg, highlightbackground=self.bg, highlightcolor=self.bg, font=button_font)
        self.menu_button.configure(bg=self.bg, fg=self.fg, activebackground=self.fg, activeforeground=self.bg, highlightbackground=self.bg, highlightcolor=self.bg, font=button_font)

        if font_family == "OpenDyslexic":
            title_size, body_size, self.spacing = 40, 16, 8
        else:
            title_size, body_size, self.spacing = 40, 15, 4

        title_size += self.text_size_level
        body_size += self.text_size_level

        self.title_font = self._make_font(font_family, title_size, weight="bold")
        self.body_font = self._make_font(font_family, body_size)
        self.bold_font = self._make_font(font_family, body_size, weight="bold")
        self.italic_font = self._make_font(font_family, body_size, slant="italic")
        self.bold_italic_font = self._make_font(font_family, body_size, weight="bold", slant="italic")
        self.header_font = self._make_font(font_family, body_size + 5, weight="bold")
        self.subheader_font = self._make_font(font_family, body_size + 3, weight="bold")
        self.book_title_font = self._make_font(font_family, title_size, weight="bold")
        self.book_author_font = self._make_font(font_family, body_size, slant="italic")

        self.page_label.configure(font=self._make_font(font_family, 11))
        self.page_arrow.configure(font=self._make_font(font_family, 11))

        self._configure_text_tags()
        self._needs_page_rebuild = True
        self._persist_settings()
        self.page_arrow.configure(text="")

    def _resolve_font_family(self, family):
        try:
            available = set(tkfont.families())
        except Exception:
            available = set()
        if family in available:
            return family
        if family == "OpenDyslexic":
            for candidate in ("Arial", "Helvetica", "Verdana", "Georgia"):
                if candidate in available:
                    return candidate
        for candidate in ("Arial", "Helvetica", "Verdana", "Georgia", "Times New Roman"):
            if candidate in available:
                return candidate
        return "Arial"

    def _make_font(self, family, size, weight="normal", slant="roman"):
        try:
            return tkfont.Font(family=family, size=size, weight=weight, slant=slant)
        except tk.TclError:
            fallback = self._resolve_font_family("Arial")
            return tkfont.Font(family=fallback, size=size, weight=weight, slant=slant)

    def _configure_text_tags(self):
        self._configure_widget_tags(self.text_widget)

    def _configure_widget_tags(self, widget):
        widget.tag_configure("normal", font=self.body_font, foreground=self.fg)
        widget.tag_configure("bold", font=self.bold_font, foreground=self.fg)
        widget.tag_configure("italic", font=self.italic_font, foreground=self.fg)
        widget.tag_configure("bold_italic", font=self.bold_italic_font, foreground=self.fg)
        widget.tag_configure("header", font=self.header_font, foreground=self.fg)
        widget.tag_configure("subheader", font=self.subheader_font, foreground=self.fg)
        widget.tag_configure("book_title", font=self.book_title_font, foreground=self.fg)
        widget.tag_configure("book_author", font=self.book_author_font, foreground=self.fg)
        widget.tag_configure("debug", font=self._make_font(self._resolve_font_family("Arial"), 10), foreground="#999999")
        widget.tag_configure("info", font=self.body_font, foreground=self.fg)

    def _apply_app_icon(self):
        icon_path = resource_path(ICON_FILENAME)
        if not os.path.exists(icon_path):
            return
        try:
            self.root.iconbitmap(icon_path)
        except Exception:
            try:
                photo = tk.PhotoImage(file=icon_path)
                self.root.iconphoto(False, photo)
                self.root._icon_image = photo
            except Exception:
                pass

    def _setup_drag_drop(self):
        try:
            import tkinter.dnd as dnd
            if hasattr(self.root, "drop_target_register") and hasattr(self.root, "dnd_bind"):
                self.root.drop_target_register(dnd.DND_FILES)
                self.root.dnd_bind("<<Drop>>", self._on_drop)
                return
        except Exception:
            pass

    def _on_drop(self, event):
        paths = self._parse_drop_files(event.data)
        if paths:
            self._import_paths(paths)

    def _parse_drop_files(self, data):
        if not data:
            return []
        parts = []
        current = ""
        in_brace = False
        for ch in data:
            if ch == "{":
                in_brace = True
                current = ""
            elif ch == "}":
                in_brace = False
                parts.append(current)
                current = ""
            elif ch == " " and not in_brace:
                if current:
                    parts.append(current)
                    current = ""
            else:
                current += ch
        if current:
            parts.append(current)
        return parts

    def _prompt_password(self, prompt_title):
        return simpledialog.askstring(prompt_title, "Enter encryption password:", show="*", parent=self.root)

    def load_book_list(self):
        filenames = self.storage.get_books()
        self.book_entries = [self.storage.load_book_metadata(name) for name in filenames]
        self.books = [entry["filename"] for entry in self.book_entries]
        if self.current_book is None and self.books:
            self.current_book = 0
        elif self.current_book is not None and self.current_book >= len(self.books):
            self.current_book = 0 if self.books else None

    def display_title(self, entry):
        title = (entry.get("title") or "").strip()
        if title:
            return title
        filename = entry.get("filename") or ""
        return os.path.splitext(filename)[0] or "Untitled Book"

    def display_author(self, entry):
        author = (entry.get("author") or "").strip()
        return author or "Author Unknown"

    def load_current_book(self, password=None):
        self.load_book_list()
        if not self.book_entries:
            self.current_title = None
            self.current_author = None
            self.book_blocks = []
            self.pages = [{"type": "info", "message": "No books found."}]
            self.current_page = 0
            self._needs_page_rebuild = False
            return False

        book = self.book_entries[self.current_book]
        try:
            raw_text = self.storage.load_book(book["filename"], password=password)
        except Exception as exc:
            if self.storage.is_encrypted(book["filename"]):
                if password is None:
                    password = self._prompt_password("Unlock encrypted book")
                if not password:
                    self.show_notification("Password required", kind="error")
                    self.pages = [{"type": "info", "message": "This book is encrypted. Enter the correct password to unlock it."}]
                    self.current_title = self.display_title(book)
                    self.current_author = self.display_author(book)
                    self.book_blocks = []
                    self.current_page = 0
                    self._needs_page_rebuild = False
                    return False
                try:
                    raw_text = self.storage.load_book(book["filename"], password=password)
                except Exception:
                    self.show_notification("Incorrect password", kind="error")
                    self.pages = [{"type": "info", "message": "Incorrect password. This book cannot be opened."}]
                    self.current_title = self.display_title(book)
                    self.current_author = self.display_author(book)
                    self.book_blocks = []
                    self.current_page = 0
                    self._needs_page_rebuild = False
                    return False
            else:
                self.show_notification("Unable to load book", kind="error")
                self.pages = [{"type": "info", "message": "Unable to load this book."}]
                self.current_title = self.display_title(book)
                self.current_author = self.display_author(book)
                self.book_blocks = []
                self.current_page = 0
                self._needs_page_rebuild = False
                return False

        was_decrypted = self.storage.is_book_decrypted(book["filename"])
        if self.storage.is_encrypted(book["filename"]):
            self.storage.record_decrypted_book(book["filename"], plaintext=raw_text)
            if not was_decrypted:
                self.show_notification("Book unlocked", kind="success")

        title, author, blocks = parse_book_text(raw_text)
        self.current_title = (title or "").strip() or self.display_title(book)
        self.current_author = (author or "").strip() or self.display_author(book)
        self.book_blocks = blocks
        self.pages = []
        self.current_page = self.storage.load_progress(book["filename"])
        self._needs_page_rebuild = True
        return True

    def _initialize_layout(self):
        self.root.update_idletasks()
        self._needs_page_rebuild = True
        self._update_text_padding()
        self.draw_page()

    def _update_text_padding(self):
        width = max(800, self.root.winfo_width() or WIDTH)
        height = max(400, self.root.winfo_height() or HEIGHT)
        padx = max(8, min(50, int(width / 80)))
        pady = max(8, min(20, int(height / 80)))
        self.text_widget.configure(padx=padx, pady=pady)

    def _build_content_pages(self, blocks):
        self.pages = [{"type": "intro", "title": self.current_title, "author": self.current_author}]
        if not blocks:
            self._needs_page_rebuild = False
            return

        self._update_text_padding()
        self.root.update_idletasks()

        layout_engine = TextPageLayoutEngine(self.root)
        view_width = max(240, self._measure_text_width())
        view_height = max(8, self._get_page_height_limit())

        def font_lookup(style):
            if style == "bold":
                return self.bold_font
            if style == "italic":
                return self.italic_font
            if style == "bold_italic":
                return self.bold_italic_font
            if style == "header":
                return self.header_font
            if style == "subheader":
                return self.subheader_font
            if style == "book_title":
                return self.book_title_font
            if style == "book_author":
                return self.book_author_font
            if style == "info":
                return self.body_font
            return self.body_font

        built_pages = layout_engine.build_pages(blocks, view_width, view_height, font_lookup)
        for page_blocks in built_pages:
            self.pages.append({"type": "content", "blocks": page_blocks})

        self._needs_page_rebuild = False

    def _get_page_height_limit(self):
        self.root.update_idletasks()
        visible_height = self.text_widget.winfo_height()
        if visible_height <= 1:
            visible_height = max(180, self.content_container.winfo_height() - 40)
        return max(24, visible_height - 24)

    def _estimate_page_height(self, blocks):
        if not blocks:
            return 1

        measurement = tk.Text(self.content_container, wrap="word", state="disabled", bd=0, padx=0, pady=0, highlightthickness=0)
        measurement.configure(width=self._measure_text_width())
        self._configure_widget_tags(measurement)

        for block in blocks:
            block_type = block.get("type")
            if block_type in {"header", "subheader"}:
                measurement.insert("end", "\n", "normal")
                self._insert_segments(measurement, block.get("segments", []), default_tag=block["type"])
                measurement.insert("end", "\n\n", "normal")
            else:
                self._insert_segments(measurement, block.get("segments", []), default_tag="normal")
                if block.get("para_end", True):
                    measurement.insert("end", "\n\n", "normal")

        measurement.update_idletasks()
        line_count = int(measurement.count("1.0", "end", "displaylines")[0])
        measurement.destroy()
        return max(1, line_count)

    def _measure_text_width(self):
        self.root.update_idletasks()
        widget_width = self.text_widget.winfo_width()
        if widget_width <= 1:
            widget_width = max(240, self.content_container.winfo_width() or 720)
        try:
            padx = int(self.text_widget.cget("padx") or 0)
        except (tk.TclError, ValueError, TypeError):
            padx = 8
        scrollbar_width = self.scrollbar.winfo_width() if self.current_theme == 5 else 0
        inner_width = max(20, widget_width - (padx * 2) - scrollbar_width)
        sample = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 "
        avg_char_width = max(1, self.body_font.measure(sample) / len(sample))
        return max(20, int(inner_width / avg_char_width))

    def _block_tag(self, block_type):
        if block_type == "header":
            return "header"
        if block_type == "subheader":
            return "subheader"
        return "normal"

    def _collect_block_tokens(self, block):
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


    def add_book_files(self):
        selected = filedialog.askopenfilenames(title="Add books to BookLizard", filetypes=[("Text Documents", "*.txt"), ("Rich Text Files", "*.rtf")])
        if not selected:
            return
        password = self._prompt_password("Create encryption password")
        if not password:
            self.show_notification("No password entered", kind="error")
            return
        password_confirm = self._prompt_password("Confirm encryption password")
        if password_confirm != password:
            self.show_notification("Passwords did not match", kind="error")
            return
        self._import_paths(selected, password)

    def _import_paths(self, paths, password=None):
        if not paths:
            return
        if password is None:
            password = self._prompt_password("Create encryption password")
            if not password:
                self.show_notification("No password entered", kind="error")
                return
        copied = self.storage.copy_books(paths, password)
        if not copied:
            self.show_notification("No books added", kind="error")
            return
        self.load_book_list()
        if copied[0] in self.books:
            self.current_book = self.books.index(copied[0])
        self.load_current_book(password)
        self.close_menu()
        self.show_notification(f"Added {len(copied)} book(s)", kind="success")

    def on_resize(self, event=None):
        # Window size is fixed / only changes via an explicit preset pick
        # (see apply_screen_size), so there's no live auto-wrap-on-drag
        # to handle here anymore.
        return
        self.draw_page()

    def draw_page(self):
        self.canvas.pack_forget()
        self.text_widget.pack_forget()
        self.scrollbar.pack_forget()

        if self.menu_open:
            self.canvas.pack(fill="both", expand=True)
            self.draw_menu()
            return

        self._update_text_padding()
        self.text_widget.pack(side="left", fill="both", expand=True)
        if self.current_theme == 5:
            self.scrollbar.pack(side="right", fill="y")
        else:
            self.scrollbar.pack_forget()
        self.root.update_idletasks()
        self.draw_reader()

    def draw_reader(self):
        self.text_widget.configure(state="normal")
        self.text_widget.delete("1.0", "end")

        if not self.book_entries:
            self.text_widget.insert("end", "No books found.\n\nUse Browse to add books, or drop .txt/.rtf files onto the window.\n\nThen open the menu with ESC and select a book.", "info")
            self.page_label.configure(text="")
            self.page_arrow.configure(text="")
            self.text_widget.configure(state="disabled")
            self.text_widget.yview_moveto(0.0)
            return

        if self._needs_page_rebuild:
            self._build_content_pages(self.book_blocks)
        if self.current_page >= len(self.pages):
            self.current_page = len(self.pages) - 1

        page = self.pages[self.current_page]

        if self.debug_mode:
            widget_width = self.text_widget.winfo_width()
            widget_height = self.text_widget.winfo_height()
            inner_cols = self._measure_text_width()
            page_height_limit = self._get_page_height_limit()
            page_type = page.get("type", "unknown")
            debug_lines = [
                f"page {self.current_page + 1}/{len(self.pages)} type={page_type} theme={self.current_theme} text_size={self.text_size_level}",
                f"widget={widget_width}x{widget_height} inner_cols={inner_cols} page_limit={page_height_limit}",
            ]
            if page_type == "content":
                block_types = [b["type"] for b in page.get("blocks", [])]
                debug_lines.append(f"blocks={len(block_types)} types={block_types}")
                for index, block in enumerate(page.get("blocks", []), start=1):
                    segs = block.get("segments", [])
                    chars = sum(len(entry.get("text", "")) for entry in segs)
                    debug_lines.append(f"  {index}: {block.get('type')} segs={len(segs)} chars={chars}")
            debug_text = "\n".join(debug_lines) + "\n\n"
            self.text_widget.insert("end", debug_text, "debug")

        if page["type"] == "intro":
            self.text_widget.insert("end", page["title"] + "\n", "book_title")
            if page.get("author"):
                self.text_widget.insert("end", page["author"] + "\n\n", "book_author")
        elif page["type"] == "content":
            for block in page.get("blocks", []):
                if block["type"] in {"header", "subheader"}:
                    self.text_widget.insert("end", "\n", "normal")
                    self._insert_segments(self.text_widget, block.get("segments", []), default_tag=block["type"])
                    self.text_widget.insert("end", "\n\n", "normal")
                else:
                    self._insert_segments(self.text_widget, block.get("segments", []), default_tag="normal")
                    if block.get("para_end", True):
                        self.text_widget.insert("end", "\n\n", "normal")

        debug_suffix = " [DBG]" if self.debug_mode else ""
        self.page_label.configure(text=f"{self.current_page + 1}/{len(self.pages)}{debug_suffix}")
        self.text_widget.configure(state="disabled")
        self.text_widget.yview_moveto(0.0)
        self._update_scroll_indicator()

    def _insert_segments(self, widget, segments, default_tag="normal"):
        for entry in segments:
            text = entry.get("text", "")
            style = entry.get("style", default_tag)
            if style == "normal" and default_tag in {"header", "subheader"}:
                tag = default_tag
            else:
                tag = style if style in {"normal", "bold", "italic", "bold_italic", "header", "subheader"} else default_tag
            widget.insert("end", text, tag)

    def _on_mousewheel(self, event=None):
        # This is a paginated reader, not a scrolling one -- block wheel/
        # trackpad scroll so a page can't get dragged out of view. Theme 5
        # is the one exception that intentionally supports scrolling.
        if self.current_theme == 5:
            return None
        return "break"

    def _update_scroll_indicator(self):
        if self.current_theme != 5:
            self.page_arrow.configure(text="")
            return
        try:
            if self.text_widget.yview()[1] < 0.98:
                self.page_arrow.configure(text="↓")
            else:
                self.page_arrow.configure(text="")
        except Exception:
            self.page_arrow.configure(text="")

    def draw_menu(self):
        self.canvas.configure(bg=self.bg)
        self.content_container.configure(bg=self.bg)
        self.root.configure(bg=self.bg)
        self.canvas.delete("all")
        self.canvas.create_rectangle(0,0,self.root.winfo_width(),self.root.winfo_height(),fill=self.bg,outline=self.bg)
        width, height = self.root.winfo_width(), self.root.winfo_height()
        if self.menu_page == -1:
            self.canvas.create_text(width / 2, height / 2 - 20, text=INTRO_TEXT, font=self.body_font, fill=self.fg, anchor="center", width=max(300, width - MARGIN * 2))
            self.canvas.create_text(width / 2, height - 70, text="ESC = Close Menu | Left/Right = Switch Pages", font=self.body_font, fill=self.fg)
            self.page_label.configure(text="")
            self.page_arrow.configure(text="")
            return

        titles = {0: "Book Selector", 1: "Screen Size", 2: "Reading Settings"}
        title = titles.get(self.menu_page, "Book Selector")
        self.canvas.create_text(width / 2, 80, text=title, font=self.title_font, fill=self.fg)

        if self.menu_page == 0:
            items = self.book_entries if self.book_entries else [{"title": "No books found", "author": "", "filename": ""}]
        elif self.menu_page == 1:
            items = [{"title": p["name"], "author": "", "filename": ""} for p in self.screen_presets]
        else:
            items = [
                {"title": "Increase text size", "author": f"Current: {self.text_size_level:+d}", "filename": ""},
                {"title": "Decrease text size", "author": f"Current: {self.text_size_level:+d}", "filename": ""},
                {"title": "Reset appearance", "author": "", "filename": ""},
            ]

        y = 160
        for index, item in enumerate(items, start=1):
            label = f"{index}. {self.display_title(item)}"
            if self.menu_page == 0:
                label += f" — {self.display_author(item)}"
            if self.menu_page == 1 and index - 1 == self.current_size_index:
                label += "  (current)"
            self.canvas.create_text(width / 2, y, text=label, font=self.body_font, fill=self.fg)
            y += self.body_font.metrics("linespace") + self.spacing

        self.canvas.create_text(width / 2, height - 70, text="Left/Right = Switch Pages   |   ESC = Close Menu", font=self.body_font, fill=self.fg)
        self.page_label.configure(text="")
        self.page_arrow.configure(text="")

    def toggle_menu(self, event=None):
        if self.menu_open:
            self.close_menu()
        else:
            self.menu_open = True
            self.menu_page = 0
            self.draw_page()

    def close_menu(self):
        # The single source of truth for "closing the menu" -- this is
        # exactly what ESC does. Every menu selection should end up
        # calling this instead of hand-rolling its own menu_open=False +
        # draw_page(), so picking a book/size/text-option always behaves
        # the same as pressing ESC afterward.
        self.menu_open = False
        self.draw_page()

    def switch_menu_page(self, direction=1, event=None):
        if not self.menu_open:
            return
        if self.menu_page == -1:
            self.menu_page = 0
        else:
            options = [0, 1, 2]
            try:
                current_index = options.index(self.menu_page)
            except ValueError:
                current_index = 0
            next_index = max(0, min(len(options) - 1, current_index + direction))
            self.menu_page = options[next_index]
        self.draw_page()

    def handle_keys(self, event):
        if not self.menu_open or not event.char or not event.char.isdigit():
            return
        index = int(event.char) - 1
        if self.menu_page == 0 and 0 <= index < len(self.book_entries):
            self.current_book = index
            self.load_current_book()
            self.close_menu()
        elif self.menu_page == 1 and 0 <= index < len(self.screen_presets):
            self.apply_screen_size(index)
        elif self.menu_page == 2:
            if index == 0:
                self.adjust_text_size(1)
                self.close_menu()
            elif index == 1:
                self.adjust_text_size(-1)
                self.close_menu()
            elif index == 2:
                self.reset_appearance()
                self.close_menu()

    def apply_screen_size(self, index):
        if not (0 <= index < len(self.screen_presets)):
            return
        preset = self.screen_presets[index]
        self.current_size_index = index
        self.root.geometry(f"{preset['width']}x{preset['height']}")
        self.root.update_idletasks()
        self._needs_page_rebuild = True
        self._persist_settings()
        self.close_menu()

    def adjust_text_size(self, delta):
        self.text_size_level = max(-4, min(4, self.text_size_level + delta))
        self.apply_theme()
        self._needs_page_rebuild = True
        self.draw_page()

    def reset_appearance(self):
        self.text_size_level = 0
        self.apply_theme()
        self._needs_page_rebuild = True
        self.draw_page()

    def _persist_settings(self):
        self.storage.save_settings({
            "current_theme": self.current_theme,
            "screen_size_index": self.current_size_index,
            "text_size_level": self.text_size_level,
        })

    def on_right(self, event=None):
        if self.menu_open:
            self.switch_menu_page(1)
        else:
            self.next_page()

    def on_left(self, event=None):
        if self.menu_open:
            self.switch_menu_page(-1)
        else:
            self.prev_page()

    def toggle_debug_mode(self, event=None):
        self.debug_mode = not self.debug_mode
        self.draw_page()

    def next_page(self, event=None):
        if self.menu_open or self.current_page >= len(self.pages) - 1:
            return
        self.current_page += 1
        if self.current_book is not None:
            self.storage.save_progress(self.books[self.current_book], self.current_page)
        self.draw_page()

    def prev_page(self, event=None):
        if self.menu_open or self.current_page <= 0:
            return
        self.current_page -= 1
        if self.current_book is not None:
            self.storage.save_progress(self.books[self.current_book], self.current_page)
        self.draw_page()
