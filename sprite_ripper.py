"""
The Quest — Sprite Ripper  (40×40 tile edition)
================================================
Left panel  : screenshot viewer with 40×40 snap-grid overlay.
              Click any tile to select it.
Middle panel: pixel editor — selected tile shown at 10× zoom.
              Left-drag  → erase pixels (transparent)
              Right-drag → restore pixels from original
Right panel : save options, background-colour removal, saved list.

Workflow
--------
1. File > Open Screenshot
2. Adjust Grid Offset if the 40×40 grid is misaligned.
3. Click the tile you want in the left panel.
4. (Optional) tick "Remove BG" and right-click the screenshot to pick
   the background colour(s) to strip.
5. Manually erase stray pixels in the middle pixel editor if needed.
6. Choose "Solid" (opaque PNG) or "Transparent" (alpha PNG).
7. Type a name and press Enter / Save.
"""

import os
import re
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageTk

SPRITES_DIR = os.path.join(os.path.dirname(__file__), "sprites")
TILE_SIZE   = 40   # native game pixels per tile

os.makedirs(SPRITES_DIR, exist_ok=True)

ZOOM_LEVELS  = [1, 2, 3, 4, 6, 8]   # viewer zoom
EDITOR_ZOOM  = 10                    # pixel-editor zoom (fixed 10×)


# ── helpers ───────────────────────────────────────────────────────────────────

