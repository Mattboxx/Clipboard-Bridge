#!/usr/bin/env python3
"""Linux desktop client. Network and clipboard helpers run off the Tk thread."""

import argparse
import base64
import io
import os
import queue
import shutil
import subprocess
import tempfile
import threading
import tkinter as tk
from contextlib import contextmanager
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from urllib.parse import quote, unquote

from clipboard_linux_shortcuts import ShortcutListener, forward, runtime_path
from clipboard_linux_transport import Connection, clipboard_text, sync_text


PALETTES = {
    "dark": ("#121a22", "#1d2934", "#edf5fa", "#adbdcb", "#385973", "#23485b", "#304352"),
    "light": ("#edf2f5", "#ffffff", "#192a36", "#465e70", "#c9dfed", "#d7ece7", "#bfced8"),
}
KINDS = {"All": "", "Text": "text", "Images": "image", "Files": "file", "Groups": "bundle"}


def render_preview(data, kind, mime, name, bounds):
    if kind == "text":
        return "text", data.decode("utf-8", errors="replace")
    if kind != "image" and mime != "application/pdf" and not name.lower().endswith(".pdf"):
        return "text", name
    try:
        from PIL import Image

        if kind == "image":
            with Image.open(io.BytesIO(data)) as source:
                source.thumbnail(bounds)
                image = source.convert("RGBA")
        elif shutil.which("pdftoppm"):
            with tempfile.TemporaryDirectory(prefix="clipboard-preview-") as directory:
                output_path = Path(directory) / "page"
                subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-singlefile", "-png",
                                "-scale-to", str(max(bounds)), "-", str(output_path)],
                               input=data, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                               timeout=10, check=True)
                with Image.open(output_path.with_suffix(".png")) as source:
                    source.thumbnail(bounds)
                    image = source.convert("RGBA")
        else:
            import pypdfium2

            with pypdfium2.PdfDocument(data) as document:
                page = document[0]
                try:
                    scale = min(2, bounds[0] / page.get_width(), bounds[1] / page.get_height())
                    bitmap = page.render(scale=scale)
                    try:
                        image = bitmap.to_pil().copy()
                    finally:
                        bitmap.close()
                finally:
                    page.close()
        output = io.BytesIO()
        image.save(output, format="PNG")
        return "image", output.getvalue()
    except ImportError:
        return "text", f"{name}\n\nInstall Pillow and Poppler for image and PDF previews."


