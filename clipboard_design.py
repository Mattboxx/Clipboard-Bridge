"""Lightweight, matte surfaces for the existing native Tk controls.

This is an opaque Liquid Glass-inspired appearance, not desktop capture or blur.
Text stays fully opaque, controls retain Tk keyboard/accessibility behavior and
all raster surfaces are generated once per palette, without an animation loop.
"""

import ctypes
from ctypes import wintypes
import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageTk


def _rgb(value):
    return tuple(bytes.fromhex(value.lstrip("#")))


def _surface(fill, edge, *, radius=7):
    scale, width, height = 3, 32, 32
    image = Image.new("RGBA", (width * scale, height * scale))
    mask = Image.new("L", image.size)
    ImageDraw.Draw(mask).rounded_rectangle((1, 1, width * scale - 2, height * scale - 2),
                                          radius=radius * scale, fill=255)
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, width * scale, height * scale), fill=fill)
    image.putalpha(mask)
    draw.rounded_rectangle((1, 1, width * scale - 2, height * scale - 2),
                           radius=radius * scale, outline=edge, width=scale)
    return image.resize((width, height), Image.Resampling.LANCZOS)


def _switch(colors, selected=False, disabled=False):
    image = Image.new("RGBA", (108, 66))
    draw = ImageDraw.Draw(image)
    background = colors["disabled"] if disabled else colors["primary"] if selected else colors["scroll"]
    draw.rounded_rectangle((3, 6, 105, 60), radius=27, fill=background)
    x = 55 if selected else 9
    draw.ellipse((x + 1, 13, x + 43, 55), fill="#00000028")
    draw.ellipse((x, 11, x + 42, 53), fill="#ffffff")
    return image.resize((36, 22), Image.Resampling.LANCZOS)


def _radio(colors, selected=False, disabled=False):
    image = Image.new("RGBA", (54, 54))
    draw = ImageDraw.Draw(image)
    colour = colors["disabled"] if disabled else colors["primary"] if selected else colors["scroll"]
    draw.ellipse((4, 4, 50, 50), fill=colors["field"], outline=colour, width=4)
    if selected:
        draw.ellipse((15, 15, 39, 39), fill=colour)
    return image.resize((18, 18), Image.Resampling.LANCZOS)


def native_chrome(window, colors, appearance):
    """Best-effort system title bar/rounded corners, with a safe Windows 10 fallback."""
    if os.name != "nt":
        return
    try:
        user = ctypes.WinDLL("user32", use_last_error=True)
        user.GetParent.argtypes, user.GetParent.restype = (wintypes.HWND,), wintypes.HWND
        handle = user.GetParent(window.winfo_id())
        if not handle:
            return
        system = Path(os.environ.get("SystemRoot", "C:/Windows")) / "System32" / "dwmapi.dll"
        set_attribute = ctypes.WinDLL(str(system)).DwmSetWindowAttribute
        set_attribute.argtypes = (wintypes.HWND, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD)
        set_attribute.restype = ctypes.c_long
        for attribute, value in ((20, int(appearance == "dark")), (33, 2),
                                 (34, int.from_bytes(bytes(_rgb(colors["border"])), "little"))):
            data = wintypes.DWORD(value)
            set_attribute(handle, attribute, ctypes.byref(data), ctypes.sizeof(data))
    except (OSError, AttributeError, ValueError):
        pass