def _checker(w: int, h: int, size: int = 8) -> Image.Image:
    """Return an RGBA checkerboard image."""
    img = Image.new("RGBA", (w, h))
    pix = img.load()
    for y in range(h):
        for x in range(w):
            if (x // size + y // size) % 2 == 0:
                pix[x, y] = (170, 170, 170, 255)
            else:
                pix[x, y] = (100, 100, 100, 255)
    return img


def _remove_bg(img: Image.Image,
               colours: list[tuple[int, int, int]],
               tol: int = 0) -> Image.Image:
    """Return RGBA copy of img with listed colours set transparent."""
    out  = img.convert("RGBA")
    data = out.load()
    for y in range(out.height):
        for x in range(out.width):
            r, g, b, _ = data[x, y]
            for tr, tg, tb in colours:
                if abs(r-tr) <= tol and abs(g-tg) <= tol and abs(b-tb) <= tol:
                    data[x, y] = (r, g, b, 0)
                    break
    return out


# ── main app ──────────────────────────────────────────────────────────────────

class SpriteRipper(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("The Quest — Sprite Ripper")
        self.configure(bg="#1e1e2e")
        self.resizable(True, True)

        # state
        self.screenshot: Image.Image | None = None   # RGB original
        self.zoom_idx   = 2                          # into ZOOM_LEVELS
        self._viewer_img_ref  = None
        self._editor_img_ref  = None
        self._preview_img_ref = None

        self.grid_ox = tk.IntVar(value=0)   # grid offset x
        self.grid_oy = tk.IntVar(value=0)   # grid offset y

        self.selected_tile: tuple[int, int] | None = None  # (col, row) in tile coords
        self.tile_rgba:  Image.Image | None = None   # 40×40 RGBA working copy
        self.tile_orig:  Image.Image | None = None   # 40×40 RGB  original pixels

        self.bg_colours: list[tuple[int, int, int]] = []
        self.fuzzy_var  = tk.BooleanVar(value=False)
        self.remove_bg_var = tk.BooleanVar(value=True)
        self.solid_var  = tk.BooleanVar(value=False)   # False = transparent, True = solid

        self._erase_mode = True   # left=erase, right=restore
        self._editor_dragging = False

        self._build_ui()

    # ─────────────────────────────────────────────────────────────────────────
    # UI
    # ─────────────────────────────────────────────────────────────────────────

    def _build_ui(self):
        # ── menu ──
        mb = tk.Menu(self)
        fm = tk.Menu(mb, tearoff=0)
        fm.add_command(label="Open Screenshot…", command=self._open,
                       accelerator="Ctrl+O")
        fm.add_separator()
        fm.add_command(label="Exit", command=self.quit)
        mb.add_cascade(label="File", menu=fm)
        self.config(menu=mb)
        self.bind("<Control-o>", lambda e: self._open())
        self.bind("<Return>",    lambda e: self._save())
        self.bind("<Escape>",    lambda e: self._clear_editor())

        # ── toolbar ──
        tb = tk.Frame(self, bg="#313244", pady=3)
        tb.pack(fill="x", padx=4, pady=(4, 0))

        tk.Button(tb, text="Open Screenshot", command=self._open,
                  bg="#45475a", fg="#cdd6f4", relief="flat", padx=8
                  ).pack(side="left", padx=4)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)

        tk.Label(tb, text="Grid offset  X:", bg="#313244", fg="#cdd6f4",
                 font=("Consolas", 8)).pack(side="left")
        tk.Spinbox(tb, from_=0, to=39, textvariable=self.grid_ox, width=3,
                   bg="#1e1e2e", fg="#cdd6f4", font=("Consolas", 8),
                   command=self._redraw_viewer).pack(side="left", padx=(2,6))
        tk.Label(tb, text="Y:", bg="#313244", fg="#cdd6f4",
                 font=("Consolas", 8)).pack(side="left")
        tk.Spinbox(tb, from_=0, to=39, textvariable=self.grid_oy, width=3,
                   bg="#1e1e2e", fg="#cdd6f4", font=("Consolas", 8),
                   command=self._redraw_viewer).pack(side="left", padx=(2,8))

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)

        tk.Label(tb, text="Zoom:", bg="#313244", fg="#cdd6f4",
                 font=("Consolas", 8)).pack(side="left")
        for i, z in enumerate(ZOOM_LEVELS):
            tk.Button(tb, text=f"{z}×", width=3,
                      bg="#45475a", fg="#cdd6f4", relief="flat",
                      font=("Consolas", 8),
                      command=lambda idx=i: self._set_zoom(idx)
                      ).pack(side="left", padx=1)

        ttk.Separator(tb, orient="vertical").pack(side="left", fill="y", padx=6)

        tk.Label(tb, text="Name:", bg="#313244", fg="#cdd6f4",
                 font=("Consolas", 8)).pack(side="left")
        self.name_var = tk.StringVar(value="tile_1")
        tk.Entry(tb, textvariable=self.name_var, width=14,
                 bg="#1e1e2e", fg="#cdd6f4", insertbackground="#cdd6f4",
                 relief="flat", font=("Consolas", 9)
                 ).pack(side="left", padx=(4, 6))

        tk.Button(tb, text="Save  [Enter]", command=self._save,
                  bg="#a6e3a1", fg="#1e1e2e", relief="flat", padx=10,
                  font=("Consolas", 9, "bold")
                  ).pack(side="left", padx=4)

        # ── three-column body ──
        body = tk.Frame(self, bg="#1e1e2e")
        body.pack(fill="both", expand=True, padx=4, pady=4)

        self._build_viewer(body)
        self._build_editor(body)
        self._build_controls(body)

        # ── status ──
        self.status_var = tk.StringVar(value="Open a DOSBox screenshot to begin")
        tk.Label(self, textvariable=self.status_var, anchor="w",
                 bg="#313244", fg="#cdd6f4", padx=6, pady=2
                 ).pack(side="bottom", fill="x")

    # ── left: screenshot viewer ───────────────────────────────────────────────

    def _build_viewer(self, parent):
        frame = tk.Frame(parent, bg="#1e1e2e")
        frame.pack(side="left", fill="both", expand=True)

        tk.Label(frame, text="SCREENSHOT  (click tile to select)",
                 bg="#1e1e2e", fg="#89b4fa",
                 font=("Consolas", 9, "bold")).pack(anchor="w")

        cf = tk.Frame(frame, bg="#1e1e2e")
        cf.pack(fill="both", expand=True)

        self.viewer = tk.Canvas(cf, bg="#0d0d1a", cursor="crosshair",
                                highlightthickness=0)
        hb = ttk.Scrollbar(cf, orient="horizontal", command=self.viewer.xview)
        vb = ttk.Scrollbar(cf, orient="vertical",   command=self.viewer.yview)
        self.viewer.configure(xscrollcommand=hb.set, yscrollcommand=vb.set)
        hb.pack(side="bottom", fill="x")
        vb.pack(side="right",  fill="y")
        self.viewer.pack(fill="both", expand=True)

        self.viewer.bind("<ButtonPress-1>",   self._viewer_click)
        self.viewer.bind("<ButtonPress-3>",   self._viewer_pick_bg)
        self.viewer.bind("<MouseWheel>",      self._viewer_scroll)

    # ── middle: pixel editor ─────────────────────────────────────────────────

    def _build_editor(self, parent):
        frame = tk.Frame(parent, bg="#1e1e2e", width=420)
        frame.pack(side="left", fill="y", padx=(6, 0))
        frame.pack_propagate(False)

        tk.Label(frame, text="PIXEL EDITOR  (40×40 tile)",
                 bg="#1e1e2e", fg="#89b4fa",
                 font=("Consolas", 9, "bold")).pack(anchor="w")

        hint = tk.Frame(frame, bg="#1e1e2e")
        hint.pack(fill="x", pady=(0, 4))
        tk.Label(hint, text="L-drag: erase   R-drag: restore",
                 bg="#1e1e2e", fg="#7f849c",
                 font=("Consolas", 8)).pack(side="left")

        # editor canvas — fixed 400×400 (40 tiles × 10px each)
        EW = TILE_SIZE * EDITOR_ZOOM
        self.editor = tk.Canvas(frame, width=EW, height=EW,
                                bg="#1e1e2e", cursor="pencil",
                                highlightthickness=1,
                                highlightbackground="#45475a")
        self.editor.pack()

        self.editor.bind("<ButtonPress-1>",   self._edit_start)
        self.editor.bind("<B1-Motion>",       self._edit_drag)
        self.editor.bind("<ButtonRelease-1>", self._edit_end)
        self.editor.bind("<ButtonPress-3>",   self._edit_start_r)
        self.editor.bind("<B3-Motion>",       self._edit_drag_r)
        self.editor.bind("<ButtonRelease-3>", self._edit_end)

        # pixel grid toggle
        self.show_grid_var = tk.BooleanVar(value=True)
        tk.Checkbutton(frame, text="Show pixel grid",
                       variable=self.show_grid_var,
                       command=self._redraw_editor,
                       bg="#1e1e2e", fg="#cdd6f4",
                       selectcolor="#313244",
                       activebackground="#1e1e2e",
                       font=("Consolas", 8)
                       ).pack(anchor="w", pady=(4, 0))

        tk.Button(frame, text="Reset tile (undo all edits)",
                  command=self._reset_tile,
                  bg="#45475a", fg="#cdd6f4", relief="flat"
                  ).pack(fill="x", pady=2)

    # ── right: controls ───────────────────────────────────────────────────────

    def _build_controls(self, parent):
        frame = tk.Frame(parent, bg="#1e1e2e", width=200)
        frame.pack(side="left", fill="y", padx=(6, 0))
        frame.pack_propagate(False)

        # ── output mode ──
        tk.Label(frame, text="OUTPUT MODE", bg="#1e1e2e", fg="#89b4fa",
                 font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0,2))

        mode_f = tk.Frame(frame, bg="#1e1e2e")
        mode_f.pack(fill="x")
        tk.Radiobutton(mode_f, text="Transparent PNG",
                       variable=self.solid_var, value=False,
                       bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                       activebackground="#1e1e2e", font=("Consolas", 8)
                       ).pack(anchor="w")
        tk.Radiobutton(mode_f, text="Solid PNG (no alpha)",
                       variable=self.solid_var, value=True,
                       bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                       activebackground="#1e1e2e", font=("Consolas", 8)
                       ).pack(anchor="w")

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=6)

        # ── background removal ──
        tk.Label(frame, text="BACKGROUND REMOVAL", bg="#1e1e2e", fg="#89b4fa",
                 font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0,2))

        tk.Checkbutton(frame, text="Remove background",
                       variable=self.remove_bg_var,
                       command=self._apply_bg_and_redraw,
                       bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                       activebackground="#1e1e2e", font=("Consolas", 8)
                       ).pack(anchor="w")

        tk.Label(frame, text="Right-click screenshot\nto pick BG colour",
                 bg="#1e1e2e", fg="#7f849c",
                 font=("Consolas", 8), justify="left").pack(anchor="w")

        self.bg_list_frame = tk.Frame(frame, bg="#1e1e2e")
        self.bg_list_frame.pack(fill="x", pady=4)

        tk.Checkbutton(frame, text="Fuzzy match ±8",
                       variable=self.fuzzy_var,
                       command=self._apply_bg_and_redraw,
                       bg="#1e1e2e", fg="#cdd6f4", selectcolor="#313244",
                       activebackground="#1e1e2e", font=("Consolas", 8)
                       ).pack(anchor="w")

        tk.Button(frame, text="Clear BG colours",
                  command=self._clear_bg,
                  bg="#45475a", fg="#cdd6f4", relief="flat"
                  ).pack(fill="x", pady=2)

        ttk.Separator(frame, orient="horizontal").pack(fill="x", pady=6)

        # ── saved sprites ──
        tk.Label(frame, text="SAVED SPRITES", bg="#1e1e2e", fg="#89b4fa",
                 font=("Consolas", 9, "bold")).pack(anchor="w", pady=(0,2))
        self.saved_lb = tk.Listbox(frame, bg="#181825", fg="#cdd6f4",
                                   font=("Consolas", 8), height=12,
                                   relief="flat", selectbackground="#45475a")
        self.saved_lb.pack(fill="both", expand=True)
        self._refresh_saved_list()

    # ─────────────────────────────────────────────────────────────────────────
    # File
    # ─────────────────────────────────────────────────────────────────────────

    def _open(self):
        path = filedialog.askopenfilename(
            title="Open DOSBox Screenshot",
            filetypes=[("Images", "*.png *.bmp *.jpg *.jpeg"),
                       ("All files", "*.*")])
        if not path:
            return
        try:
            self.screenshot = Image.open(path).convert("RGB")
            self.selected_tile = None
            self.tile_rgba = self.tile_orig = None
            self._clear_bg()
            self._redraw_viewer()
            self._redraw_editor()
            self.status_var.set(
                f"{os.path.basename(path)}  "
                f"({self.screenshot.width}×{self.screenshot.height})  —  "
                f"click a tile in the viewer")
        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ─────────────────────────────────────────────────────────────────────────
    # Viewer
    # ─────────────────────────────────────────────────────────────────────────

    @property
    def zoom(self):
        return ZOOM_LEVELS[self.zoom_idx]

    def _set_zoom(self, idx: int):
        self.zoom_idx = idx
        self._redraw_viewer()

    def _viewer_scroll(self, event):
        if event.delta > 0:
            self.zoom_idx = min(len(ZOOM_LEVELS)-1, self.zoom_idx+1)
        else:
            self.zoom_idx = max(0, self.zoom_idx-1)
        self._redraw_viewer()

    def _redraw_viewer(self, *_):
        if self.screenshot is None:
            return
        z  = self.zoom
        ox = self.grid_ox.get()
        oy = self.grid_oy.get()
        sw = self.screenshot.width
        sh = self.screenshot.height

        # Scale screenshot
        scaled = self.screenshot.resize((sw*z, sh*z), Image.NEAREST)
        self._viewer_img_ref = ImageTk.PhotoImage(scaled)

        self.viewer.delete("all")
        self.viewer.configure(scrollregion=(0, 0, sw*z, sh*z))
        self.viewer.create_image(0, 0, anchor="nw",
                                 image=self._viewer_img_ref)

        # Draw 40×40 grid
        ts = TILE_SIZE * z
        # vertical lines
        x = ox * z
        while x <= sw * z:
            self.viewer.create_line(x, 0, x, sh*z, fill="#000000", width=1)
            x += ts
        # horizontal lines
        y = oy * z
        while y <= sh * z:
            self.viewer.create_line(0, y, sw*z, y, fill="#000000", width=1)
            y += ts

        # Highlight selected tile
        if self.selected_tile:
            col, row = self.selected_tile
            x0 = (ox + col * TILE_SIZE) * z
            y0 = (oy + row * TILE_SIZE) * z
            self.viewer.create_rectangle(x0, y0, x0+ts, y0+ts,
                                         outline="#f5c2e7", width=2)

    def _viewer_click(self, event):
        if self.screenshot is None:
            return
        z  = self.zoom
        ox = self.grid_ox.get()
        oy = self.grid_oy.get()
        cx = int(self.viewer.canvasx(event.x))
        cy = int(self.viewer.canvasy(event.y))

        # Snap to grid
        img_x = cx // z
        img_y = cy // z
        col = (img_x - ox) // TILE_SIZE
        row = (img_y - oy) // TILE_SIZE
        if col < 0 or row < 0:
            return

        # Pixel rect of this tile in the original screenshot
        px = ox + col * TILE_SIZE
        py = oy + row * TILE_SIZE
        if px + TILE_SIZE > self.screenshot.width or \
           py + TILE_SIZE > self.screenshot.height:
            return

        self.selected_tile = (col, row)
        crop = self.screenshot.crop((px, py, px+TILE_SIZE, py+TILE_SIZE))
        self.tile_orig = crop.copy()   # keep untouched original
        self.tile_rgba = crop.convert("RGBA")

        self._apply_bg_and_redraw()
        self._redraw_viewer()
        self.status_var.set(
            f"Selected tile ({col}, {row})  —  "
            f"pixel origin ({px}, {py})  —  "
            f"erase/restore in editor, then Save")

    def _viewer_pick_bg(self, event):
        if self.screenshot is None:
            return
        z  = self.zoom
        cx = int(self.viewer.canvasx(event.x))
        cy = int(self.viewer.canvasy(event.y))
        ix = min(cx // z, self.screenshot.width  - 1)
        iy = min(cy // z, self.screenshot.height - 1)
        colour = self.screenshot.getpixel((ix, iy))
        if colour not in self.bg_colours:
            self.bg_colours.append(colour)
            self._rebuild_bg_list()
            self.remove_bg_var.set(True)
            self._apply_bg_and_redraw()
            self.status_var.set(
                f"BG colour added: rgb{colour}  ({len(self.bg_colours)} total)")

    # ─────────────────────────────────────────────────────────────────────────
    # Background removal
    # ─────────────────────────────────────────────────────────────────────────

    def _apply_bg_and_redraw(self, *_):
        """Re-apply background removal to tile_orig → tile_rgba, then redraw."""
        if self.tile_orig is None:
            return
        if self.remove_bg_var.get() and self.bg_colours:
            tol = 8 if self.fuzzy_var.get() else 0
            self.tile_rgba = _remove_bg(self.tile_orig, self.bg_colours, tol)
        else:
            self.tile_rgba = self.tile_orig.convert("RGBA")
        self._redraw_editor()

    def _rebuild_bg_list(self):
        for w in self.bg_list_frame.winfo_children():
            w.destroy()
        for i, c in enumerate(self.bg_colours):
            row = tk.Frame(self.bg_list_frame, bg="#1e1e2e")
            row.pack(fill="x", pady=1)
            hx = f"#{c[0]:02x}{c[1]:02x}{c[2]:02x}"
            tk.Label(row, bg=hx, width=2, relief="ridge").pack(side="left")
            tk.Label(row, text=f" {hx}", bg="#1e1e2e", fg="#cdd6f4",
                     font=("Consolas", 7)).pack(side="left")
            tk.Button(row, text="✕", bg="#1e1e2e", fg="#f38ba8",
                      relief="flat", font=("Consolas", 8),
                      command=lambda i=i: self._remove_bg_colour(i)
                      ).pack(side="right")

    def _remove_bg_colour(self, idx: int):
        if 0 <= idx < len(self.bg_colours):
            self.bg_colours.pop(idx)
            self._rebuild_bg_list()
            self._apply_bg_and_redraw()

    def _clear_bg(self):
        self.bg_colours.clear()
        self._rebuild_bg_list()
        if self.tile_orig is not None:
            self.tile_rgba = self.tile_orig.convert("RGBA")
            self._redraw_editor()

    # ─────────────────────────────────────────────────────────────────────────
    # Pixel editor
    # ─────────────────────────────────────────────────────────────────────────

    def _redraw_editor(self):
        EZ = EDITOR_ZOOM
        EW = TILE_SIZE * EZ
        self.editor.delete("all")

        # Checkerboard background
        checker = _checker(EW, EW, EZ)
        if self.tile_rgba is not None:
            # Composite tile over checker
            composite = checker.copy()
            composite.paste(self.tile_rgba.resize(
                (EW, EW), Image.NEAREST), (0, 0), self.tile_rgba.resize(
                (EW, EW), Image.NEAREST))
        else:
            composite = checker

        self._editor_img_ref = ImageTk.PhotoImage(composite)
        self.editor.create_image(0, 0, anchor="nw",
                                 image=self._editor_img_ref)

        # Pixel grid overlay
        if self.show_grid_var.get():
            for i in range(0, TILE_SIZE + 1):
                self.editor.create_line(i*EZ, 0, i*EZ, EW,
                                        fill="#333333", width=1)
                self.editor.create_line(0, i*EZ, EW, i*EZ,
                                        fill="#333333", width=1)

    def _editor_pixel(self, event) -> tuple[int, int] | None:
        """Return (px, py) in tile coords from editor mouse event."""
        EZ = EDITOR_ZOOM
        x = event.x // EZ
        y = event.y // EZ
        if 0 <= x < TILE_SIZE and 0 <= y < TILE_SIZE:
            return x, y
        return None

    def _edit_start(self, event):
        self._editor_dragging = True
        self._do_erase(event)

    def _edit_drag(self, event):
        if self._editor_dragging:
            self._do_erase(event)

    def _edit_end(self, event):
        self._editor_dragging = False

    def _edit_start_r(self, event):
        self._editor_dragging = True
        self._do_restore(event)

    def _edit_drag_r(self, event):
        if self._editor_dragging:
            self._do_restore(event)

    def _do_erase(self, event):
        if self.tile_rgba is None:
            return
        px = self._editor_pixel(event)
        if px is None:
            return
        x, y = px
        r, g, b, _ = self.tile_rgba.getpixel((x, y))
        self.tile_rgba.putpixel((x, y), (r, g, b, 0))
        self._redraw_editor()

    def _do_restore(self, event):
        if self.tile_rgba is None or self.tile_orig is None:
            return
        px = self._editor_pixel(event)
        if px is None:
            return
        x, y = px
        r, g, b = self.tile_orig.getpixel((x, y))
        self.tile_rgba.putpixel((x, y), (r, g, b, 255))
        self._redraw_editor()

    def _reset_tile(self):
        if self.tile_orig is None:
            return
        self.tile_rgba = self.tile_orig.convert("RGBA")
        self._apply_bg_and_redraw()

    def _clear_editor(self):
        self.selected_tile = None
        self.tile_rgba = self.tile_orig = None
        self._redraw_editor()
        self._redraw_viewer()

    # ─────────────────────────────────────────────────────────────────────────
    # Save
    # ─────────────────────────────────────────────────────────────────────────

    def _save(self):
        if self.tile_rgba is None:
            messagebox.showwarning("Nothing selected",
                                   "Click a tile in the viewer first.")
            return

        name = self.name_var.get().strip()
        safe = re.sub(r"[^\w\-]", "_", name) or "sprite"

        out_path = os.path.join(SPRITES_DIR, safe + ".png")
        if os.path.exists(out_path):
            if not messagebox.askyesno("Overwrite?",
                                       f"{safe}.png already exists.\nOverwrite?"):
                return

        # Ensure exactly 40×40
        tile = self.tile_rgba.resize((TILE_SIZE, TILE_SIZE), Image.NEAREST)

        if self.solid_var.get():
            # Flatten onto white background → RGB
            bg = Image.new("RGB", (TILE_SIZE, TILE_SIZE), (255, 255, 255))
            bg.paste(tile, mask=tile.split()[3])
            bg.save(out_path)
        else:
            tile.save(out_path)

        self._refresh_saved_list()
        self.status_var.set(f"Saved → sprites/{safe}.png")

        # Auto-increment trailing number
        m = re.match(r'^(.*?)(\d+)$', name)
        if m:
            self.name_var.set(m.group(1) + str(int(m.group(2)) + 1))

    def _refresh_saved_list(self):
        self.saved_lb.delete(0, "end")
        try:
            for f in sorted(os.listdir(SPRITES_DIR)):
                if f.lower().endswith(".png"):
                    self.saved_lb.insert("end", f)
        except FileNotFoundError:
            pass


if __name__ == "__main__":
    app = SpriteRipper()
    app.geometry("1280x760")
    app.mainloop()