class Desktop:
    def __init__(self, root, listener=None):
        self.root = root
        self.style = ttk.Style(root)
        self.style.theme_use("clam")
        self.theme = "dark"
        self.results = queue.Queue()
        self.client = None
        self.auth = {}
        self.busy = False
        self.modal_open = False
        self.closed = False
        self.last_saved = None
        self.image = None
        self.listener = listener
        self.sync_state = None
        self.sync_enabled = tk.BooleanVar(value=False)
        self.address = tk.StringVar(value=os.environ.get("CB_URL", ""))
        self.query = tk.StringVar()
        self.kind = tk.StringVar(value="All")
        self.status = tk.StringVar(value="Not connected")
        self.summary = tk.StringVar(value="No items loaded")
        self.buttons = []
        self.selection_buttons = []

        root.title("Clipboard Bridge")
        root.geometry("980x600")
        root.minsize(660, 450)
        root.protocol("WM_DELETE_WINDOW", self.close)

        shell = ttk.Frame(root, padding=18)
        shell.pack(fill="both", expand=True)
        header = ttk.Frame(shell)
        header.pack(fill="x", pady=(0, 12))
        ttk.Label(header, text="Clipboard Bridge", style="Title.TLabel").pack(side="left")
        self.theme_button = self.button(header, "Light theme", self.toggle_theme,
                                        side="right", tracked=False)
        self.button(header, "Connection settings", self.connection_settings, side="right")

        connection = ttk.Frame(shell)
        connection.pack(fill="x", pady=(0, 12))
        ttk.Label(connection, text="Server address").pack(side="left", padx=(0, 8))
        self.address_input = ttk.Entry(connection, textvariable=self.address)
        self.address_input.pack(side="left", fill="x", expand=True, ipady=5)
        self.address_input.bind("<Return>", lambda _: self.connect())
        self.connect_button = self.button(connection, "Connect", self.connect)

        actions = ttk.Frame(shell)
        actions.pack(fill="x", pady=(0, 12))
        self.send_button = self.button(actions, "Send clipboard", self.send_clipboard)
        self.files_button = self.button(actions, "Send files", self.send_files)
        self.receive_button = self.button(actions, "Receive latest", self.receive_latest)
        self.receive_button.configure(style="Accent.TButton")
        self.refresh_button = self.button(actions, "Refresh", self.refresh, side="right")
        self.sync_button = ttk.Checkbutton(actions, text="Auto-sync text",
                                           variable=self.sync_enabled, command=self.reset_sync)
        self.sync_button.pack(side="right", padx=(0, 6))
        self.buttons.append(self.sync_button)

        panes = ttk.Panedwindow(shell, orient="horizontal")
        panes.pack(fill="both", expand=True)
        history = ttk.Frame(panes, padding=(0, 0, 10, 0))
        details = ttk.Frame(panes, padding=(10, 0, 0, 0))
        panes.add(history, weight=3)
        panes.add(details, weight=2)

        ttk.Label(history, text="Server history", style="Section.TLabel").pack(anchor="w")
        filters = ttk.Frame(history)
        filters.pack(fill="x", pady=8)
        search = ttk.Entry(filters, textvariable=self.query)
        search.pack(side="left", fill="x", expand=True)
        search.bind("<Return>", lambda _: self.refresh())
        filter_box = ttk.Combobox(filters, textvariable=self.kind, values=list(KINDS),
                                  width=8, state="readonly")
        filter_box.pack(side="left", padx=(6, 0))
        filter_box.bind("<<ComboboxSelected>>", lambda _: self.refresh())
        self.button(filters, "Search", self.refresh)
        table = ttk.Frame(history)
        table.pack(fill="both", expand=True)
        self.tree = ttk.Treeview(table, columns=("type", "item"), show="headings",
                                 selectmode="browse", height=8)
        self.tree.heading("type", text="Type")
        self.tree.heading("item", text="Item")
        self.tree.column("type", width=82, minwidth=72, stretch=False)
        self.tree.column("item", width=255, minwidth=130)
        yscroll = ttk.Scrollbar(table, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=yscroll.set)
        self.tree.pack(side="left", fill="both", expand=True)
        yscroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", lambda _: self.selection_changed())
        self.tree.bind("<Double-1>", lambda _: self.preview_item())
        ttk.Label(history, textvariable=self.summary, style="Muted.TLabel").pack(anchor="w", pady=(6, 0))

        ttk.Label(details, text="Preview", style="Section.TLabel").pack(anchor="w", pady=(0, 8))
        preview_frame = ttk.Frame(details)
        preview_frame.pack(fill="both", expand=True)
        self.preview = tk.Text(preview_frame, height=8, width=20, wrap="word", bd=0,
                               padx=12, pady=10, highlightthickness=0, state="disabled")
        preview_scroll = ttk.Scrollbar(preview_frame, orient="vertical", command=self.preview.yview)
        self.preview.configure(yscrollcommand=preview_scroll.set)
        self.preview.pack(side="left", fill="both", expand=True)
        preview_scroll.pack(side="right", fill="y")
        selected = ttk.Frame(details)
        selected.pack(fill="x", pady=(8, 0))
        for label, command in (("Preview", self.preview_item), ("Receive", self.receive_selected),
                               ("Delete", self.delete_selected)):
            self.selection_buttons.append(self.button(selected, label, command))
        saved = ttk.Frame(details)
        saved.pack(fill="x", pady=(6, 0))
        self.open_button = self.button(saved, "Open file", lambda: self.open_saved(False))
        self.folder_button = self.button(saved, "Open folder", lambda: self.open_saved(True))

        ttk.Separator(shell).pack(fill="x", pady=(10, 7))
        ttk.Label(shell, textvariable=self.status, style="Muted.TLabel", wraplength=600).pack(anchor="w")
        root.bind("<F5>", lambda _: self.refresh())
        root.bind("<Control-Shift-S>", lambda _: self.send_clipboard())
        root.bind("<Control-Shift-R>", lambda _: self.receive_latest())
        root.bind("<Control-q>", lambda _: self.close())
        self.paint()
        self.show_text("Select an item to preview its contents.")
        self.address.trace_add("write", self.address_changed)
        self.update_controls()
        self.timer = root.after(35, self.pump)
        self.sync_timer = root.after(2000, self.poll_sync)

    def button(self, parent, label, command, *, side="left", tracked=True):
        widget = ttk.Button(parent, text=label, command=command)
        widget.pack(side=side, padx=(0, 6) if side == "left" else (6, 0))
        if tracked:
            self.buttons.append(widget)
        return widget

    def paint(self):
        bg, panel, fg, muted, hover, select, border = PALETTES[self.theme]
        self.style.configure(".", background=bg, foreground=fg, bordercolor=border,
                             lightcolor=border, darkcolor=border, troughcolor=bg,
                             arrowcolor=muted)
        self.style.configure("Title.TLabel", font=("TkDefaultFont", 21, "bold"))
        self.style.configure("Section.TLabel", font=("TkDefaultFont", 11, "bold"))
        self.style.configure("Muted.TLabel", foreground=muted)
        self.style.configure("TButton", padding=(8, 5), background=panel)
        self.style.map("TButton", background=[("pressed", select), ("active", hover)],
                       foreground=[("disabled", muted)], bordercolor=[("focus", muted)])
        self.style.configure("Accent.TButton", background=select)
        for style in ("TEntry", "TCombobox", "Treeview"):
            self.style.configure(style, fieldbackground=panel, background=panel, foreground=fg,
                                 insertcolor=fg)
        self.style.map("TEntry", bordercolor=[("focus", muted)])
        self.style.map("TCombobox", fieldbackground=[("readonly", panel)])
        self.style.configure("Treeview", rowheight=29)
        self.style.map("Treeview", background=[("selected", select)], foreground=[("selected", fg)])
        self.style.configure("Treeview.Heading", background=bg, foreground=fg, padding=(5, 4))
        self.style.map("Treeview.Heading", background=[("active", hover)])
        self.style.configure("Vertical.TScrollbar", background=border, arrowsize=12, gripcount=0)
        self.style.map("Vertical.TScrollbar", background=[("active", hover)])
        self.preview.configure(background=panel, foreground=fg, selectbackground=hover,
                               selectforeground=fg, font="TkDefaultFont")

    def toggle_theme(self):
        self.theme = "light" if self.theme == "dark" else "dark"
        self.theme_button.configure(text="Light theme" if self.theme == "dark" else "Dark theme")
        self.paint()

    def connection_settings(self):
        dialog = tk.Toplevel(self.root)
        dialog.title("Connection settings")
        dialog.transient(self.root)
        frame = ttk.Frame(dialog, padding=16)
        frame.pack(fill="both", expand=True)
        auth = self.auth or {}
        entries = []
        for row, (label, key) in enumerate((("Username", "X-Clipboard-User"),
                                           ("Password", "X-Clipboard-Password"),
                                           ("Shared token", "X-Auth-Token"))):
            ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=5)
            var = tk.StringVar(value=auth.get(key, ""))
            ttk.Entry(frame, textvariable=var, show="*" if row else "", width=32).grid(
                row=row, column=1, pady=5)
            entries.append(var)

        def apply():
            user, password, token = (var.get() for var in entries)
            if bool(user) != bool(password) or (user and token):
                messagebox.showerror("Connection settings", "Enter an account or a shared token, not both.",
                                     parent=dialog)
                return
            self.auth = ({"X-Clipboard-User": user, "X-Clipboard-Password": password} if user
                         else {"X-Auth-Token": token} if token else {})
            dialog.destroy()
            self.connect()

        ttk.Button(frame, text="Connect", command=apply).grid(row=3, column=1, sticky="e", pady=(8, 0))
        dialog.bind("<Escape>", lambda _: dialog.destroy())
        dialog.grab_set()

    def selection(self):
        selected = self.tree.selection()
        return selected[0] if selected else None

    def selection_changed(self):
        self.update_controls()

    def address_changed(self, *_):
        self.client = None
        self.auth = {}
        self.sync_enabled.set(False)
        self.reset_sync()
        self.load_history({"items": []})
        self.show_text("Select an item to preview its contents.")
        self.status.set("Not connected")

    def update_controls(self):
        for button in self.buttons:
            button.state(["disabled"] if self.busy else ["!disabled"])
        for button in (self.send_button, self.files_button, self.receive_button, self.refresh_button,
                       self.sync_button):
            if not self.client:
                button.state(["disabled"])
        for button in self.selection_buttons:
            if not self.client or not self.selection():
                button.state(["disabled"])
        for button in (self.open_button, self.folder_button):
            if not self.last_saved:
                button.state(["disabled"])
        self.address_input.state(["disabled"] if self.busy else ["!disabled"])

    def start(self, label, work, done):
        if self.busy or self.closed or self.modal_open:
            return
        self.busy = True
        if label:
            self.status.set(label)
        self.update_controls()

        def worker():
            try:
                self.results.put((done, work(), None))
            except Exception as error:
                self.results.put((done, None, str(error)))

        threading.Thread(target=worker, daemon=True).start()

    def pump(self):
        if (self.listener and not self.modal_open and not self.root.grab_current()
                and (command := self.listener.take())):
            if command == "show" or command == "toggle" and self.root.state() != "normal":
                self.root.deiconify()
                self.root.lift()
            elif command == "toggle":
                self.root.withdraw()
            elif command == "send":
                self.send_clipboard()
            elif command == "receive":
                self.receive_latest()
        try:
            done, value, error = self.results.get_nowait()
        except queue.Empty:
            pass
        else:
            self.busy = False
            self.update_controls()
            if error is not None:
                self.status.set(error)
            else:
                try:
                    done(value)
                except (KeyError, TypeError, ValueError, tk.TclError) as error:
                    self.status.set(f"Could not display the server response: {error}")
        if not self.closed:
            self.timer = self.root.after(35, self.pump)

    def close(self):
        self.closed = True
        self.root.after_cancel(self.timer)
        self.root.after_cancel(self.sync_timer)
        self.root.destroy()

    def reset_sync(self):
        self.sync_state = None

    @contextmanager
    def modal_dialog(self):
        self.modal_open = True
        try:
            yield
        finally:
            self.modal_open = False

    def poll_sync(self):
        self.sync_timer = self.root.after(2000, self.poll_sync)
        if (not self.client or self.busy or self.modal_open or self.root.grab_current()
                or not self.sync_enabled.get()):
            return
        client, state = self.client, self.sync_state

        def done(result):
            self.sync_state, status = result
            if status:
                self.refresh(status)

        self.start(None, lambda: sync_text(client, state, clipboard_text), done)

    def connect(self):
        if self.busy:
            return
        address, auth = self.address.get().strip(), self.auth
        if not address:
            self.status.set("Enter a server address.")
            return
        self.client = None
        self.sync_enabled.set(False)
        self.reset_sync()
        self.load_history({"items": []})
        self.show_text("Select an item to preview its contents.")

        def work():
            client = Connection(address, auth)
            return client, client.history(100)

        def done(value):
            client, page = value
            if address != self.address.get().strip():
                return
            self.client = client
            self.load_history(page)
            warning = " (HTTP is unencrypted)" if self.client.base.startswith("http://") else ""
            self.status.set("Connected" + warning)

        self.start("Connecting...", work, done)

    def load_history(self, page):
        current = self.selection()
        self.tree.delete(*self.tree.get_children())
        rows = page["items"]
        for item in rows:
            name = item.get("filename") or item.get("preview") or ""
            clean = " ".join(name.split())
            self.tree.insert("", "end", iid=item["id"], values=(item["type"].title(), clean))
        if current and self.tree.exists(current):
            self.tree.selection_set(current)
        self.summary.set(f"{len(rows)} of {page.get('total', len(rows))} items")
        self.update_controls()

    def refresh(self, status="History refreshed"):
        if not self.client or self.busy:
            return
        client, search, kind = self.client, self.query.get(), KINDS[self.kind.get()]

        def done(page):
            self.load_history(page)
            self.status.set(status)

        self.start("Loading history...", lambda: client.history(100, search=search, kind=kind), done)

    def send_clipboard(self):
        if not self.client or self.busy:
            return
        client = self.client

        def work():
            data = clipboard_text()
            if not data or b"\x00" in data:
                raise ValueError("The clipboard does not contain text. Use Send files for attachments.")
            data.decode("utf-8")
            client.send_text(data)

        def done(_):
            self.reset_sync()
            self.refresh("Clipboard sent")

        self.start("Sending clipboard...", work, done)

    def send_files(self):
        if not self.client or self.busy:
            return
        with self.modal_dialog():
            paths = [Path(name) for name in filedialog.askopenfilenames(parent=self.root)]
        if paths:
            client = self.client
            self.start("Sending files...", lambda: client.send_files(paths),
                       lambda _: self.refresh("Files sent"))

    def receive_latest(self):
        self.fetch(None)

    def receive_selected(self):
        if item_id := self.selection():
            self.fetch(item_id)

    def preview_item(self):
        if item_id := self.selection():
            self.fetch(item_id, preview=True)

    def fetch(self, item_id, *, preview=False):
        if not self.client or self.busy:
            return
        client = self.client
        bounds = (max(64, self.preview.winfo_width() - 24),
                  max(64, self.preview.winfo_height() - 20))

        def work():
            data, headers = client.item(item_id)
            kind = headers.get("x-clipboard-type")
            if not kind:
                raise ValueError("No clipboard item is available.")
            mime = headers.get("content-type", "").split(";", 1)[0]
            name = unquote(headers.get("x-clipboard-filename", "")).replace("\\", "/").rsplit("/", 1)[-1]
            name = "".join(ch for ch in name if ch.isprintable()).strip()
            if name in ("", ".", ".."):
                name = "clipboard-item"
            if preview:
                return render_preview(data, kind, mime, name, bounds)
            if kind == "text":
                clipboard_text(data)
                return "text", data.decode("utf-8", errors="replace")
            return "file", (data, name)

        def done(result):
            kind, value = result
            if kind == "file":
                self.save_download(*value)
            elif kind == "image":
                self.show_image(value)
                self.status.set("Preview loaded")
            else:
                if not preview:
                    self.reset_sync()
                self.show_text(value)
                self.status.set("Preview loaded" if preview else "Copied to the clipboard")

        self.start("Loading item...", work, done)

    def show_text(self, value):
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.image = None
        self.preview.insert("1.0", value)
        self.preview.configure(state="disabled")

    def show_image(self, value):
        self.show_text("")
        self.image = tk.PhotoImage(master=self.root, data=base64.b64encode(value))
        self.preview.configure(state="normal")
        self.preview.image_create("1.0", image=self.image)
        self.preview.configure(state="disabled")

    def save_download(self, data, name):
        with self.modal_dialog():
            selected = filedialog.asksaveasfilename(parent=self.root, initialfile=name)
        if not selected:
            self.status.set("Save cancelled")
            return
        path = Path(selected)

        def done(_):
            self.last_saved = path
            self.update_controls()
            self.status.set(f"Saved {path.name}")

        self.start("Saving file...", lambda: path.write_bytes(data), done)

    def open_saved(self, folder):
        if self.last_saved:
            target = self.last_saved.parent if folder else self.last_saved

            def work():
                subprocess.run(["xdg-open", str(target)], check=True, timeout=30)

            self.start("Opening...", work,
                       lambda _: self.status.set(f"Opened {target.name}"))

    def delete_selected(self):
        item_id = self.selection()
        if not self.client or not item_id or self.busy:
            return
        with self.modal_dialog():
            if not messagebox.askyesno("Delete item", "Delete this item from the server history?", parent=self.root):
                return
        client = self.client

        def done(_):
            self.show_text("Select an item to preview its contents.")
            self.refresh("Item deleted")

        self.start("Deleting item...", lambda: client.request("DELETE", f"/clipboard/item/{quote(item_id, safe='')}"),
                   done)


def main():
    parser = argparse.ArgumentParser(description="Clipboard Bridge desktop app")
    actions = parser.add_mutually_exclusive_group()
    for action in ("send", "receive", "toggle"):
        actions.add_argument(f"--{action}", action="store_const", const=action, dest="command")
    command = parser.parse_args().command
    path = runtime_path()
    if forward(path, command or "show"):
        return
    if command:
        parser.exit(1, "Open Clipboard Bridge before using desktop shortcuts.\n")
    listener = None
    if path is not None:
        try:
            listener = ShortcutListener(path)
        except BlockingIOError:
            return
    try:
        root = tk.Tk()
        Desktop(root, listener)
        root.mainloop()
    finally:
        if listener:
            listener.close()


if __name__ == "__main__":
    main()
