# BookLizard

BookLizard is a lightweight desktop e-reader built with Tkinter. It loads local text files, paginates them for a fixed window size, and provides simple keyboard-driven navigation, optional book encryption, and screen preset controls.

---

## Overview

Use `BookLizard` to read `.txt` and `.rtf` books from a small local library. The app displays one page at a time and lets you move through content with the arrow keys. It also supports a menu for choosing books, switching between preset window sizes, and adjusting text size.

## Quick Start

1. Install Python 3.
2. Install the one external dependency:

   ```bash
   pip install cryptography
   ```

3. Run the app from the project root:

   ```bash
   python3 -m booklizard.main
   ```

4. Drop text files into the window or click `Browse & Add` to add books.
5. Use `ESC` to open and close the menu.
6. Use `Left` / `Right` arrows to switch pages when reading, and to switch menu pages when the menu is open.

---

## Features

- **Book selector**: choose from available books stored in the app library.
- **Screen size presets**: switch the app window to one of several fixed sizes (1280×720, 1366×768, 1440×900, 1920×1080).
- **Reading settings**: increase/decrease text size or reset appearance back to default.
- **Book encryption**: every book added via drag-and-drop or `Browse & Add` is encrypted at rest with a password you set (Fernet + PBKDF2), and prompts for that password again when you open it.
- **Persistent progress and settings**: the app remembers the last read page per book, plus your theme, text size, and screen size across launches.
- **Inline formatting**: supports basic bold and italic markers, plus headers/subheaders, in source text.
- **Drag-and-drop file import**: drop supported book files directly onto the window.
- **Debug overlay**: press `F3` to toggle a small on-page debug readout (page index, theme, text size).

## Supported file formats

- `.txt`
- `.rtf`

Files are copied (and encrypted) into the app's local library under `~/Library/Application Support/BookLizard/books` on macOS. Progress, settings, and metadata live alongside it in the same `BookLizard` folder.

## File formatting

The book parser extracts optional title and author metadata from the top of each file.

Block formatting uses a prefix/suffix heading style with `#` counts:

- `!# Title text #!` or `!# Title text` for the book title
- `~# Author name` for the author
- `!## Header text ##!` or `!## Header text` for section headers
- `!### Subheader text ###!` or `!### Subheader text` for subheaders

Inline text formatting is supported using the following markers:

- `@@# ... $$#` for bold
- `@# ... $#` (or `#$`) for italic

Example:

```text
!# My Story
~# Jane Doe

This is a normal paragraph.

!## Chapter 1

@@#This text is bold.$$# And @#this text is italic.$#
```

## Controls

- `ESC` — open/close the menu
- `Left` — previous page / previous menu page
- `Right` — next page / next menu page
- `1`, `2`, `3`, ... — select a book/size/setting in the menu
- `F3` — toggle debug overlay
- `Browse & Add` — open a file dialog to import books (you'll be asked to set an encryption password)

### Menu pages

Cycle through these with `Left`/`Right` while the menu is open:

1. **Book Selector** — pick which book to read
2. **Screen Size** — pick a fixed window size
3. **Reading Settings** — increase/decrease text size, or reset appearance

> Note: the in-app welcome text still mentions a "Theme Changer" menu page, but there's currently no menu screen for switching reading themes (Classic, Warm Tan, Dark Mode, Soft Mint, Open Dyslexic) — `current_theme` is only changeable by editing the saved settings file directly. Worth knowing if you go looking for it in the UI.

## Project structure

- `main.py` / `__main__.py` — app entry points
- `ui.py` — main Tkinter UI, menu, and navigation logic
- `layout_engine.py` — measures and lays out text for pagination
- `pagination.py` — book parsing (title/author/headers/inline formatting)
- `storage.py` — local library, encryption, progress, and settings persistence
- `themes.py` — theme definitions
- `config.py` — app constants, window settings, and screen presets
- `utils.py` — utility helpers
- `tests/` — unit tests for config and layout engine

## Notes

- The app window is locked to preset sizes rather than allowing free manual resizing.
- Pagination is recomputed whenever the window size, text size, or current book changes.
- Encrypted books use Fernet symmetric encryption with a PBKDF2-derived key (390,000 iterations); decrypted content is cached locally after a correct password so you aren't re-prompted every page turn.
- Progress files are stored under `~/Library/Application Support/BookLizard/progress`.

---

## Development

To extend the app:

- Add new themes in `themes.py`
- Add new screen presets in `config.py`
- Modify parsing rules in `pagination.py`
- Adjust UI behavior in `ui.py`

Run the test suite from the `booklizard` package directory:

```bash
python3 -m unittest discover -s booklizard/tests
```
