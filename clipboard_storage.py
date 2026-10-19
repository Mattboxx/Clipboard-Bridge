"""Small, fail-safe JSON history persistence shared by the Python applications.

Callers own their store lock. A missing index starts a new history; an unreadable
or malformed existing index must never be mistaken for an empty one.
"""

import json
import os
import tempfile


class HistoryStoreError(OSError):
    """A history operation could not safely read or commit its index."""

    def __init__(self, reason):
        self.reason = reason
        super().__init__(
            "History is unavailable. Existing data was preserved. "
            "Check storage permissions or restore the index from a backup."
        )


def _validate_history(index):
    if not isinstance(index, list) or any(not isinstance(item, dict) for item in index):
        raise HistoryStoreError("invalid_index")


def read_history(path):
    """Read a legacy-compatible list of entries, failing closed on storage errors."""
    try:
        with open(path, "r", encoding="utf-8") as stream:
            index = json.load(stream)
    except FileNotFoundError:
        return []
    except (json.JSONDecodeError, UnicodeError) as error:
        raise HistoryStoreError("invalid_index") from error
    except OSError as error:
        raise HistoryStoreError("read_failed") from error
    _validate_history(index)
    return index


def write_history(path, index):
    """Replace an index only after a complete, flushed temporary write succeeds."""
    _validate_history(index)
    path = os.fspath(path)
    parent = os.path.dirname(os.path.abspath(path))
    temporary = None
    try:
        os.makedirs(parent, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", newline="\n", dir=parent,
            prefix="." + os.path.basename(path) + "-", suffix=".tmp", delete=False,
        ) as stream:
            temporary = stream.name
            json.dump(index, stream, ensure_ascii=False, indent=2)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
        temporary = None
    except (OSError, TypeError, ValueError) as error:
        raise HistoryStoreError("write_failed") from error
    finally:
        if temporary is not None:
            try:
                os.unlink(temporary)
            except OSError:
                pass
