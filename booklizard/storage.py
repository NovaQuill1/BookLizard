import base64
import json
import os
import shutil
from .config import APP_SUPPORT_ROOT, BOOK_METADATA_FILENAME, DECRYPTED_BOOKS_FILENAME, VALID_EXTENSIONS
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

ENCRYPTION_MAGIC = b"BOOKLIZARD-FERNET\n"
ENCRYPTION_PREFIX = b"BOOKLIZARD-UNLOCKED\n"
KDF_ITERATIONS = 390000


class IncorrectPasswordError(Exception):
    pass


class StorageManager:
    def __init__(self):
        self.base_path = APP_SUPPORT_ROOT
        self.books_path = os.path.join(self.base_path, "books")
        self.progress_path = os.path.join(self.base_path, "progress")
        self.settings_path = os.path.join(self.base_path, "settings.json")
        self.metadata_path = os.path.join(self.base_path, BOOK_METADATA_FILENAME)
        self.decrypted_list_path = os.path.join(self.base_path, DECRYPTED_BOOKS_FILENAME)
        self.cache_path = os.path.join(self.base_path, ".cache")
        os.makedirs(self.books_path, exist_ok=True)
        os.makedirs(self.progress_path, exist_ok=True)
        os.makedirs(self.cache_path, exist_ok=True)
        self._migrate_workspace_books()
        self._ensure_hidden_files()

    def _migrate_workspace_books(self):
        workspace_books = os.path.abspath(
            os.path.join(os.path.dirname(__file__), "..", "books")
        )
        if not os.path.isdir(workspace_books):
            return

        for filename in os.listdir(workspace_books):
            lower = filename.lower()
            if any(lower.endswith(ext) for ext in VALID_EXTENSIONS):
                source = os.path.join(workspace_books, filename)
                target = os.path.join(self.books_path, filename)
                if not os.path.exists(target):
                    try:
                        shutil.copy2(source, target)
                    except Exception:
                        pass

    def _ensure_hidden_files(self):
        for path in (self.settings_path, self.metadata_path, self.decrypted_list_path):
            if not os.path.exists(path):
                try:
                    with open(path, "w", encoding="utf-8") as f:
                        json.dump({}, f) if path != self.decrypted_list_path else f.write("[]")
                except Exception:
                    pass
            try:
                os.chmod(path, 0o600)
            except Exception:
                pass
        try:
            os.chmod(self.cache_path, 0o700)
        except Exception:
            pass

    def get_books(self):
        return sorted(
            [f for f in os.listdir(self.books_path) if f.lower().endswith(VALID_EXTENSIONS)],
            key=lambda name: name.lower(),
        )

    def _derive_key(self, password, salt):
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=KDF_ITERATIONS,
        )
        return base64.urlsafe_b64encode(kdf.derive(password.encode("utf-8")))

    def _encrypt_payload(self, data, password):
        salt = os.urandom(16)
        key = self._derive_key(password, salt)
        token = Fernet(key).encrypt(ENCRYPTION_PREFIX + data)
        return ENCRYPTION_MAGIC + salt + token

    def _decrypt_payload(self, encrypted_data, password):
        if not encrypted_data.startswith(ENCRYPTION_MAGIC):
            raise IncorrectPasswordError("Not an encrypted book")
        salt = encrypted_data[len(ENCRYPTION_MAGIC): len(ENCRYPTION_MAGIC) + 16]
        token = encrypted_data[len(ENCRYPTION_MAGIC) + 16:]
        key = self._derive_key(password, salt)
        try:
            decrypted = Fernet(key).decrypt(token)
        except InvalidToken:
            raise IncorrectPasswordError("Incorrect password")
        if not decrypted.startswith(ENCRYPTION_PREFIX):
            raise IncorrectPasswordError("Encrypted book validation failed")
        return decrypted[len(ENCRYPTION_PREFIX):]

    def load_book(self, filename, password=None):
        if self.is_book_decrypted(filename):
            try:
                return self.load_cached_decrypted_book(filename)
            except Exception:
                pass

        path = os.path.join(self.books_path, filename)
        with open(path, "rb") as f:
            raw = f.read()

        if raw.startswith(ENCRYPTION_MAGIC):
            if password is None:
                raise IncorrectPasswordError("Password required")
            plaintext = self._decrypt_payload(raw, password)
            return plaintext.decode("utf-8", errors="replace")

        return raw.decode("utf-8", errors="replace")

    def is_encrypted(self, filename):
        path = os.path.join(self.books_path, filename)
        try:
            with open(path, "rb") as f:
                raw = f.read(len(ENCRYPTION_MAGIC) + 16)
            return raw.startswith(ENCRYPTION_MAGIC)
        except Exception:
            return False

    def load_book_metadata(self, filename, password=None):
        title = None
        author = None
        metadata = self._load_metadata()

        if filename in metadata:
            title = metadata[filename].get("title")
            author = metadata[filename].get("author")
        else:
            try:
                raw = self.load_book(filename, password=password)
            except IncorrectPasswordError:
                raw = None

            if raw is not None:
                for line in raw.splitlines():
                    stripped = line.strip()
                    if stripped.startswith("!###"):
                        continue
                    if stripped.startswith("!##"):
                        continue
                    if stripped.startswith("!#") and not stripped.startswith("!##"):
                        title = stripped[2:].strip()
                        continue
                    if stripped.startswith("~#"):
                        author = stripped[2:].strip()
                        continue
                    if title is not None and author is not None:
                        break

        if title is None:
            title = os.path.splitext(filename)[0]
            if title.lower().endswith(".txt") or title.lower().endswith(".rtf"):
                title = os.path.splitext(title)[0]
            if title.lower().endswith(".enc"):
                title = os.path.splitext(title)[0]
        if author is None:
            author = "Author Unknown"

        return {
            "filename": filename,
            "title": title,
            "author": author,
        }

        for line in raw.splitlines():
            stripped = line.strip()
            if stripped.startswith("!###"):
                continue
            if stripped.startswith("!##"):
                continue
            if stripped.startswith("!#") and not stripped.startswith("!##"):
                title = stripped[2:].strip()
                continue
            if stripped.startswith("~#"):
                author = stripped[2:].strip()
                continue
            if title is not None and author is not None:
                break

        return {
            "filename": filename,
            "title": title or os.path.splitext(filename)[0],
            "author": author or "Author Unknown",
        }

    def save_progress(self, filename, page_index):
        if not filename:
            return
        path = os.path.join(self.progress_path, f"{filename}.progress")
        with open(path, "w", encoding="utf-8") as f:
            f.write(str(page_index))

    def _load_metadata(self):
        try:
            with open(self.metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _save_metadata(self, data):
        try:
            with open(self.metadata_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.chmod(self.metadata_path, 0o600)
        except Exception:
            pass

    def _cache_path(self, filename):
        safe_name = os.path.basename(filename).replace(os.sep, "_").replace("/", "_")
        return os.path.join(self.cache_path, f".{safe_name}.unlock")

    def save_cached_decrypted_book(self, filename, plaintext):
        if not filename or not plaintext:
            return False
        cache_path = self._cache_path(filename)
        try:
            with open(cache_path, "w", encoding="utf-8") as handle:
                handle.write(plaintext)
            os.chmod(cache_path, 0o600)
            return True
        except Exception:
            return False

    def load_cached_decrypted_book(self, filename):
        if not filename:
            raise FileNotFoundError("No filename supplied")
        cache_path = self._cache_path(filename)
        if not os.path.exists(cache_path):
            raise FileNotFoundError("No cached decrypt found")
        with open(cache_path, "r", encoding="utf-8") as handle:
            return handle.read()

    def _load_decrypted_list(self):
        try:
            with open(self.decrypted_list_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, list) else []
        except Exception:
            return []

    def _save_decrypted_list(self, items):
        try:
            with open(self.decrypted_list_path, "w", encoding="utf-8") as f:
                json.dump(items, f, indent=2)
            os.chmod(self.decrypted_list_path, 0o600)
        except Exception:
            pass

    def is_book_decrypted(self, filename):
        return filename in self.get_decrypted_books()

    def record_decrypted_book(self, filename, plaintext=None):
        items = self._load_decrypted_list()
        if filename not in items:
            items.append(filename)
            self._save_decrypted_list(items)
        if plaintext is not None:
            self.save_cached_decrypted_book(filename, plaintext)

    def get_decrypted_books(self):
        return self._load_decrypted_list()

    def load_settings(self):
        if not os.path.exists(self.settings_path):
            return {}
        try:
            with open(self.settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def save_settings(self, settings):
        try:
            with open(self.settings_path, "w", encoding="utf-8") as f:
                json.dump(settings, f, indent=2)
        except Exception:
            pass

    def load_progress(self, filename):
        if not filename:
            return 0
        path = os.path.join(self.progress_path, f"{filename}.progress")
        if not os.path.exists(path):
            with open(path, "w", encoding="utf-8") as f:
                f.write("0")
            return 0
        try:
            with open(path, "r", encoding="utf-8") as f:
                return int(f.read().strip() or 0)
        except ValueError:
            return 0
        except Exception:
            return 0

    def copy_books(self, file_paths, password):
        copied = []
        for path in file_paths:
            if not path:
                continue
            normalized = os.path.expanduser(path)
            if not os.path.isfile(normalized):
                continue
            destination_name = os.path.basename(normalized) + ".enc"
            destination = os.path.join(self.books_path, destination_name)
            destination = self._unique_destination(destination)
            try:
                with open(normalized, "rb") as source_file:
                    data = source_file.read()
                encrypted = self._encrypt_payload(data, password)
                with open(destination, "wb") as dest_file:
                    dest_file.write(encrypted)
                copied.append(os.path.basename(destination))
            except Exception:
                continue
        return copied

    def _unique_destination(self, destination):
        base, ext = os.path.splitext(destination)
        counter = 1
        while os.path.exists(destination):
            destination = f"{base}-{counter}{ext}"
            counter += 1
        return destination