def apply_styles(window, owner, style, appearance, colors):
    cache = getattr(owner, "_glass_images", None)
    if cache is None:
        owner._glass_images = cache = {}
    key = (appearance, tuple(colors.items()))
    if key not in cache:
        values = {}
        for name, fill, border in (
            ("normal", colors["panel"], colors["border"]),
            ("hover", colors["hover"], colors["border"]),
            ("pressed", colors["selected"], colors["primary"]),
            ("primary", colors["primary"], colors["primary"]),
            ("primary_hover", colors["primary_hover"], colors["primary_hover"]),
            ("primary_focus", colors["primary"], "#8ebaff"),
            ("primary_disabled", colors["soft"], colors["border"]),
            ("button_focus", colors["panel"], colors["primary"]),
            ("field", colors["field"], colors["border"]),
            ("focus", colors["field"], colors["primary"]),
            ("rail", colors["rail"], colors["rail"]),
        ):
            values[name] = ImageTk.PhotoImage(_surface(fill, border), master=owner)
        for selected in (False, True):
            for disabled in (False, True):
                values[f"switch-{selected}-{disabled}"] = ImageTk.PhotoImage(
                    _switch(colors, selected, disabled), master=owner)
                values[f"radio-{selected}-{disabled}"] = ImageTk.PhotoImage(
                    _radio(colors, selected, disabled), master=owner)
        for name, size, color in (("divider", (1, 1), colors["border"]),
                                  ("track", (1, 3), colors["panel"]),
                                  ("progress", (32, 3), colors["primary"])):
            values[name] = ImageTk.PhotoImage(Image.new("RGB", size, color), master=owner)
        values["indicator_gap"] = ImageTk.PhotoImage(Image.new("RGBA", (9, 1)), master=owner)
        cache[key] = values
    images = cache[key]
    prefix = "Glass." + appearance

    def element(name, default, *states, border=10):
        name = prefix + "." + name
        if name not in style.element_names():
            style.element_create(name, "image", images[default],
                                 *((state, images[image]) for state, image in states),
                                 border=border, padding=0, sticky="nsew")
        return name

    def button_layout(name):
        return [(name, {"sticky": "nsew", "children": [("Button.padding", {
            "sticky": "nsew", "children": [("Button.label", {"sticky": "nsew"})]})]})]

    normal = element("Button", "normal", ("disabled", "normal"), ("pressed", "pressed"),
                     ("active", "hover"), ("focus", "button_focus"))
    primary = element("Primary", "primary", ("disabled", "primary_disabled"),
                      ("pressed", "primary_hover"), ("active", "primary_hover"), ("focus", "primary_focus"))
    style.layout("TButton", button_layout(normal))
    style.configure("TButton", padding=(11, 6), borderwidth=0, anchor="center", background=colors["panel"])
    style.map("TButton", background=[("active", colors["panel"]), ("pressed", colors["panel"])])
    for name in ("Primary.TButton", "Settings.Primary.TButton"):
        style.layout(name, button_layout(primary))
        style.configure(name, padding=(11, 6), background=colors["panel"])
        style.map(name, background=[("active", colors["panel"]), ("pressed", colors["panel"])])
    style.configure("Command.TButton", padding=(10, 6))
    field = element("Field", "field", ("focus", "focus"), border=8)
    style.layout("TEntry", [(field, {"sticky": "nsew", "children": [("Entry.padding", {
        "sticky": "nsew", "children": [("Entry.textarea", {"sticky": "nsew"})]})]})])
    style.configure("TEntry", padding=(10, 7), insertcolor=colors["text"])
    style.configure("TCombobox", padding=(8, 6), arrowsize=12)
    # Clam supplies light hover/readonly colors unless every state is overridden.
    # Keep the field and arrow area separate, just like the reference UI tokens.
    for name in ("TEntry", "TCombobox", "TSpinbox"):
        style.configure(name, foreground=colors["text"], background=colors["soft"],
                        arrowcolor=colors["muted"], insertcolor=colors["text"])
        style.map(name,
            fieldbackground=[("disabled", colors["soft"]), ("!disabled", colors["field"])],
            background=[("disabled", colors["panel"]), ("pressed", colors["selected"]),
                        ("active", colors["hover"]), ("!disabled", colors["soft"])],
            foreground=[("disabled", colors["disabled"]), ("!disabled", colors["text"])],
            arrowcolor=[("disabled", colors["disabled"]), ("!disabled", colors["muted"])],
            bordercolor=[("focus", colors["primary"]), ("!focus", colors["border"])],
            lightcolor=[("!disabled", colors["border"]), ("disabled", colors["border"])],
            darkcolor=[("!disabled", colors["border"]), ("disabled", colors["border"])],
            selectbackground=[("!disabled", colors["selected"])],
            selectforeground=[("!disabled", colors["selected_text"])])
    style.map("TEntry", background=[("!disabled", colors["panel"]), ("disabled", colors["panel"])])
    for role in ("Checkbutton", "Radiobutton"):
        name = "switch" if role == "Checkbutton" else "radio"
        indicator = element(role + ".indicator", name + "-False-False",
            (("disabled", "selected"), name + "-True-True"), ("disabled", name + "-False-True"),
            ("selected", name + "-True-False"), border=0)
        gap = element("Indicator.gap", "indicator_gap", border=0)
        style.layout("T" + role, [(role + ".padding", {"sticky": "nsew", "children": [
            (indicator, {"side": "left", "sticky": "w"}),
            (gap, {"side": "left", "sticky": "w"}),
            (role + ".focus", {"side": "left", "sticky": "w", "children": [
                (role + ".label", {"sticky": "nsew"})]})]})])
        style.configure("T" + role, padding=(0, 5), indicatormargin=(0, 0, 9, 0))
    rail = element("Navigation", "rail", ("selected", "normal"), ("active", "hover"))
    segment = element("Segment", "rail", ("selected", "normal"), ("active", "hover"), ("focus", "button_focus"))
    for name, surface in (("Navigation.TRadiobutton", rail), ("Segment.TRadiobutton", segment)):
        style.layout(name, [(surface, {"sticky": "nsew", "children": [("Radiobutton.padding", {
            "sticky": "nsew", "children": [("Radiobutton.label", {"sticky": "nsew"})]})]})])
        style.configure(name, padding=(11, 9), anchor="w", compound="left")
        style.map(name, background=[("!disabled", colors["rail"]), ("disabled", colors["rail"])])
    style.configure("Filter.TRadiobutton", padding=(9, 6), anchor="center", font=("Segoe UI", -12))
    style.layout("Filter.TRadiobutton", style.layout("Segment.TRadiobutton"))
    style.map("Filter.TRadiobutton", foreground=[("selected", colors["text"]), ("!selected", colors["muted"])],
              background=[("!disabled", colors["panel"]), ("disabled", colors["panel"])])
    style.configure("Rail.TFrame", background=colors["rail"])
    style.configure("Rail.TLabel", background=colors["rail"], foreground=colors["muted"])
    style.configure("Canvas.TFrame", background=colors["canvas"])
    style.configure("Heading.TLabel", font=("Segoe UI", -20, "bold"))
    style.configure("Section.TLabel", font=("Segoe UI", -12, "bold"), foreground=colors["muted"])
    style.configure("Treeview", rowheight=26, font=("Segoe UI", -13))
    style.layout("Treeview.Item", [("Treeitem.padding", {"sticky": "nsew", "children": [
        ("Treeitem.image", {"side": "left", "sticky": ""}),
        ("Treeitem.text", {"side": "left", "sticky": "w"})]})])
    style.configure("Treeview.Item", padding=(6, 0))
    style.configure("Treeview.Heading", background=colors["panel"], padding=(8, 7),
                    bordercolor=colors["panel"], lightcolor=colors["panel"], darkcolor=colors["panel"])
    style.map("Treeview.Heading", background=[("active", colors["hover"]), ("!active", colors["panel"])],
              foreground=[("!disabled", colors["muted"])],
              lightcolor=[("!disabled", colors["panel"])], darkcolor=[("!disabled", colors["panel"])])
    style.configure("Meta.TLabel", font=("Consolas", -11), foreground=colors["muted"])
    divider = element("Divider", "divider", border=0)
    style.layout("TSeparator", [(divider, {"sticky": "nsew"})])
    style.configure("Settings.Section.TLabelframe", padding=(4, 12))
    style.configure("Settings.Section.TLabelframe.Label", font=("Segoe UI", -14, "bold"))
    track = element("Progress.track", "track", border=0)
    progress = element("Progress.bar", "progress", border=0)
    style.layout("Horizontal.TProgressbar", [(track, {"sticky": "nsew", "children": [
        (progress, {"side": "left", "sticky": "ns"})]})])
    style.configure("Horizontal.TProgressbar", borderwidth=0, thickness=3)
    native_chrome(window, colors, appearance)
