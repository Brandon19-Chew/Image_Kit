#!/usr/bin/env python3
"""
ImageKit — Modern Image Processing System
Fixed: format conversion, save-as with correct format, all buttons have icons
Fixed: Reset to original image now works properly
"""

import base64
import os
import zipfile
import gzip
import bz2
from pathlib import Path
from datetime import datetime
from typing import Optional, Tuple
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk, ImageOps, ImageFilter, ImageEnhance
import io

# ══════════════════════════════════════════════
#  THEME
# ══════════════════════════════════════════════
BG_DARK    = "#0d1117"
BG_PANEL   = "#161c2a"
BG_CARD    = "#1c2333"
BG_HOVER   = "#232d42"
BG_INPUT   = "#1a2030"
ACCENT     = "#58a6ff"
ACCENT_DIM = "#1f3a5f"
TEXT_PRI   = "#e6edf3"
TEXT_SEC   = "#7d8590"
TEXT_MUTED = "#3d444d"
BORDER     = "#30363d"
SUCCESS    = "#3fb950"
WARNING    = "#d29922"
DANGER     = "#f85149"
PURPLE     = "#bc8cff"

FONT_UI    = ("Segoe UI", 9)
FONT_MONO  = ("Consolas", 9)
FONT_BOLD  = ("Segoe UI", 9, "bold")
FONT_TITLE = ("Segoe UI", 13, "bold")
FONT_TINY  = ("Segoe UI", 8)

# ── Format registry ──────────────────────────
FORMAT_INFO = {
    "PNG":  ("PNG",  [".png"],          False),
    "JPEG": ("JPEG", [".jpg", ".jpeg"], True),
    "WEBP": ("WEBP", [".webp"],         False),
    "BMP":  ("BMP",  [".bmp"],          False),
    "GIF":  ("GIF",  [".gif"],          True),
    "TIFF": ("TIFF", [".tiff", ".tif"], False),
    "ICO":  ("ICO",  [".ico"],          False),
}

EXT_TO_FMT = {}
for _k, (_p, _exts, _) in FORMAT_INFO.items():
    for _e in _exts:
        EXT_TO_FMT[_e] = _k


def to_saveable(img: Image.Image, fmt: str) -> Image.Image:
    """Mode-convert image so it can be saved in the target format."""
    if fmt == "GIF":
        return img.convert("P", palette=Image.ADAPTIVE) if img.mode != "P" else img
    _, _, needs_convert = FORMAT_INFO.get(fmt, (fmt, [], False))
    if needs_convert and img.mode in ("RGBA", "P", "LA"):
        bg  = Image.new("RGB", img.size, (255, 255, 255))
        src = img.convert("RGBA") if img.mode == "P" else img
        if src.mode in ("RGBA", "LA"):
            bg.paste(src, mask=src.split()[-1])
        return bg
    return img


