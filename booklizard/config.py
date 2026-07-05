import os

WIDTH = 1280
HEIGHT = 720
MARGIN = 80
TITLE_TEXT = "BookLizard: Portable E-Reader"
INTRO_TEXT = (
    "Welcome to BookLizard!\n\n"
    "Use the arrow keys to turn pages.\n"
    "In the menu, use the left/right arrows to switch between Book Selector, Theme Changer, and Screen Size.\n"
    "Press ESC to open or close this menu at any time.\n\n"
    "Drop text files onto the window or use Browse to add books.\n"
    "Happy reading!"
)
VALID_EXTENSIONS = (".txt", ".rtf", ".enc")
ICON_FILENAME = "icon.icns"
APP_SUPPORT_ROOT = os.path.join(os.path.expanduser("~"), "Library", "Application Support", "BookLizard")
DECRYPTED_BOOKS_FILENAME = ".decrypted_books.json"
BOOK_METADATA_FILENAME = ".book_metadata.json"

# The window no longer freely resizes/auto-wraps -- it's locked at WIDTH x
# HEIGHT by default, and can only switch to one of these known preset
# sizes (picked from the Screen Size menu). Pagination is computed fresh
# for whichever fixed size is active, instead of recalculating live while
# dragging a resize handle.
SCREEN_PRESETS = [
    {"name": "1280 x 720", "width": 1280, "height": 720},
    {"name": "1366 x 768", "width": 1366, "height": 768},
    {"name": "1440 x 900", "width": 1440, "height": 900},
    {"name": "1920 x 1080", "width": 1920, "height": 1080},
]