# ══════════════════════════════════════════════
#  CORE ENGINE
# ══════════════════════════════════════════════
class ImageProcessorCore:

    def __init__(self):
        self.current_image  = None
        self.original_image = None
        self.reset_image    = None
        self.current_path   = None
        self.current_fmt    = "PNG"
        self._history       = []
        self._max_hist      = 30
        self._brightness    = 1.0
        self._contrast      = 1.0
        self._color         = 1.0

    # ── load ────────────────────────────────────
    def load_image(self, path: str) -> Tuple[bool, str]:
        try:
            img = Image.open(path)
            img.load()
            self.current_image  = img.copy()
            self.original_image = img.copy()
            self.reset_image    = img.copy()
            self.current_path   = path
            self.current_fmt    = EXT_TO_FMT.get(Path(path).suffix.lower(), "PNG")
            self._reset_adj()
            self._push()
            return True, f"Loaded: {os.path.basename(path)}  {img.size[0]}x{img.size[1]}  {img.mode}"
        except Exception as e:
            return False, f"Load error: {e}"

    def _reset_adj(self):
        self._brightness = self._contrast = self._color = 1.0

    def _push(self):
        if self.current_image:
            self._history.append(self.current_image.copy())
            if len(self._history) > self._max_hist:
                self._history.pop(0)

    def undo(self) -> Tuple[bool, str]:
        if len(self._history) > 1:
            self._history.pop()
            self.current_image  = self._history[-1].copy()
            self.original_image = self.current_image.copy()
            self._reset_adj()
            return True, "Undo successful"
        return False, "Nothing to undo"

    # ── reset to original ───────────────────────
    def reset_to_original(self) -> Tuple[bool, str]:
        if not self.reset_image:
            return False, "No reset point available"
        self.current_image  = self.reset_image.copy()
        self.original_image = self.reset_image.copy()
        self._reset_adj()
        self._history.clear()
        self._push()
        return True, "Image reset to original appearance"
    
    def set_reset_point(self):
        if self.current_image:
            self.reset_image = self.current_image.copy()
            self.original_image = self.current_image.copy()

    # ── save ────────────────────────────────────
    def save_image(self, path: str, quality: int = 95,
                   fmt: str = None) -> Tuple[bool, str]:
        if not self.current_image:
            return False, "No image loaded"
        try:
            os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
            ext      = Path(path).suffix.lower()
            save_fmt = fmt or EXT_TO_FMT.get(ext) or self.current_fmt or "PNG"
            pil_fmt  = FORMAT_INFO.get(save_fmt, (save_fmt,))[0]

            save_img = to_saveable(self.current_image, save_fmt)
            kw = {"format": pil_fmt}
            if save_fmt == "JPEG":
                kw["quality"] = quality; kw["optimize"] = True
            elif save_fmt == "WEBP":
                kw["quality"] = quality
            elif save_fmt == "PNG":
                kw["optimize"] = True

            save_img.save(path, **kw)
            return True, f"Saved: {os.path.basename(path)}  ({self._fmtsz(os.path.getsize(path))})"
        except Exception as e:
            return False, f"Save error: {e}"

    # ── format conversion ───────────────────────
    def convert_format(self, target_fmt: str) -> Tuple[bool, str]:
        if not self.current_image:
            return False, "No image loaded"
        if target_fmt not in FORMAT_INFO:
            return False, f"Unknown format: {target_fmt}"
        try:
            pil_fmt  = FORMAT_INFO[target_fmt][0]
            conv_img = to_saveable(self.current_image, target_fmt)

            buf = io.BytesIO()
            kw  = {"format": pil_fmt}
            if target_fmt == "JPEG":
                kw["quality"] = 95; kw["optimize"] = True
            elif target_fmt == "WEBP":
                kw["quality"] = 95
            elif target_fmt == "PNG":
                kw["optimize"] = True
            conv_img.save(buf, **kw)
            buf.seek(0)

            self.current_image  = Image.open(buf).copy()
            self.original_image = self.current_image.copy()
            self.reset_image    = self.current_image.copy()
            self.current_fmt    = target_fmt
            self._reset_adj()
            self._push()
            return True, f"Converted to {target_fmt}  (mode: {self.current_image.mode})"
        except Exception as e:
            return False, f"Conversion error: {e}"

    # ── non-destructive adjustments ─────────────
    def apply_adjustments(self, brightness=None, contrast=None,
                          color=None) -> Tuple[bool, str]:
        if not self.original_image:
            return False, "No image loaded"
        if brightness is not None: self._brightness = brightness
        if contrast   is not None: self._contrast   = contrast
        if color      is not None: self._color      = color

        img = self.original_image.copy()
        img = ImageEnhance.Brightness(img).enhance(self._brightness)
        img = ImageEnhance.Contrast(img).enhance(self._contrast)
        img = ImageEnhance.Color(img).enhance(self._color)
        self.current_image = img
        return True, f"B:{self._brightness:.2f} C:{self._contrast:.2f} S:{self._color:.2f}"

    # ── quality compression ──────────────────────
    def compress_quality(self, quality: int = 50) -> Tuple[bool, str]:
        if not self.current_image:
            return False, "No image loaded"
        try:
            buf     = io.BytesIO()
            save_img = to_saveable(self.current_image, "JPEG")
            save_img.save(buf, format="JPEG", quality=quality, optimize=True)
            buf.seek(0)
            self.current_image  = Image.open(buf).copy()
            self.original_image = self.current_image.copy()
            self._reset_adj()
            self._push()
            return True, f"Quality compressed to {quality}%"
        except Exception as e:
            return False, f"Compression error: {e}"

    # ── transforms ──────────────────────────────
    def resize(self, width=None, height=None, percentage=None,
               keep_aspect=True) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        ow, oh = self.current_image.size
        try:
            if percentage:
                nw = max(1, int(ow * percentage / 100))
                nh = max(1, int(oh * percentage / 100))
            elif width and height:
                nw, nh = width, height
            elif width:
                nw = width
                nh = max(1, int(oh * width / ow)) if keep_aspect else oh
            elif height:
                nh = height
                nw = max(1, int(ow * height / oh)) if keep_aspect else ow
            else:
                return False, "No size provided"
            self.current_image  = self.current_image.resize(
                (nw, nh), Image.Resampling.LANCZOS)
            self.original_image = self.current_image.copy()
            self._push()
            return True, f"Resized {ow}x{oh} -> {nw}x{nh}"
        except Exception as e:
            return False, f"Resize error: {e}"

    def rotate(self, degrees) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image  = self.current_image.rotate(
            degrees, expand=True, resample=Image.Resampling.BICUBIC)
        self.original_image = self.current_image.copy()
        self._push()
        return True, f"Rotated {degrees} degrees"

    def flip_horizontal(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image  = ImageOps.mirror(self.current_image)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Flipped horizontal"

    def flip_vertical(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image  = ImageOps.flip(self.current_image)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Flipped vertical"

    def apply_grayscale(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image  = ImageOps.grayscale(self.current_image)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Converted to grayscale"

    def apply_blur(self, radius=2.0) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image = self.current_image.filter(
            ImageFilter.GaussianBlur(radius))
        self.original_image = self.current_image.copy()
        self._push()
        return True, f"Gaussian blur r={radius}"

    def apply_sharpen(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image = self.current_image.filter(ImageFilter.SHARPEN)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Sharpen applied"

    def apply_autocontrast(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        img = self.current_image
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        self.current_image  = ImageOps.autocontrast(img)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Auto contrast applied"

    def apply_edge_enhance(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image = self.current_image.filter(ImageFilter.EDGE_ENHANCE)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Edge enhance applied"

    def apply_emboss(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image = self.current_image.filter(ImageFilter.EMBOSS)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Emboss applied"

    def apply_smooth(self) -> Tuple[bool, str]:
        if not self.current_image: return False, "No image loaded"
        self.current_image = self.current_image.filter(ImageFilter.SMOOTH)
        self.original_image = self.current_image.copy()
        self._push()
        return True, "Smooth applied"

    # ── base64 ──────────────────────────────────
    def image_to_base64(self, quality=95):
        if not self.current_image: return False, None, "No image loaded"
        try:
            buf = io.BytesIO()
            img = to_saveable(self.current_image, "JPEG")
            img.save(buf, format="JPEG", quality=quality)
            enc = base64.b64encode(buf.getvalue()).decode()
            return True, enc, f"Encoded {len(enc):,} chars"
        except Exception as e:
            return False, None, f"Encode error: {e}"

    def base64_to_image(self, b64: str) -> Tuple[bool, str]:
        try:
            if "base64," in b64:
                b64 = b64.split("base64,")[1]
            img = Image.open(io.BytesIO(base64.b64decode(b64))).copy()
            self.current_image  = img
            self.original_image = img.copy()
            self.reset_image    = img.copy()
            self._reset_adj()
            self._push()
            return True, "Image loaded from base64"
        except Exception as e:
            return False, f"Decode error: {e}"

    # ── archive ─────────────────────────────────
    def compress_to_zip(self, output_path: str, level=9) -> Tuple[bool, str]:
        if not self.current_path and not self.current_image:
            return False, "No image to compress"
        try:
            temp = None
            src  = self.current_path
            if not src:
                temp = "_tmp_imagekit.png"
                self.current_image.save(temp)
                src = temp
            with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED,
                                 compresslevel=level) as zf:
                zf.write(src, os.path.basename(src))
            if temp and os.path.exists(temp):
                os.remove(temp)
            cs  = os.path.getsize(output_path)
            osz = os.path.getsize(src)
            return True, f"ZIP: {self._fmtsz(cs)}  ({(1 - cs/osz)*100:.1f}% saved)"
        except Exception as e:
            return False, f"ZIP error: {e}"

    @staticmethod
    def extract_archive(archive_path: str, output_dir: str) -> Tuple[bool, str]:
        try:
            os.makedirs(output_dir, exist_ok=True)
            ap = archive_path
            if ap.endswith(".zip"):
                with zipfile.ZipFile(ap, "r") as zf:
                    zf.extractall(output_dir)
                    return True, f"Extracted {len(zf.namelist())} file(s)"
            elif ap.endswith(".gz"):
                out = os.path.join(output_dir, Path(ap).stem)
                with gzip.open(ap, "rb") as fi, open(out, "wb") as fo:
                    fo.write(fi.read())
                return True, "Extracted 1 file"
            elif ap.endswith(".bz2"):
                out = os.path.join(output_dir, Path(ap).stem)
                with bz2.open(ap, "rb") as fi, open(out, "wb") as fo:
                    fo.write(fi.read())
                return True, "Extracted 1 file"
            return False, "Unsupported archive format"
        except Exception as e:
            return False, f"Extract error: {e}"

    def get_image_info(self) -> dict:
        if not self.current_image:
            return {}
        img = self.current_image
        d = {
            "Size":   f"{img.size[0]} x {img.size[1]} px",
            "Mode":   img.mode,
            "Format": self.current_fmt,
        }
        if self.current_path and os.path.exists(self.current_path):
            d["File"]         = os.path.basename(self.current_path)
            d["Size on disk"] = self._fmtsz(os.path.getsize(self.current_path))
        return d

    @staticmethod
    def _fmtsz(n: int) -> str:
        for u in ("B", "KB", "MB", "GB"):
            if n < 1024: return f"{n:.1f} {u}"
            n /= 1024
        return f"{n:.1f} TB"


# ══════════════════════════════════════════════
#  CUSTOM WIDGETS
# ══════════════════════════════════════════════

class ModernSlider(tk.Frame):
    """Slider with live value label + reset button."""
    def __init__(self, parent, label, from_, to, default,
                 resolution=0.01, command=None, integer=False, **kw):
        super().__init__(parent, bg=BG_CARD, **kw)
        self._default = default
        self._cmd     = command
        self._integer = integer
        self._fmt     = "d" if integer else ".2f"

        row = tk.Frame(self, bg=BG_CARD)
        row.pack(fill=tk.X)

        tk.Label(row, text=label, font=FONT_UI,
                 fg=TEXT_SEC, bg=BG_CARD).pack(side=tk.LEFT)

        rst = tk.Label(row, text="  \u21ba", font=("Segoe UI", 10),
                       fg=TEXT_MUTED, bg=BG_CARD, cursor="hand2")
        rst.pack(side=tk.RIGHT, padx=(4, 0))
        rst.bind("<Button-1>", lambda e: self.reset())
        rst.bind("<Enter>",    lambda e: rst.config(fg=ACCENT))
        rst.bind("<Leave>",    lambda e: rst.config(fg=TEXT_MUTED))

        self.val_lbl = tk.Label(row, text=f"{default:{self._fmt}}",
                                font=FONT_MONO, fg=TEXT_MUTED,
                                bg=BG_CARD, width=6, anchor="e")
        self.val_lbl.pack(side=tk.RIGHT)

        self.var = tk.DoubleVar(value=default)
        self.scale = tk.Scale(
            self, variable=self.var, from_=from_, to=to,
            orient=tk.HORIZONTAL, resolution=resolution,
            showvalue=False, bg=BG_CARD, fg=ACCENT,
            troughcolor=BG_HOVER, activebackground=ACCENT,
            highlightthickness=0, bd=0,
            command=self._on_change)
        self.scale.pack(fill=tk.X, pady=(1, 0))

    def _on_change(self, val):
        v = int(float(val)) if self._integer else float(val)
        diff = abs(v - self._default)
        changed = diff > (0.5 if self._integer else 0.005)
        self.val_lbl.config(text=f"{v:{self._fmt}}",
                            fg=ACCENT if changed else TEXT_MUTED)
        if self._cmd:
            self._cmd(v)

    def get(self):
        v = self.var.get()
        return int(v) if self._integer else v

    def set(self, v):
        self.var.set(v)
        self.val_lbl.config(text=f"{v:{self._fmt}}")

    def reset(self):
        self.set(self._default)
        if self._cmd:
            self._cmd(self._default)


class Btn(tk.Label):
    """Flat icon+text button."""
    _COLORS = {
        "default": (BG_HOVER,    TEXT_PRI,  "#2c3855"),
        "primary": (ACCENT_DIM,  ACCENT,    "#1e4a7a"),
        "success": ("#1a3d25",   SUCCESS,   "#1f5030"),
        "danger":  ("#3d1a1a",   DANGER,    "#5c2020"),
        "purple":  ("#2a1f40",   PURPLE,    "#3a2a58"),
        "subtle":  (BG_CARD,     TEXT_SEC,  BG_HOVER),
    }

    def __init__(self, parent, text, command, icon="",
                 variant="default", full=True, **kw):
        bg, fg, hbg = self._COLORS.get(variant, self._COLORS["default"])
        label = f"{icon}  {text}" if icon else text
        super().__init__(parent, text=label, font=FONT_UI,
                         fg=fg, bg=bg, cursor="hand2",
                         padx=10, pady=6,
                         anchor="w" if full else "center",
                         relief="flat", **kw)
        self._bg = bg; self._hbg = hbg
        if full:
            self.pack(fill=tk.X, pady=1)
        self.bind("<Button-1>", lambda e: command())
        self.bind("<Enter>",    lambda e: self.config(bg=self._hbg))
        self.bind("<Leave>",    lambda e: self.config(bg=self._bg))


def section(parent, title: str):
    f = tk.Frame(parent, bg=BG_PANEL)
    f.pack(fill=tk.X, pady=(12, 2))
    tk.Label(f, text=title.upper(), font=("Segoe UI", 7, "bold"),
             fg=TEXT_MUTED, bg=BG_PANEL, padx=10).pack(side=tk.LEFT)
    tk.Frame(f, bg=BORDER, height=1).pack(side=tk.RIGHT, fill=tk.X,
                                           expand=True, padx=(0, 10), pady=9)


def card(parent, pady=6, padx=8):
    f = tk.Frame(parent, bg=BG_CARD, pady=pady, padx=padx,
                 highlightbackground=BORDER, highlightthickness=1)
    f.pack(fill=tk.X, padx=8, pady=2)
    return f


def icon_row_buttons(parent, buttons: list):
    row = tk.Frame(parent, bg=BG_CARD)
    row.pack(fill=tk.X, pady=4)
    for icon, tip, cmd in buttons:
        b = tk.Label(row, text=icon, font=("Segoe UI", 12),
                     fg=TEXT_SEC, bg=BG_HOVER, cursor="hand2",
                     padx=10, pady=5, width=4)
        b.pack(side=tk.LEFT, padx=2)
        b.bind("<Button-1>", lambda e, c=cmd: c())
        b.bind("<Enter>",    lambda e, w=b: w.config(fg=TEXT_PRI, bg=ACCENT_DIM))
        b.bind("<Leave>",    lambda e, w=b: w.config(fg=TEXT_SEC, bg=BG_HOVER))
        _tooltip(b, tip)


def _tooltip(widget, text: str):
    tip = [None]
    def show(e):
        x = widget.winfo_rootx() + 20
        y = widget.winfo_rooty() + widget.winfo_height() + 2
        tip[0] = tw = tk.Toplevel(widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{x}+{y}")
        tk.Label(tw, text=text, font=FONT_TINY,
                 bg=BG_CARD, fg=TEXT_PRI, padx=6, pady=3,
                 relief="flat").pack()
    def hide(e):
        if tip[0]: tip[0].destroy(); tip[0] = None
    widget.bind("<Enter>", show, add="+")
    widget.bind("<Leave>", hide, add="+")


# ══════════════════════════════════════════════
#  MAIN GUI
# ══════════════════════════════════════════════
class ImageProcessingGUI:
    def __init__(self, root):
        self.root     = root
        self.root.title("ImageKit")
        self.root.geometry("1300x840")
        self.root.configure(bg=BG_DARK)
        self.root.minsize(900, 600)

        self.proc     = ImageProcessorCore()
        self.image_tk = None
        self._adj_job = None

        self._style()
        self._build()
        self._menu()
        self._binds()
        self.log("ImageKit ready - open an image to begin", "info")

    def _style(self):
        s = ttk.Style()
        s.theme_use("default")
        s.configure("TScrollbar", background=BG_PANEL,
                    troughcolor=BG_DARK, arrowcolor=TEXT_MUTED,
                    borderwidth=0, relief="flat")
        s.configure("TCombobox", fieldbackground=BG_INPUT,
                    background=BG_HOVER, foreground=TEXT_PRI,
                    arrowcolor=TEXT_SEC, borderwidth=1,
                    relief="flat", padding=4)
        s.map("TCombobox",
              fieldbackground=[("readonly", BG_INPUT)],
              foreground=[("readonly", TEXT_PRI)])

    # ── build layout ────────────────────────────
    def _build(self):
        # top bar
        bar = tk.Frame(self.root, bg=BG_PANEL, height=48,
                       highlightbackground=BORDER, highlightthickness=1)
        bar.pack(fill=tk.X)
        bar.pack_propagate(False)

        tk.Label(bar, text="ImageKit", font=FONT_TITLE,
                 fg=ACCENT, bg=BG_PANEL, padx=16).pack(side=tk.LEFT, pady=10)

        self._status = tk.StringVar(value="No image loaded")
        tk.Label(bar, textvariable=self._status, font=FONT_UI,
                 fg=TEXT_SEC, bg=BG_PANEL).pack(side=tk.LEFT, padx=10)

        for txt, cmd, bg in [
            ("Undo",  self.undo,        BG_HOVER),
            ("Reset", self.reset_appearance, BG_HOVER),
            ("Open",  self.open_image,  ACCENT_DIM),
        ]:
            b = tk.Label(bar, text=txt, font=FONT_BOLD, fg=TEXT_PRI,
                         bg=bg, padx=14, pady=6, cursor="hand2")
            b.pack(side=tk.RIGHT, padx=4, pady=10)
            b.bind("<Button-1>", lambda e, c=cmd: c())
            b.bind("<Enter>",    lambda e, w=b, oc=bg: w.config(bg=self._lgt(oc)))
            b.bind("<Leave>",    lambda e, w=b, oc=bg: w.config(bg=oc))

        # paned window
        paned = tk.PanedWindow(self.root, orient=tk.HORIZONTAL,
                               bg=BORDER, sashwidth=3, sashpad=0,
                               handlesize=0, relief=tk.FLAT)
        paned.pack(fill=tk.BOTH, expand=True)

        # LEFT PANEL
        lo = tk.Frame(paned, bg=BG_PANEL, width=300)
        paned.add(lo, minsize=240)

        self._lc = tk.Canvas(lo, bg=BG_PANEL, highlightthickness=0, width=295)
        ls = ttk.Scrollbar(lo, orient=tk.VERTICAL, command=self._lc.yview)
        self._lc.configure(yscrollcommand=ls.set)
        ls.pack(side=tk.RIGHT, fill=tk.Y)
        self._lc.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._lp    = tk.Frame(self._lc, bg=BG_PANEL)
        self._lp_id = self._lc.create_window((0, 0), window=self._lp, anchor="nw")

        self._lp.bind("<Configure>", lambda e:
                      self._lc.configure(scrollregion=self._lc.bbox("all")))
        self._lc.bind("<Configure>", lambda e:
                      self._lc.itemconfig(self._lp_id, width=e.width))

        # scroll bindings
        def bind_scroll(e):
            self._lc.bind_all("<MouseWheel>", self._scroll)
            self._lc.bind_all("<Button-4>",   self._scroll)
            self._lc.bind_all("<Button-5>",   self._scroll)
        def unbind_scroll(e):
            self._lc.unbind_all("<MouseWheel>")
            self._lc.unbind_all("<Button-4>")
            self._lc.unbind_all("<Button-5>")
        self._lc.bind("<Enter>", bind_scroll)
        self._lc.bind("<Leave>", unbind_scroll)

        self._sidebar()

        # RIGHT PANEL
        right = tk.Frame(paned, bg=BG_DARK)
        paned.add(right, minsize=450)
        self._canvas_area(right)
        self._log_area(right)

    def _scroll(self, event):
        if   event.num == 4:  d = -1
        elif event.num == 5:  d =  1
        elif event.delta > 0: d = -1
        else:                 d =  1
        self._lc.yview_scroll(d, "units")

    # ── sidebar contents ────────────────────────
    def _sidebar(self):
        p = self._lp

        # FILE
        section(p, "File")
        c = card(p)
        Btn(c, "Open Image",  self.open_image,    "O",  "primary")
        Btn(c, "Save As...",  self.save_image_as,  "SA", "default")

        # FORMAT CONVERSION
        section(p, "Format Conversion")
        c = card(p)

        row = tk.Frame(c, bg=BG_CARD)
        row.pack(fill=tk.X, pady=(4, 6))
        tk.Label(row, text="Target format:", font=FONT_UI,
                 fg=TEXT_SEC, bg=BG_CARD).pack(side=tk.LEFT)
        self._fmt_var = tk.StringVar(value="PNG")
        cb = ttk.Combobox(row, textvariable=self._fmt_var,
                          values=list(FORMAT_INFO.keys()),
                          state="readonly", width=10)
        cb.pack(side=tk.RIGHT)

        Btn(c, "Convert In-Memory",   self.convert_format,   "C",  "default")
        Btn(c, "Convert & Save As...", self.convert_and_save, "CS", "primary")

        # ADJUSTMENTS
        section(p, "Adjustments  (live, non-destructive)")
        c = card(p, pady=8)
        tk.Label(c, text="Sliders apply on top of original - drag to 1.00 to reset",
                 font=FONT_TINY, fg=TEXT_MUTED, bg=BG_CARD,
                 wraplength=240, justify="left").pack(anchor="w", pady=(0, 4))

        self._sl_b = ModernSlider(c, "Brightness", 0.1, 3.0, 1.0,
                                   command=self._adj_change)
        self._sl_b.pack(fill=tk.X, pady=2)
        self._sl_c = ModernSlider(c, "Contrast",   0.1, 3.0, 1.0,
                                   command=self._adj_change)
        self._sl_c.pack(fill=tk.X, pady=2)
        self._sl_s = ModernSlider(c, "Saturation", 0.0, 3.0, 1.0,
                                   command=self._adj_change)
        self._sl_s.pack(fill=tk.X, pady=2)

        # JPEG QUALITY
        section(p, "JPEG Quality Compression")
        c = card(p, pady=8)
        self._sl_q = ModernSlider(c, "Quality %", 1, 100, 85,
                                   resolution=1, integer=True)
        self._sl_q.pack(fill=tk.X, pady=2)
        Btn(c, "Apply Quality Compression", self.reduce_quality, "Q", "default")

        # RESIZE
        section(p, "Resize")
        c = card(p, pady=8)

        dimrow = tk.Frame(c, bg=BG_CARD)
        dimrow.pack(fill=tk.X, pady=(0, 4))
        for lbl, attr in [("W", "_w_entry"), ("H", "_h_entry")]:
            tk.Label(dimrow, text=lbl, font=FONT_UI,
                     fg=TEXT_SEC, bg=BG_CARD, width=2).pack(side=tk.LEFT)
            e = tk.Entry(dimrow, width=7, font=FONT_MONO,
                         bg=BG_INPUT, fg=TEXT_PRI, insertbackground=ACCENT,
                         relief=tk.FLAT, bd=5,
                         highlightbackground=BORDER, highlightthickness=1)
            e.pack(side=tk.LEFT, padx=2)
            setattr(self, attr, e)
        Btn(dimrow, "Go", self.resize_px, "R", "primary",
            full=False).pack(side=tk.RIGHT)

        prow = tk.Frame(c, bg=BG_CARD)
        prow.pack(fill=tk.X)
        self._sl_pct = ModernSlider(prow, "Resize %", 1, 400, 100,
                                     resolution=1, integer=True)
        self._sl_pct.pack(fill=tk.X, expand=True, side=tk.LEFT)
        Btn(prow, "Go", self.resize_pct, "R", "primary",
            full=False).pack(side=tk.RIGHT, padx=(4, 0))

        # ROTATE & FLIP
        section(p, "Rotate & Flip")
        c = card(p)
        icon_row_buttons(c, [
            ("CCW", "Rotate 90 CCW",  lambda: self.rotate(-90)),
            ("CW",  "Rotate 90 CW",   lambda: self.rotate(90)),
            ("H",   "Flip Horizontal", self.flip_h),
            ("V",   "Flip Vertical",   self.flip_v),
        ])

        # EFFECTS
        section(p, "Effects")
        c = card(p)
        Btn(c, "Grayscale",      self.apply_grayscale,    "G",  "default")
        Btn(c, "Gaussian Blur",  self.apply_blur,         "BL", "default")
        Btn(c, "Sharpen",        self.apply_sharpen,      "SH", "default")
        Btn(c, "Auto Contrast",  self.apply_autocontrast, "AC", "default")
        Btn(c, "Edge Enhance",   self.apply_edge_enhance, "EE", "default")
        Btn(c, "Emboss",         self.apply_emboss,       "EM", "default")
        Btn(c, "Smooth",         self.apply_smooth,       "SM", "default")
        
        # RESET BUTTON
        tk.Frame(c, bg=BG_CARD, height=4).pack()
        Btn(c, "↺ Reset Image Appearance", self.reset_appearance, "R", "danger")

        # BASE64
        section(p, "Base64")
        c = card(p)
        Btn(c, "Export to Base64 file",  self.export_b64, "E", "default")
        Btn(c, "Import from Base64 file", self.import_b64, "I", "default")
        Btn(c, "Copy to Clipboard",       self.copy_b64,   "C", "default")

        # ARCHIVE
        section(p, "Archive")
        c = card(p)
        Btn(c, "Compress to ZIP",  self.compress_zip, "Z", "default")
        Btn(c, "Extract Archive",  self.extract,      "X", "default")

        # HISTORY
        section(p, "History")
        c = card(p)
        Btn(c, "Undo Last Change", self.undo,      "U", "danger")
        Btn(c, "Image Info",       self.show_info, "I", "subtle")

        tk.Frame(p, bg=BG_PANEL, height=20).pack()

    # ── canvas ──────────────────────────────────
    def _canvas_area(self, parent):
        cf = tk.Frame(parent, bg=BG_DARK)
        cf.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(cf, bg="#080c12", highlightthickness=0)
        hs = ttk.Scrollbar(cf, orient=tk.HORIZONTAL, command=self.canvas.xview)
        vs = ttk.Scrollbar(cf, orient=tk.VERTICAL,   command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hs.set, yscrollcommand=vs.set)

        self.canvas.grid(row=0, column=0, sticky="nsew")
        hs.grid(row=1, column=0, sticky="ew")
        vs.grid(row=0, column=1, sticky="ns")
        cf.grid_rowconfigure(0, weight=1)
        cf.grid_columnconfigure(0, weight=1)

        self._placeholder()

    def _placeholder(self):
        self.canvas.delete("all")
        cw = self.canvas.winfo_width()  or 700
        ch = self.canvas.winfo_height() or 440
        self.canvas.create_text(cw//2, ch//2,
                                text="",
                                fill=TEXT_MUTED, font=("Segoe UI", 14))

    # ── log area ────────────────────────────────
    def _log_area(self, parent):
        lf = tk.Frame(parent, bg=BG_PANEL,
                      highlightbackground=BORDER, highlightthickness=1)
        lf.pack(fill=tk.X, side=tk.BOTTOM)

        hdr = tk.Frame(lf, bg=BG_PANEL)
        hdr.pack(fill=tk.X)
        tk.Label(hdr, text="LOG", font=("Segoe UI", 7, "bold"),
                 fg=TEXT_MUTED, bg=BG_PANEL, padx=10).pack(side=tk.LEFT, pady=4)
        clr = tk.Label(hdr, text="clear", font=FONT_TINY,
                       fg=TEXT_MUTED, bg=BG_PANEL, cursor="hand2", padx=8)
        clr.pack(side=tk.RIGHT, pady=4)
        clr.bind("<Button-1>", lambda e: self._logtxt.delete(1.0, tk.END))

        self._logtxt = tk.Text(
            lf, height=4, bg=BG_PANEL, fg=TEXT_SEC,
            font=FONT_MONO, relief=tk.FLAT, wrap=tk.WORD,
            insertbackground=ACCENT, padx=10, pady=4)
        self._logtxt.pack(fill=tk.X, pady=(0, 4))
        for tag, col in [("info", TEXT_SEC), ("success", SUCCESS),
                          ("warn", WARNING),  ("error",   DANGER)]:
            self._logtxt.tag_config(tag, foreground=col)

    # ── menu ────────────────────────────────────
    def _menu(self):
        mb = tk.Menu(self.root, bg=BG_PANEL, fg=TEXT_PRI,
                     activebackground=ACCENT_DIM, activeforeground=TEXT_PRI,
                     relief=tk.FLAT, bd=0)
        self.root.config(menu=mb)

        fm = tk.Menu(mb, tearoff=0, bg=BG_PANEL, fg=TEXT_PRI)
        mb.add_cascade(label="File", menu=fm)
        fm.add_command(label="Open    Ctrl+O", command=self.open_image)
        fm.add_command(label="Save As...",     command=self.save_image_as)
        fm.add_separator()
        fm.add_command(label="Exit", command=self.root.quit)

        em = tk.Menu(mb, tearoff=0, bg=BG_PANEL, fg=TEXT_PRI)
        mb.add_cascade(label="Edit", menu=em)
        em.add_command(label="Undo  Ctrl+Z", command=self.undo)
        em.add_separator()
        em.add_command(label="Reset to Original", command=self.reset_appearance)
        em.add_command(label="Image Info",   command=self.show_info)
        em.add_command(label="Clear Log",
                       command=lambda: self._logtxt.delete(1.0, tk.END))

    def _binds(self):
        self.root.bind("<Control-o>", lambda e: self.open_image())
        self.root.bind("<Control-z>", lambda e: self.undo())
        self.root.bind("<Configure>", self._on_resize)

    # ── helpers ─────────────────────────────────
    @staticmethod
    def _lgt(hex_color: str) -> str:
        try:
            h = hex_color.lstrip("#")
            r = int(h[0:2], 16); g = int(h[2:4], 16); b = int(h[4:6], 16)
            return "#{:02x}{:02x}{:02x}".format(
                min(255, r+22), min(255, g+22), min(255, b+22))
        except Exception:
            return hex_color

    def log(self, msg: str, level="info"):
        ts = datetime.now().strftime("%H:%M:%S")
        self._logtxt.insert(tk.END, f"[{ts}] {msg}\n", level)
        self._logtxt.see(tk.END)

    def display(self):
        if not self.proc.current_image:
            return
        cw = max(self.canvas.winfo_width(),  450)
        ch = max(self.canvas.winfo_height(), 300)
        img = self.proc.current_image.copy()
        img.thumbnail((cw - 20, ch - 20), Image.Resampling.LANCZOS)
        self.image_tk = ImageTk.PhotoImage(img)
        self.canvas.delete("all")
        self.canvas.create_image(cw//2, ch//2,
                                 image=self.image_tk, anchor=tk.CENTER)
        d = self.proc.get_image_info()
        parts = [d.get("File", "unsaved"), d.get("Size", ""),
                 d.get("Mode", ""), d.get("Format", "")]
        self._status.set("  |  ".join(p for p in parts if p))

    def _on_resize(self, event):
        if event.widget == self.root and self.proc.current_image:
            self.display()

    def _run(self, result: tuple, reset_sliders=False):
        ok, msg = result
        self.log(msg, "success" if ok else "error")
        if ok:
            if reset_sliders:
                self._sl_b.reset()
                self._sl_c.reset()
                self._sl_s.reset()
            self.display()
        return ok

    # ── adjustments ─────────────────────────────
    def _adj_change(self, _=None):
        if self._adj_job:
            self.root.after_cancel(self._adj_job)
        self._adj_job = self.root.after(55, self._do_adj)

    def _do_adj(self):
        ok, msg = self.proc.apply_adjustments(
            brightness=self._sl_b.get(),
            contrast=self._sl_c.get(),
            color=self._sl_s.get())
        if ok:
            self.display()

    # ── file ops ────────────────────────────────
    def open_image(self):
        ft = [("Images", "*.jpg *.jpeg *.png *.gif *.bmp *.webp *.tiff *.ico"),
              ("All", "*.*")]
        fn = filedialog.askopenfilename(filetypes=ft)
        if fn:
            ok, msg = self.proc.load_image(fn)
            self.log(msg, "success" if ok else "error")
            if ok:
                self._sl_b.reset(); self._sl_c.reset(); self._sl_s.reset()
                self.display()

    def save_image_as(self):
        fmt = self.proc.current_fmt or "PNG"
        ext = FORMAT_INFO[fmt][1][0]
        ft  = [("PNG",  "*.png"), ("JPEG", "*.jpg *.jpeg"),
               ("WebP", "*.webp"), ("BMP",  "*.bmp"),
               ("GIF",  "*.gif"),  ("TIFF", "*.tiff"),
               ("ICO",  "*.ico"),  ("All",  "*.*")]
        fn = filedialog.asksaveasfilename(defaultextension=ext, filetypes=ft)
        if fn:
            chosen_ext = Path(fn).suffix.lower()
            save_fmt   = EXT_TO_FMT.get(chosen_ext, fmt)
            self._run(self.proc.save_image(fn, fmt=save_fmt))

    # ── format conversion ────────────────────────
    def convert_format(self):
        self._run(self.proc.convert_format(self._fmt_var.get()),
                  reset_sliders=True)

    def convert_and_save(self):
        """Convert in-memory then save with the correct format."""
        target = self._fmt_var.get()
        ok, msg = self.proc.convert_format(target)
        self.log(msg, "success" if ok else "error")
        if not ok:
            return
        self.display()
        ext = FORMAT_INFO[target][1][0]
        ft  = [(target, f"*{ext}"), ("All", "*.*")]
        fn  = filedialog.asksaveasfilename(
            defaultextension=ext, filetypes=ft,
            title=f"Save as {target}")
        if fn:
            self._run(self.proc.save_image(fn, fmt=target))

    # ── quality ─────────────────────────────────
    def reduce_quality(self):
        q = int(self._sl_q.get())
        self._run(self.proc.compress_quality(q), reset_sliders=True)

    # ── transforms ──────────────────────────────
    def resize_px(self):
        try:
            w = int(self._w_entry.get()) if self._w_entry.get().strip() else None
            h = int(self._h_entry.get()) if self._h_entry.get().strip() else None
            if not (w or h):
                self.log("Enter width or height", "warn"); return
            self._run(self.proc.resize(width=w, height=h))
        except ValueError:
            self.log("Invalid dimensions", "error")

    def resize_pct(self):
        self._run(self.proc.resize(percentage=int(self._sl_pct.get())))

    def rotate(self, deg):
        self._run(self.proc.rotate(deg))

    def flip_h(self):
        self._run(self.proc.flip_horizontal())

    def flip_v(self):
        self._run(self.proc.flip_vertical())

    # ── effects ─────────────────────────────────
    def apply_grayscale(self):
        self._run(self.proc.apply_grayscale(), reset_sliders=True)

    def apply_blur(self):
        self._run(self.proc.apply_blur())

    def apply_sharpen(self):
        self._run(self.proc.apply_sharpen())

    def apply_autocontrast(self):
        self._run(self.proc.apply_autocontrast(), reset_sliders=True)

    def apply_edge_enhance(self):
        self._run(self.proc.apply_edge_enhance())

    def apply_emboss(self):
        self._run(self.proc.apply_emboss())

    def apply_smooth(self):
        self._run(self.proc.apply_smooth())

    # ── reset appearance ─────────────────────────
    def reset_appearance(self):
        """Reset image to original loaded state, clearing all effects."""
        if not self.proc.current_image:
            self.log("No image to reset", "warn")
            return
        
        if messagebox.askyesno("Reset Image", 
                              "Reset image to original appearance?\n"
                              "This will undo all effects and transformations"):
            ok, msg = self.proc.reset_to_original()
            self.log(msg, "success" if ok else "warn")
            if ok:
                self._sl_b.reset()
                self._sl_c.reset()
                self._sl_s.reset()
                self._sl_q.reset()
                self._sl_pct.reset()
                self.display()

    # ── base64 ──────────────────────────────────
    def export_b64(self):
        ok, b64, msg = self.proc.image_to_base64()
        self.log(msg, "success" if ok else "error")
        if ok:
            fn = filedialog.asksaveasfilename(
                defaultextension=".txt",
                filetypes=[("Text", "*.txt"), ("All", "*.*")])
            if fn:
                with open(fn, "w") as f: f.write(b64)
                self.log(f"Saved to {fn}", "success")

    def import_b64(self):
        fn = filedialog.askopenfilename(
            filetypes=[("Text", "*.txt"), ("All", "*.*")])
        if fn:
            with open(fn, "r") as f: b64 = f.read().strip()
            ok, msg = self.proc.base64_to_image(b64)
            self.log(msg, "success" if ok else "error")
            if ok: self.display()

    def copy_b64(self):
        ok, b64, msg = self.proc.image_to_base64()
        if ok:
            self.root.clipboard_clear()
            self.root.clipboard_append(b64)
            self.log("Base64 copied to clipboard", "success")
        else:
            self.log(msg, "error")

    # ── archive ─────────────────────────────────
    def compress_zip(self):
        fn = filedialog.asksaveasfilename(
            defaultextension=".zip",
            filetypes=[("ZIP", "*.zip"), ("All", "*.*")])
        if fn:
            self._run(self.proc.compress_to_zip(fn))

    def extract(self):
        fn = filedialog.askopenfilename(
            filetypes=[("Archives", "*.zip *.gz *.bz2"), ("All", "*.*")])
        if fn:
            out = filedialog.askdirectory(title="Extract to folder...")
            if out:
                ok, msg = ImageProcessorCore.extract_archive(fn, out)
                self.log(msg, "success" if ok else "error")

    # ── history / info ───────────────────────────
    def undo(self):
        ok, msg = self.proc.undo()
        self.log(msg, "success" if ok else "warn")
        if ok:
            self._sl_b.reset(); self._sl_c.reset(); self._sl_s.reset()
            self.display()

    def show_info(self):
        d = self.proc.get_image_info()
        if not d:
            messagebox.showinfo("Image Info", "No image loaded")
            return
        txt = "\n".join(f"  {k}:  {v}" for k, v in d.items())
        messagebox.showinfo("Image Info", txt)


# ══════════════════════════════════════════════
#  ENTRY POINT
# ══════════════════════════════════════════════
def main():
    root = tk.Tk()
    ImageProcessingGUI(root)
    root.mainloop()


if __name__ == "__main__":
    main()
