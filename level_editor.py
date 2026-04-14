"""
The Quest — Level Editor
Reads/writes L00001.dat – L00007.dat map files and SAVE*.dat save files.

════════════════════════════════════════════════════════════════════
MAP FILE FORMAT  (L00001.dat – L00007.dat)
════════════════════════════════════════════════════════════════════
  100×100 tiles, 10 000 lines of 8 encoded fields each:
    x  y  floor  wall  object  enemy  gold  extra
  Numbers: each decimal digit stored as (digit + 0x81).
           Negative prefix: 0x7E byte before the digits.
  Fields delimited by 0x20 (space), lines by CRLF.

════════════════════════════════════════════════════════════════════
SAVE FILE FORMAT  (SAVE*.dat)  — confirmed by binary analysis
════════════════════════════════════════════════════════════════════
  Line 0        : 10 fields — field[0]=Player Level, field[1]=Class ID,
                  remaining fields are screen/position data (preserved verbatim).
                  Class IDs: 1=Knight  2=Mage  3=Rogue  4=Monk

  Lines 1–9999  : Map tile data, column-major order (same codec as map files).
                  Tile (1,1) is absent from this section.

  Lines 10000–10099 : Screen cache — 100 lines of 8 fields each:
                  [lx, ly, floor, wall, object, enemy, gold, extra]
                  lx/ly are 1-based coords within the current 10×10 screen block.

  Line 10100    : Player position — [abs_x, abs_y, rel_x, rel_y]

  Line 10101    : Player combat stats — 10 fields:
                  [0] Max Life   [1] Cur Life   [2] Max Mana   [3] Cur Mana
                  [4] Strength   [5] Intelligence [6] Dexterity [7] Accuracy
                  [8] Reputation [9] EXP Needed

  Line 10102    : Gold + potion counts — 12 fields:
                  [0–2] unknown (preserved verbatim)   [3] Gold
                  [4] Half Life Potion   [5] Full Life Potion
                  [6] Half Mana Potion   [7] Full Mana Potion
                  [8] Half Restoration   [9] Full Restoration
                  [10] Cure Poison       [11] Berserker Potion

  Lines 10103+  : World flags / inventory — preserved verbatim.

  Line 11358–11367 : Spell book LEFT column  — 10 spell slot IDs (0 = empty).
  Lines 11368–11387: Unknown gap             — never written, preserved verbatim.
  Lines 11388–11397: Spell book RIGHT column — 10 spell slot IDs (0 = empty).
  Lines 11398–11417: Spell learned flags     — 20 lines, one per spell ID (0/1).

  Line 11645    : Skill/Fault flags — 8 fields (each 0 or 1):
                  [0] Ambidexterity  [1] Bargaining  [2] Scholar
                  [3] Memorisation   [4] Markmanship
                  [5] Cowardice      [6] Honor        [7] Rashness

  Line 11649    : Skill/fault secondary encoding — preserved verbatim.
                  (Written by the game itself; exact format not fully decoded.)

SPELL IDs (lines 11358–11397 and 11398–11417):
   1=Heal            2=Flame           3=Teleport        4=Shield
   5=Ring of Ice     6=Black Ward      7=Invisibility    8=Summon Skeleton
   9=Inferno        10=Restore        11=Life Drain      12=Thunder Bolt
  13=Shield of Fire 14=Deteriorate   15=Summon Stone Knight
  16=Earthquake     17=Cure          18=Summon Scorpion
  19=Meteor         20=Dark Hour
"""

import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import os
import re as _re
from PIL import Image, ImageTk

DATA_DIR    = os.path.join(os.path.dirname(__file__), "data")
SPRITES_DIR = os.path.join(os.path.dirname(__file__), "sprites")
MAP_SIZE    = 100

# Class ID → hero sprite stem  (hero_Knight.png etc.)
_CLASS_SPRITE = {1: "hero_Knight", 2: "hero_Mage", 3: "hero_Rogue", 4: "hero_Monk"}

# ── Codec ─────────────────────────────────────────────────────────────────────

def decode_field(token: bytes) -> int:
    if not token:
        return 0
    neg  = token[0] == 0x7E
    data = token[1:] if neg else token
    n    = 0
    for b in data:
        n = n * 10 + (b - 0x81)
    return -n if neg else n


def encode_field(value: int) -> bytes:
    neg     = value < 0
    s       = str(abs(value))
    encoded = bytes(int(d) + 0x81 for d in s)
    return (b'\x7e' + encoded) if neg else encoded


def load_map(path: str) -> list[list[list[int]]]:
    """Return grid[y][x] = [tile_type, variant, object_id, enemy, gold, extra].
    Only exactly-8-field lines are treated as tile data — avoids the 10-field
    hero-stats line at the top of save files."""
    grid = [[[1, 0, 0, 0, 0, 0] for _ in range(MAP_SIZE)] for _ in range(MAP_SIZE)]
    with open(path, 'rb') as f:
        lines = f.read().split(b'\r\n')
    tiles_loaded = 0
    for line in lines:
        if tiles_loaded >= MAP_SIZE * MAP_SIZE:
            break
        if not line:
            continue
        fields = [fld for fld in line.split(b' ') if fld]
        if len(fields) != 8:
            continue
        vals = [decode_field(fld) for fld in fields]
        x, y = vals[0] - 1, vals[1] - 1
        if 0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE:
            grid[y][x] = vals[2:8]
            tiles_loaded += 1
    return grid


def save_map(path: str, grid: list[list[list[int]]]):
    """Write a plain level file (L*.dat) — 10,000 lines of 8-field tile data."""
    lines = []
    for x in range(MAP_SIZE):
        for y in range(MAP_SIZE):
            tile = grid[y][x]
            row  = [x + 1, y + 1] + tile
            lines.append(b' '.join(encode_field(v) for v in row))
    with open(path, 'wb') as f:
        f.write(b'\r\n'.join(lines))


def is_save_file(path: str) -> bool:
    return os.path.basename(path).upper().startswith('SAVE')


def read_player_pos(lines: list[bytes]) -> tuple[int, int] | None:
    """Extract player (abs_x, abs_y) from an already-loaded line list."""
    if len(lines) <= 10100:
        return None
    fields = [f for f in lines[10100].split(b' ') if f]
    if len(fields) >= 2:
        abs_x = decode_field(fields[0])
        abs_y = decode_field(fields[1])
        if 1 <= abs_x <= MAP_SIZE and 1 <= abs_y <= MAP_SIZE:
            return abs_x, abs_y
    return None


def read_player_class(lines: list[bytes]) -> int:
    """Extract class ID from line 0 field[1]. Returns 1 (Knight) as default."""
    if not lines:
        return 1
    f0 = [f for f in lines[0].split(b' ') if f]
    if len(f0) >= 2:
        cid = decode_field(f0[1])
        if cid in _CLASS_SPRITE:
            return cid
    return 1


def read_all_player_data(lines: list[bytes]) -> dict | None:
    """Extract all editable player data from an already-loaded line list."""
    if len(lines) <= 10102:
        return None
    f0   = [f for f in lines[0].split(b' ') if f]
    f101 = [f for f in lines[10101].split(b' ') if f]
    f102 = [f for f in lines[10102].split(b' ') if f]
    if len(f101) != 10 or len(f102) != 12:
        return None
    return {
        'level': decode_field(f0[0]) if f0 else 1,
        'stats': [decode_field(f) for f in f101],
        'inv':   [decode_field(f) for f in f102],
    }


def write_all_player_data(path: str, level: int,
                          stats: list[int], inv: list[int]):
    """Patch level (line 0 field[0]), stats (line 10101), inv (line 10102)."""
    with open(path, 'rb') as f:
        lines = f.read().split(b'\r\n')
    if len(lines) <= 10102:
        raise ValueError("Save file too short — not a valid SAVE*.dat")
    f0       = [fld for fld in lines[0].split(b' ') if fld]
    f0[0]    = encode_field(level)
    lines[0] = b' '.join(f0)
    lines[10101] = b' '.join(encode_field(v) for v in stats)
    lines[10102] = b' '.join(encode_field(v) for v in inv)
    with open(path, 'wb') as f:
        f.write(b'\r\n'.join(lines))


# ── Class / Skills / Spells line constants ────────────────────────────────────

_SPELL_LEFT_START  = 11358
_SPELL_RIGHT_START = 11388
_SPELL_FLAGS_START = 11398
_SKILLS_LINE       = 11645
_SKILLS_AUX_LINE   = 11649


def read_all_class_data(lines: list[bytes]) -> dict | None:
    """Extract class, skills, faults and spells from an already-loaded line list."""
    if len(lines) <= _SKILLS_AUX_LINE:
        return None
    f0  = [f for f in lines[0].split(b' ')                if f]
    f45 = [f for f in lines[_SKILLS_LINE].split(b' ')     if f]
    f49 = [f for f in lines[_SKILLS_AUX_LINE].split(b' ') if f]
    if len(f0) < 2 or len(f45) < 8:
        return None
    sf = [decode_field(f) for f in f45]

    def block(start, count):
        result = []
        for i in range(count):
            fields = [fld for fld in lines[start + i].split(b' ') if fld]
            result.append(decode_field(fields[0]) if fields else 0)
        return result

    return {
        'class':         decode_field(f0[1]),
        'ambidexterity': sf[0], 'bargaining':  sf[1], 'scholar':   sf[2],
        'memorisation':  sf[3], 'markmanship': sf[4],
        'cowardice':     sf[5], 'honor':       sf[6], 'rashness':  sf[7],
        'spell_left':    block(_SPELL_LEFT_START,  10),
        'spell_right':   block(_SPELL_RIGHT_START, 10),
        'spell_flags':   block(_SPELL_FLAGS_START, 20),
        '_line0': f0,
        '_aux49': f49,
    }


def write_all_class_data(path: str, data: dict):
    """Patch class (line 0 field[1]), skills, spells — single read + write."""
    with open(path, 'rb') as f:
        lines = f.read().split(b'\r\n')
    if len(lines) <= _SKILLS_AUX_LINE:
        raise ValueError("Save file too short — not a valid SAVE*.dat")
    # Re-read line 0 fresh from disk so we don't clobber the level written earlier
    f0    = [fld for fld in lines[0].split(b' ') if fld]
    f0[1] = encode_field(data['class'])
    lines[0] = b' '.join(f0)
    lines[_SKILLS_LINE] = b' '.join(encode_field(v) for v in [
        int(data['ambidexterity']), int(data['bargaining']),  int(data['scholar']),
        int(data['memorisation']),  int(data['markmanship']),
        int(data['cowardice']),     int(data['honor']),       int(data['rashness']),
    ])
    for i, val in enumerate(data['spell_left']):
        lines[_SPELL_LEFT_START + i] = encode_field(val)
    # Lines 11368–11387 — unknown gap, never written
    for i, val in enumerate(data['spell_right']):
        lines[_SPELL_RIGHT_START + i] = encode_field(val)
    for i, val in enumerate(data['spell_flags']):
        lines[_SPELL_FLAGS_START + i] = encode_field(val)
    lines[_SKILLS_AUX_LINE] = b' '.join(data['_aux49'])
    with open(path, 'wb') as f:
        f.write(b'\r\n'.join(lines))


def save_save_file(path: str, grid: list[list[list[int]]], player_pos: tuple[int, int]):
    """Patch a SAVE*.dat in-place — map tiles, screen cache, player position."""
    with open(path, 'rb') as f:
        lines = f.read().split(b'\r\n')
    if len(lines) <= 10100:
        raise ValueError("Save file too short — not a valid SAVE*.dat")

    abs_x, abs_y = player_pos
    rel_x = ((abs_x - 1) % 10) + 1
    rel_y = ((abs_y - 1) % 10) + 1
    sx    = ((abs_x - 1) // 10) + 1
    sy    = ((abs_y - 1) // 10) + 1

    for i in range(1, 10000):
        line   = lines[i]
        fields = [fld for fld in line.split(b' ') if fld]
        if len(fields) == 8:
            vals = [decode_field(fld) for fld in fields]
            x, y = vals[0] - 1, vals[1] - 1
            if 0 <= x < MAP_SIZE and 0 <= y < MAP_SIZE:
                lines[i] = b' '.join(encode_field(v) for v in [x+1, y+1] + grid[y][x])

    for lx in range(1, 11):
        for ly in range(1, 11):
            ax   = min(MAP_SIZE, (sx - 1) * 10 + lx)
            ay   = min(MAP_SIZE, (sy - 1) * 10 + ly)
            tile = grid[ay - 1][ax - 1]
            lines[10000 + (lx - 1) * 10 + (ly - 1)] = (
                b' '.join(encode_field(v) for v in [lx, ly] + tile))

    lines[10100] = b' '.join(encode_field(v) for v in [abs_x, abs_y, rel_x, rel_y])
    with open(path, 'wb') as f:
        f.write(b'\r\n'.join(lines))


# ── Tile colours ──────────────────────────────────────────────────────────────

TILE_TYPE_COLORS: dict[int, str] = {
    0: "#1a1a2e", 1: "#4a7c59", 2: "#7a9e7e", 3: "#2d6a4f",
    4: "#8d8d8d", 5: "#c9a84c", 6: "#e63946", 7: "#6b4226", 8: "#3d3d3d",
}

TILE_VARIANT_COLORS: dict[tuple[int, int], str] = {
    (1,  0): "#5a8f4e", (1, -1): "#4a7c3e", (1,  1): "#6a9f5e",
    (1,  2): "#2e86ab", (1,  3): "#1e5e28", (1,  4): "#7ab060",
    (1,  5): "#8ac070", (1,  6): "#9acd80", (1,  7): "#aad090",
    (1,  8): "#bad3a0", (1,  9): "#cad6b0", (1, 12): "#dae0c0",
    (2, -1): "#6a8e7e", (2,  0): "#7a9e7e", (3,  0): "#2d6a4f",
    (3,  3): "#1d5a3f", (6, -1): "#c02030", (6,  0): "#e63946",
    (6,  9): "#ff6060", (7,  0): "#6b4226", (8,  0): "#3d3d3d",
}


def tile_color(tile_type: int, variant: int) -> str:
    c = TILE_VARIANT_COLORS.get((tile_type, variant))
    if c:
        return c
    base = TILE_TYPE_COLORS.get(tile_type, "#ff00ff")
    if variant < 0:
        r = max(0, int(base[1:3], 16) - 30)
        g = max(0, int(base[3:5], 16) - 30)
        b = max(0, int(base[5:7], 16) - 30)
        return f'#{r:02x}{g:02x}{b:02x}'
    return base


def _obj_fallback_color(obj_id: int) -> str:
    if obj_id >= 1000: return "#ffffff"
    if obj_id >= 600:  return "#ff6b6b"
    if obj_id >= 300:  return "#ffd166"
    if obj_id >= 200:  return "#06d6a0"
    if obj_id >= 100:  return "#118ab2"
    return "#ff9f1c"


# ── Sprite registry ───────────────────────────────────────────────────────────
# Tile sprites: floor_N[desc].png | wall_N[desc].png | enemy_N[desc].png
#               object_N[desc].png | extra_N[desc].png  (N may be negative)
# Hero sprites: hero_Knight.png | hero_Mage.png | hero_Rogue.png | hero_Monk.png

_SPRITE_PATTERN = _re.compile(r'^(floor|wall|enemy|object|extra)_(-?\d+)(?:\[.*\])?$')

# (stem, size) → PhotoImage — module-level to survive GC
_sprite_cache: dict[tuple[str, int], ImageTk.PhotoImage | None] = {}


def _scan_sprites() -> tuple[dict, dict, dict, dict, dict]:
    floor_s: dict[int, str] = {}
    wall_s:  dict[int, str] = {}
    ene_s:   dict[int, str] = {}
    obj_s:   dict[int, str] = {}
    extra_s: dict[int, str] = {}
    if not os.path.isdir(SPRITES_DIR):
        return floor_s, wall_s, ene_s, obj_s, extra_s
    for fname in sorted(os.listdir(SPRITES_DIR)):
        if not fname.lower().endswith('.png'):
            continue
        m = _SPRITE_PATTERN.match(fname[:-4])
        if not m:
            continue
        prefix, n = m.group(1), int(m.group(2))
        if   prefix == 'floor':  floor_s[n] = fname[:-4]
        elif prefix == 'wall':   wall_s[n]  = fname[:-4]
        elif prefix == 'enemy':  ene_s[n]   = fname[:-4]
        elif prefix == 'object': obj_s[n]   = fname[:-4]
        elif prefix == 'extra':  extra_s[n] = fname[:-4]
    return floor_s, wall_s, ene_s, obj_s, extra_s


TILE_TYPE_SPRITES, VARIANT_SPRITES, ENEMY_SPRITES, OBJECT_SPRITES, EXTRA_SPRITES = _scan_sprites()


def _load_sprite(stem: str, size: int) -> ImageTk.PhotoImage | None:
    if not stem:
        return None
    key = (stem, size)
    if key not in _sprite_cache:
        path = os.path.join(SPRITES_DIR, stem + ".png")
        if not os.path.exists(path):
            _sprite_cache[key] = None
        else:
            img = Image.open(path).convert("RGBA").resize((size, size), Image.NEAREST)
            _sprite_cache[key] = ImageTk.PhotoImage(img)
    return _sprite_cache[key]


def _sprite_label(stem: str, fallback: str) -> str:
    m = _re.search(r'\[(.+)\]$', stem)
    return m.group(1) if m else fallback


# ── Editor UI ─────────────────────────────────────────────────────────────────

CELL = 40   # native sprite size in pixels

ZOOM_STEPS       = [3, 4, 5, 6, 8, 10, 14, 20, 28, 40, 56, 80, 120]
ZOOM_DEFAULT_IDX = 9   # 40 px = 100 %

_ZOOM_BTN = [(1, "10%"), (4, "20%"), (5, "25%"), (7, "50%"),
             (9, "100%"), (11, "200%"), (12, "300%")]

_SWATCH  = 20
_PREVIEW = 160


def _center_window(win: tk.Wm, w: int, h: int):
    """Place a window at the centre of the screen."""
    sw = win.winfo_screenwidth()
    sh = win.winfo_screenheight()
    win.geometry(f"{w}x{h}+{(sw - w) // 2}+{(sh - h) // 2}")


class LevelEditor(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("The Quest — Level Editor")
        self.resizable(True, True)

        self.grid_data: list[list[list[int]]] | None = None
        self.current_file: str | None = None
        self.player_class_id: int     = 1      # drives hero sprite selection
        self._zoom_idx  = ZOOM_DEFAULT_IDX
        self.cell_size  = ZOOM_STEPS[self._zoom_idx]
        self.selected_tile_type = 1
        self.selected_variant   = 0
        self.selected_object    = 0
        self.selected_enemy     = 0
        self.selected_gold      = 0
        self.selected_extra     = 0
        self.hover_x = self.hover_y = -1
        self.is_painting = False
        self.start_pos   = (1, 1)
        self.mode        = "paint"
        self.show_tile_grid   = tk.BooleanVar(value=True)
        self.show_screen_grid = tk.BooleanVar(value=True)
        self._swatch_imgs: dict[str, ImageTk.PhotoImage] = {}

        self._build_ui()
        self._new_map()

        # Centre main window on screen after layout is complete
        self.update_idletasks()
        _center_window(self, 1150, 780)

    # ── Layout ────────────────────────────────────────────────────────────────

    def _build_ui(self):
        self.configure(bg="#1e1e2e")

        menubar  = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label="New Map",   command=self._new_map, accelerator="Ctrl+N")
        filemenu.add_command(label="Open…",     command=self._open,    accelerator="Ctrl+O")
        filemenu.add_command(label="Save",      command=self._save,    accelerator="Ctrl+S")
        filemenu.add_command(label="Save As…",  command=self._save_as)
        filemenu.add_separator()
        filemenu.add_command(label="Export map as PNG…", command=self._export_png)
        filemenu.add_separator()
        self.safe_mode = tk.BooleanVar(value=True)
        filemenu.add_checkbutton(label="Safe Mode  (sprite IDs only)",
                                 variable=self.safe_mode,
                                 command=self._apply_safe_mode)
        filemenu.add_separator()
        filemenu.add_checkbutton(label="Show tile grid  (100×100)",
                                 variable=self.show_tile_grid,  command=self._redraw)
        filemenu.add_checkbutton(label="Show screen grid  (10×10)",
                                 variable=self.show_screen_grid, command=self._redraw)
        filemenu.add_separator()
        filemenu.add_command(label="Exit", command=self.quit)
        menubar.add_cascade(label="File", menu=filemenu)
        self.config(menu=menubar)
        self.bind("<Control-n>", lambda e: self._new_map())
        self.bind("<Control-o>", lambda e: self._open())
        self.bind("<Control-s>", lambda e: self._save())
        self.bind("<Escape>",    lambda e: self._cancel_mode())

        main = tk.Frame(self, bg="#1e1e2e")
        main.pack(fill="both", expand=True, padx=4, pady=4)

        # ── Canvas ────────────────────────────────────────────────────────────
        canvas_frame = tk.Frame(main, bg="#1e1e2e")
        canvas_frame.pack(side="left", fill="both", expand=True)

        self.canvas = tk.Canvas(canvas_frame, bg="#0d0d1a",
                                highlightthickness=0, cursor="crosshair")
        hbar = ttk.Scrollbar(canvas_frame, orient="horizontal", command=self.canvas.xview)
        vbar = ttk.Scrollbar(canvas_frame, orient="vertical",   command=self.canvas.yview)
        self.canvas.configure(xscrollcommand=hbar.set, yscrollcommand=vbar.set)
        hbar.pack(side="bottom", fill="x")
        vbar.pack(side="right",  fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.canvas.bind("<ButtonPress-1>",  self._on_paint_start)
        self.canvas.bind("<B1-Motion>",       self._on_paint_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_paint_end)
        self.canvas.bind("<ButtonPress-3>",   self._on_pick)
        self.canvas.bind("<Motion>",          self._on_hover)
        self.canvas.bind("<Leave>",           self._on_leave)
        self.canvas.bind("<MouseWheel>",      self._on_scroll)
        self.canvas.bind("<ButtonPress-2>",   self._on_pan_start)
        self.canvas.bind("<B2-Motion>",       self._on_pan_drag)

        # ── Right panel ───────────────────────────────────────────────────────
        right = tk.Frame(main, bg="#1e1e2e", width=290)
        right.pack(side="right", fill="y", padx=(6, 0))
        right.pack_propagate(False)
        self._build_palette(right)
        self._build_info(right)

        # ── Status bar ────────────────────────────────────────────────────────
        self.status_var = tk.StringVar(value="Ready — open a level file or paint on the grid")
        tk.Label(self, textvariable=self.status_var, anchor="w",
                 bg="#313244", fg="#cdd6f4", padx=6, pady=2
                 ).pack(side="bottom", fill="x")

    # ── Palette ───────────────────────────────────────────────────────────────

    def _build_palette(self, parent):
        tk.Label(parent, text="TILE PALETTE", bg="#1e1e2e",
                 fg="#89b4fa", font=("Consolas", 10, "bold")
                 ).pack(fill="x", pady=(0, 4))

        preview_wrap = tk.Frame(parent, bg="#313244",
                                width=_PREVIEW + 4, height=_PREVIEW + 4)
        preview_wrap.pack(pady=(0, 8))
        preview_wrap.pack_propagate(False)
        self._preview_lbl = tk.Label(preview_wrap, bg="#313244", bd=0)
        self._preview_lbl.place(relx=0.5, rely=0.5, anchor="center")

        self.copy_tile_btn = tk.Button(parent, text="Copy Tile",
                  font=("Consolas", 8), bg="#45475a", fg="#cdd6f4",
                  activebackground="#585b70", relief="flat", bd=0, pady=3,
                  command=self._toggle_copy_mode)
        self.copy_tile_btn.pack(fill="x", pady=(4, 0))

        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=(6, 6))

        self.type_var  = tk.StringVar(value="1")
        self.var_var   = tk.StringVar(value="0")
        self.obj_var   = tk.StringVar(value="0")
        self.enemy_var = tk.StringVar(value="0")
        self.extra_var = tk.StringVar(value="0")
        self.gold_var  = tk.StringVar(value="0")

        def row(label, var, lo, hi, color, trace_cb):
            f = tk.Frame(parent, bg="#1e1e2e")
            f.pack(fill="x", pady=2)
            tk.Label(f, text=f"{label}:", bg="#1e1e2e", fg=color,
                     font=("Consolas", 9, "bold"), width=8, anchor="w").pack(side="left")
            sp = tk.Spinbox(f, from_=lo, to=hi, textvariable=var, width=5,
                            bg="#313244", fg=color, font=("Consolas", 9),
                            relief="flat", bd=1, command=trace_cb)
            sp.pack(side="left", padx=(0, 3))
            sw = tk.Label(f, bg="#313244", relief="ridge", bd=1)
            sw.pack(side="left", padx=(0, 3))
            info = tk.Label(f, text="", bg="#1e1e2e",
                            fg="#7f849c", font=("Consolas", 8), anchor="w", width=26)
            info.pack(side="left", fill="x", expand=True)
            var.trace_add("write", lambda *_: trace_cb())
            return sp, sw, info

        self._sp_type,  self._sw_type,  self._info_type  = row("Floor",  self.type_var,  -999,  999,  "#89b4fa", self._on_type_changed)
        self._sp_var,   self._sw_var,   self._info_var   = row("Wall",   self.var_var,   -999,  999,  "#a6e3a1", self._on_var_changed)
        self._sp_obj,   self._sw_obj,   self._info_obj   = row("Object", self.obj_var,      0, 9999,  "#fab387", self._on_obj_changed)
        self._sp_enemy, self._sw_enemy, self._info_enemy = row("Enemy",  self.enemy_var, -9999, 9999, "#cba6f7", self._on_enemy_changed)
        self._sp_extra, self._sw_extra, self._info_extra = row("Extra",  self.extra_var, -9999, 9999, "#cdd6f4", self._on_extra_changed)
        self._sp_gold,  self._sw_gold,  self._info_gold  = row("Gold",   self.gold_var,      0, 9999, "#f9e2af", self._on_gold_changed)

        self._sp_ranges = {
            self._sp_type:  (-999,  999),
            self._sp_var:   (-999,  999),
            self._sp_obj:   (0,    9999),
            self._sp_enemy: (-9999, 9999),
            self._sp_extra: (-9999, 9999),
        }

        # ── Zoom ──────────────────────────────────────────────────────────────
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)
        tk.Label(parent, text="ZOOM", bg="#1e1e2e", fg="#cdd6f4",
                 font=("Consolas", 9, "bold")).pack(anchor="w")
        zoom_row = tk.Frame(parent, bg="#1e1e2e")
        zoom_row.pack(fill="x", pady=(2, 0))
        for idx, label in _ZOOM_BTN:
            tk.Button(zoom_row, text=label, font=("Consolas", 7),
                      bg="#45475a", fg="#cdd6f4", relief="flat", padx=3,
                      command=lambda i=idx: self._set_zoom_idx(i, center=True)
                      ).pack(side="left", padx=1)

        # ── Player Position (SAVE files only) ────────────────────────────────────
        self._player_start_sep   = ttk.Separator(parent, orient="horizontal")
        self._player_start_frame = tk.Frame(parent, bg="#1e1e2e")

        tk.Label(self._player_start_frame, text="PLAYER POSITION",
                 bg="#1e1e2e", fg="#a6e3a1",
                 font=("Consolas", 9, "bold")).pack(anchor="w")

        pos_row = tk.Frame(self._player_start_frame, bg="#1e1e2e")
        pos_row.pack(fill="x", pady=(2, 4))
        tk.Label(pos_row, text="Pos:", bg="#1e1e2e",
                 fg="#cdd6f4", font=("Consolas", 8)).pack(side="left")
        self.start_pos_lbl = tk.Label(pos_row, text="(1, 1)",
                                      bg="#1e1e2e", fg="#a6e3a1",
                                      font=("Consolas", 9, "bold"))
        self.start_pos_lbl.pack(side="left", padx=4)

        self.set_start_btn = tk.Button(
            self._player_start_frame,
            text="Click tile to set position",
            font=("Consolas", 8), bg="#313244", fg="#cdd6f4",
            activebackground="#45475a", relief="flat", bd=0,
            command=self._toggle_set_start_mode)
        self.set_start_btn.pack(fill="x", pady=(0, 2))

        self._stats_btn = tk.Button(
            self._player_start_frame,
            text="Edit Player Stats…",
            font=("Consolas", 8), bg="#45475a", fg="#f9e2af",
            activebackground="#585b70", relief="flat", bd=0, pady=4,
            command=self._open_stats_editor)
        self._stats_btn.pack(fill="x", pady=(4, 2))

        self.after(50, self._apply_safe_mode)

    def _set_player_start_visible(self, visible: bool):
        if visible:
            self._player_start_sep.pack(fill="x", pady=6)
            self._player_start_frame.pack(fill="x")
        else:
            self._player_start_sep.pack_forget()
            self._player_start_frame.pack_forget()

    # ── Stats editor popup ────────────────────────────────────────────────────

    def _open_stats_editor(self):
        if not self.current_file or not is_save_file(self.current_file):
            messagebox.showwarning("No save file", "Open a SAVE*.dat first.")
            return

        with open(self.current_file, 'rb') as fh:
            raw_lines = fh.read().split(b'\r\n')

        pdata = read_all_player_data(raw_lines)
        cdata = read_all_class_data(raw_lines)
        if pdata is None or cdata is None:
            messagebox.showerror("Error", "Could not read data from this save file.")
            return

        stats      = pdata['stats']
        inv        = pdata['inv']
        hero_level = pdata['level']

        win = tk.Toplevel(self)
        win.title("Edit Player Stats")
        win.configure(bg="#1e1e2e")
        win.resizable(False, False)
        win.grab_set()

        BG2    = "#1e1e2e"
        PANEL  = "#313244"
        SEP_C  = "#45475a"
        FONT9  = ("Consolas", 9)
        FONT9B = ("Consolas", 9, "bold")
        FONT8  = ("Consolas", 8)
        FONT11B= ("Consolas", 11, "bold")

        STAT_FIELDS = [
            ("Max Life",     0,     0, 9999, "#00a8a8"),
            ("Life",         1,     0, 9999, "#a80000"),
            ("Max Mana",     2,     0, 9999, "#00a8a8"),
            ("Mana",         3,     0, 9999, "#0000a8"),
            ("Strength",     4,     0, 9999, "#5454fc"),
            ("Intelligence", 5,     0, 9999, "#5454fc"),
            ("Dexterity",    6,     0, 9999, "#5454fc"),
            ("Accuracy",     7,     0, 9999, "#5454fc"),
            ("Reputation",   8,    -6,    6, "#fcfc54"),
            ("EXP Needed",   9,     0, 9999, "#fcfc54"),
        ]
        POTIONS = [
            ("Half Life",        4,  "#fc5454"),
            ("Full Life",        5,  "#a80000"),
            ("Half Mana",        6,  "#a800a8"),
            ("Full Mana",        7,  "#0000a8"),
            ("Half Restoration", 8,  "#fcfc54"),
            ("Full Restoration", 9,  "#fcfcfc"),
            ("Cure Poison",      10, "#00a8a8"),
            ("Berserker",        11, "#000000"),
        ]
        CLASSES      = {1: "Knight", 2: "Mage", 3: "Rogue", 4: "Monk"}
        CLASS_COLORS = {1: "#a800a8", 2: "#a80000", 3: "#545454", 4: "#fcfcfc"}
        SKILLS = [
            ("ambidexterity", "Ambidexterity", "#ecec4e"),
            ("bargaining",    "Bargaining",    "#ecec4e"),
            ("scholar",       "Scholar",       "#ecec4e"),
            ("memorisation",  "Memorisation",  "#ecec4e"),
            ("markmanship",   "Markmanship",   "#ecec4e"),
        ]
        FAULTS = [
            ("cowardice", "Cowardice", "#a80000"),
            ("honor",     "Honor",     "#a80000"),
            ("rashness",  "Rashness",  "#a80000"),
        ]
        SPELLS = [
            ( 1, "Heal",               "#f38ba8"), ( 2, "Flame",              "#fab387"),
            ( 3, "Teleport",           "#89b4fa"), ( 4, "Shield",             "#a6e3a1"),
            ( 5, "Ring of Ice",        "#89dceb"), ( 6, "Black Ward",         "#cba6f7"),
            ( 7, "Invisibility",       "#cdd6f4"), ( 8, "Summon Skeleton",    "#6c7086"),
            ( 9, "Inferno",            "#fe640b"), (10, "Restore",            "#f38ba8"),
            (11, "Life Drain",         "#eba0ac"), (12, "Thunder Bolt",       "#f9e2af"),
            (13, "Shield of Fire",     "#fab387"), (14, "Deteriorate",        "#a6adc8"),
            (15, "Summon Stone Knight","#7f849c"), (16, "Earthquake",         "#e5c890"),
            (17, "Cure",               "#f38ba8"), (18, "Summon Scorpion",    "#a6e3a1"),
            (19, "Meteor",             "#fe640b"), (20, "Dark Hour",          "#f9e2af"),
        ]

        tk.Label(win, text="PLAYER STATS EDITOR", bg=BG2, fg="#89b4fa",
                 font=FONT11B, pady=8
                 ).grid(row=0, column=0, columnspan=2, sticky="ew", padx=16)
        tk.Label(win, text=f"File: {os.path.basename(self.current_file)}",
                 bg=BG2, fg="#6c7086", font=FONT8
                 ).grid(row=1, column=0, columnspan=2, sticky="w", padx=16, pady=(0, 4))

        left_frame  = tk.Frame(win, bg=BG2)
        left_frame.grid(row=2, column=0, sticky="n", padx=(12, 6), pady=(0, 8))
        right_frame = tk.Frame(win, bg=BG2)
        right_frame.grid(row=2, column=1, sticky="n", padx=(6, 12), pady=(0, 8))

        def fsep(parent, row, span=3):
            tk.Frame(parent, bg=SEP_C, height=1).grid(
                row=row, column=0, columnspan=span, sticky="ew", padx=8, pady=4)

        def fsec(parent, text, row, span=3):
            tk.Label(parent, text=text, bg=BG2, fg="#89b4fa", font=FONT9B, anchor="w"
                     ).grid(row=row, column=0, columnspan=span,
                            sticky="w", padx=8, pady=(8, 2))

        def fspin(parent, row, label, val, lo, hi, color):
            tk.Label(parent, text=f"{label}:", bg=BG2, fg=color,
                     font=FONT9B, width=16, anchor="e"
                     ).grid(row=row, column=0, padx=(8, 4), pady=3, sticky="e")
            sv = tk.StringVar(value=str(val))
            tk.Spinbox(parent, from_=lo, to=hi, textvariable=sv, width=7,
                       bg=PANEL, fg=color, font=FONT9, relief="flat", bd=1
                       ).grid(row=row, column=1, padx=4, pady=3, sticky="w")
            tk.Label(parent, text=f"({lo}–{hi})", bg=BG2, fg="#585b70", font=FONT8
                     ).grid(row=row, column=2, padx=(0, 8), sticky="w")
            return sv

        # ── Left column ───────────────────────────────────────────────────────
        fsec(left_frame, "CLASS", row=0)
        class_var  = tk.IntVar(value=cdata['class'])
        class_btns = {}
        bf = tk.Frame(left_frame, bg=BG2)
        bf.grid(row=1, column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))

        def select_class(cid):
            class_var.set(cid)
            for c, b in class_btns.items():
                b.configure(bg=CLASS_COLORS[cid] if c == cid else PANEL,
                            fg="#1e1e2e"          if c == cid else CLASS_COLORS[c])

        for cid, cname in CLASSES.items():
            b = tk.Button(bf, text=cname, font=FONT9B, bg=PANEL, fg=CLASS_COLORS[cid],
                          activebackground="#45475a", relief="flat", bd=0, padx=12, pady=5,
                          command=lambda c=cid: select_class(c))
            b.pack(side="left", padx=(0, 6))
            class_btns[cid] = b
        select_class(cdata['class'])

        fsep(left_frame, 2)
        fsec(left_frame, "SKILLS", row=3)
        skill_vars = {}
        for i, (key, label, color) in enumerate(SKILLS):
            sv = tk.IntVar(value=cdata[key])
            tk.Checkbutton(left_frame, text=label, variable=sv,
                           bg=BG2, fg=color, selectcolor=PANEL,
                           activebackground=BG2, activeforeground=color,
                           font=FONT9B, anchor="w"
                           ).grid(row=4+i, column=0, columnspan=3,
                                  sticky="w", padx=12, pady=2)
            skill_vars[key] = sv

        fsep(left_frame, 4 + len(SKILLS))
        fsec(left_frame, "FAULTS", row=5 + len(SKILLS))
        fault_vars = {}
        for i, (key, label, color) in enumerate(FAULTS):
            sv = tk.IntVar(value=cdata[key])
            tk.Checkbutton(left_frame, text=label, variable=sv,
                           bg=BG2, fg=color, selectcolor=PANEL,
                           activebackground=BG2, activeforeground=color,
                           font=FONT9B, anchor="w"
                           ).grid(row=6+len(SKILLS)+i, column=0,
                                  columnspan=3, sticky="w", padx=12, pady=2)
            fault_vars[key] = sv

        fsep(left_frame, 6 + len(SKILLS) + len(FAULTS))
        fsec(left_frame, "SPELLS", row=7 + len(SKILLS) + len(FAULTS))
        spell_vars = {}
        spell_grid = tk.Frame(left_frame, bg=BG2)
        spell_grid.grid(row=8+len(SKILLS)+len(FAULTS),
                        column=0, columnspan=3, sticky="w", padx=8, pady=(0, 4))
        for idx, (sid, name, color) in enumerate(SPELLS):
            col = idx % 2
            row = idx // 2
            cell = tk.Frame(spell_grid, bg=BG2)
            cell.grid(row=row, column=col, sticky="w", padx=(0, 12), pady=1)
            tk.Label(cell, text=f"{sid:2d}.", bg=BG2, fg="#585b70",
                     font=FONT8, width=3, anchor="e").pack(side="left")
            sv = tk.IntVar(value=cdata['spell_flags'][idx])
            tk.Checkbutton(cell, text=name, variable=sv,
                           bg=BG2, fg=color, selectcolor=PANEL,
                           activebackground=BG2, activeforeground=color,
                           font=FONT9B, anchor="w", width=18).pack(side="left")
            spell_vars[sid] = sv

        # ── Right column ──────────────────────────────────────────────────────
        fsec(right_frame, "GOLD", row=0)
        gold_sv = fspin(right_frame, 1, "Gold", inv[3], 0, 99999, "#f9e2af")

        fsep(right_frame, 2)
        fsec(right_frame, "PLAYER LEVEL", row=3)
        level_sv = fspin(right_frame, 4, "Player Level", hero_level, 0, 999, "#fcfc54")

        fsep(right_frame, 5)
        fsec(right_frame, "COMBAT STATS", row=6)
        stat_vars = []
        for i, (label, idx, lo, hi, color) in enumerate(STAT_FIELDS):
            sv = fspin(right_frame, 7+i, label, stats[idx], lo, hi, color)
            stat_vars.append((idx, sv, lo, hi))

        fsep(right_frame, 7 + len(STAT_FIELDS))
        fsec(right_frame, "POTIONS", row=8 + len(STAT_FIELDS))
        potion_vars = []
        for j, (name, field_idx, color) in enumerate(POTIONS):
            r = 9 + len(STAT_FIELDS) + j
            cell = tk.Frame(right_frame, bg=BG2)
            cell.grid(row=r, column=0, padx=(8, 4), pady=3, sticky="e")
            tk.Frame(cell, bg=color, width=10, height=10).pack(side="left", padx=(0, 4))
            tk.Label(cell, text=f"{name}:", bg=BG2, fg="#cdd6f4",
                     font=FONT9B, anchor="e").pack(side="left")
            sv = tk.StringVar(value=str(inv[field_idx]))
            tk.Spinbox(right_frame, from_=0, to=999, textvariable=sv, width=7,
                       bg=PANEL, fg=color, font=FONT9, relief="flat", bd=1
                       ).grid(row=r, column=1, padx=4, pady=3, sticky="w")
            tk.Label(right_frame, text="(0–999)", bg=BG2, fg="#585b70", font=FONT8
                     ).grid(row=r, column=2, padx=(0, 8), sticky="w")
            potion_vars.append((field_idx, sv))

        # ── Buttons ───────────────────────────────────────────────────────────
        tk.Frame(win, bg=SEP_C, height=1).grid(
            row=3, column=0, columnspan=2, sticky="ew", padx=12, pady=4)
        btn_row = tk.Frame(win, bg=BG2)
        btn_row.grid(row=4, column=0, columnspan=2, pady=(4, 12), padx=16, sticky="ew")

        def _apply():
            errors = []
            try:   new_gold  = int(gold_sv.get())
            except ValueError:
                errors.append("  Gold is not a valid integer");  new_gold  = None
            try:   new_level = int(level_sv.get())
            except ValueError:
                errors.append("  Player Level is not a valid integer"); new_level = None

            new_stats = list(stats)
            for idx, sv, lo, hi in stat_vars:
                try:
                    v = int(sv.get().strip())
                except ValueError:
                    errors.append(f"  {STAT_FIELDS[idx][0]}: not a valid integer"); continue
                if not (lo <= v <= hi):
                    errors.append(f"  {STAT_FIELDS[idx][0]}: {v} out of range {lo}–{hi}"); continue
                new_stats[idx] = v

            new_inv = list(inv)
            for field_idx, sv in potion_vars:
                try:    new_inv[field_idx] = int(sv.get())
                except ValueError:
                    errors.append(f"  Potion field [{field_idx}]: not a valid integer")

            if errors:
                messagebox.showerror("Invalid values", "\n".join(errors), parent=win)
                return

            new_inv[3] = new_gold

            new_cdata = dict(cdata)
            new_cdata['class'] = class_var.get()
            for key in skill_vars:  new_cdata[key] = skill_vars[key].get()
            for key in fault_vars:  new_cdata[key] = fault_vars[key].get()

            new_spell_flags = [spell_vars[sid].get() for sid, *_ in SPELLS]
            new_cdata['spell_flags'] = new_spell_flags
            known_ids = [sid for sid, *_ in SPELLS if spell_vars[sid].get()]
            padded = (known_ids + [0] * 20)[:20]
            new_cdata['spell_left']  = padded[:10]
            new_cdata['spell_right'] = padded[10:]

            try:
                write_all_player_data(self.current_file, new_level, new_stats, new_inv)
                write_all_class_data(self.current_file, new_cdata)
                # Refresh hero sprite immediately from the new class
                self.player_class_id = new_cdata['class']
                self._draw_start_marker()
                self.status_var.set(
                    f"Saved — Life:{new_stats[0]}  Mana:{new_stats[2]}  "
                    f"Lv:{new_level}  Gold:{new_gold}  Spells:{len(known_ids)}")
                win.destroy()
            except Exception as e:
                messagebox.showerror("Save error", str(e), parent=win)

        tk.Button(btn_row, text="Apply & Save", font=FONT9B,
                  bg="#a6e3a1", fg="#1e1e2e", activebackground="#cdefcf",
                  relief="flat", bd=0, padx=12, pady=6,
                  command=_apply).pack(side="left", expand=True, fill="x", padx=(0, 4))
        tk.Button(btn_row, text="Cancel", font=FONT9,
                  bg="#45475a", fg="#cdd6f4", activebackground="#585b70",
                  relief="flat", bd=0, padx=12, pady=6,
                  command=win.destroy).pack(side="left", expand=True, fill="x", padx=(4, 0))

        # Centre popup on screen
        win.update_idletasks()
        _center_window(win, win.winfo_reqwidth(), win.winfo_reqheight())

    def _build_info(self, parent):
        ttk.Separator(parent, orient="horizontal").pack(fill="x", pady=6)
        tk.Label(parent, text="TILE INFO", bg="#1e1e2e",
                 fg="#89b4fa", font=("Consolas", 10, "bold")).pack(anchor="w")
        self.info_text = tk.Text(parent, height=8, bg="#181825", fg="#cdd6f4",
                                 font=("Consolas", 8), relief="flat", state="disabled")
        self.info_text.pack(fill="x")

    # ── Swatch / preview helpers ───────────────────────────────────────────────

    def _color_to_rgb(self, hex_color: str) -> tuple[int, int, int]:
        h = hex_color.lstrip("#")
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)

    def _solid_swatch(self, color: str) -> Image.Image:
        return Image.new("RGBA", (_SWATCH, _SWATCH), self._color_to_rgb(color) + (255,))

    def _composite_layers(self, tile_type: int, variant: int,
                           obj_id: int, enemy_id: int, extra_id: int,
                           gold: int, size: int) -> Image.Image:
        """Composite all sprite layers: type → var → extra → gold → enemy → object."""
        color = tile_color(tile_type, variant)
        img   = Image.new("RGBA", (size, size), self._color_to_rgb(color) + (255,))
        for sdict, key in [
            (TILE_TYPE_SPRITES, tile_type),
            (VARIANT_SPRITES,   variant),
            (EXTRA_SPRITES,     extra_id),
            (ENEMY_SPRITES,     enemy_id),
            (OBJECT_SPRITES,    obj_id),
        ]:
            stem = sdict.get(key, "")
            if stem:
                p = os.path.join(SPRITES_DIR, stem + ".png")
                if os.path.exists(p):
                    layer = Image.open(p).convert("RGBA").resize((size, size), Image.NEAREST)
                    img.paste(layer, (0, 0), layer)
            if sdict is EXTRA_SPRITES and gold > 0:
                p = os.path.join(SPRITES_DIR, "gold.png")
                if os.path.exists(p):
                    layer = Image.open(p).convert("RGBA").resize((size, size), Image.NEAREST)
                    img.paste(layer, (0, 0), layer)
        return img

    def _set_swatch(self, label: tk.Label, photo: ImageTk.PhotoImage, key: str):
        self._swatch_imgs[key] = photo
        label.configure(image=photo, width=_SWATCH, height=_SWATCH)

    def _update_all_swatches(self):
        self._on_type_changed(); self._on_var_changed()
        self._on_obj_changed();  self._on_enemy_changed()
        self._on_extra_changed(); self._on_gold_changed()
        self._update_selection()

    def _on_type_changed(self):
        try:   tid = int(self.type_var.get())
        except (ValueError, tk.TclError): return
        self.selected_tile_type = tid
        stem  = TILE_TYPE_SPRITES.get(tid, "")
        color = TILE_TYPE_COLORS.get(tid, "#ff00ff")
        if stem:
            p   = os.path.join(SPRITES_DIR, stem + ".png")
            img = (Image.open(p).convert("RGBA").resize((_SWATCH, _SWATCH), Image.NEAREST)
                   if os.path.exists(p) else self._solid_swatch(color))
        else:
            img = self._solid_swatch(color)
        self._set_swatch(self._sw_type, ImageTk.PhotoImage(img), "type")
        self._info_type.configure(
            text=_sprite_label(stem, f"floor_{tid}") if stem else (f"floor_{tid}" if tid != 0 else "—"))
        self._refresh_var_swatch()
        self._update_preview()
        self._update_selection()

    def _blank_swatch(self, sw: tk.Label, key: str, info: tk.Label):
        img   = self._solid_swatch("#1e1e2e")
        photo = ImageTk.PhotoImage(img)
        self._swatch_imgs[key] = photo
        sw.configure(image=photo, width=_SWATCH, height=_SWATCH)
        info.configure(text="")

    def _on_var_changed(self):
        raw = self.var_var.get().strip()
        if raw == "":
            self.selected_variant = 0
            self._blank_swatch(self._sw_var, "var", self._info_var)
            self._update_preview(); return
        try:   v = int(raw)
        except (ValueError, tk.TclError): return
        self.selected_variant = v
        self._refresh_var_swatch(); self._update_preview(); self._update_selection()

    def _refresh_var_swatch(self):
        img  = self._composite_layers(self.selected_tile_type, self.selected_variant, 0, 0, 0, 0, _SWATCH)
        self._set_swatch(self._sw_var, ImageTk.PhotoImage(img), "var")
        stem = VARIANT_SPRITES.get(self.selected_variant, "")
        self._info_var.configure(
            text=_sprite_label(stem, f"wall_{self.selected_variant}") if stem
            else ("—" if self.selected_variant == 0 else f"wall_{self.selected_variant}"))

    def _on_obj_changed(self):
        raw = self.obj_var.get().strip()
        if raw == "":
            self.selected_object = 0
            self._blank_swatch(self._sw_obj, "obj", self._info_obj)
            self._update_preview(); return
        try:   oid = int(raw)
        except (ValueError, tk.TclError): return
        self.selected_object = oid
        stem = OBJECT_SPRITES.get(oid, "")
        if stem:
            p    = os.path.join(SPRITES_DIR, stem + ".png")
            img  = Image.open(p).convert("RGBA").resize((_SWATCH, _SWATCH), Image.NEAREST)
            name = _sprite_label(stem, stem)
        else:
            img  = self._solid_swatch(_obj_fallback_color(oid))
            name = f"object_{oid}" if oid != 0 else "—"
        self._set_swatch(self._sw_obj, ImageTk.PhotoImage(img), "obj")
        self._info_obj.configure(text=name)
        self._update_preview(); self._update_selection()

    def _on_enemy_changed(self):
        raw = self.enemy_var.get().strip()
        if raw == "":
            self.selected_enemy = 0
            self._blank_swatch(self._sw_enemy, "enemy", self._info_enemy)
            self._update_preview(); return
        try:   eid = int(raw)
        except (ValueError, tk.TclError): return
        self.selected_enemy = eid
        stem = ENEMY_SPRITES.get(eid, "")
        if stem:
            p    = os.path.join(SPRITES_DIR, stem + ".png")
            img  = Image.open(p).convert("RGBA").resize((_SWATCH, _SWATCH), Image.NEAREST)
            name = _sprite_label(stem, stem)
        else:
            img  = self._solid_swatch("#ff4444")
            name = f"enemy_{eid}" if eid != 0 else "—"
        self._set_swatch(self._sw_enemy, ImageTk.PhotoImage(img), "enemy")
        self._info_enemy.configure(text=name)
        self._update_preview(); self._update_selection()

    def _on_extra_changed(self):
        raw = self.extra_var.get().strip()
        if raw == "":
            self.selected_extra = 0
            self._blank_swatch(self._sw_extra, "extra", self._info_extra)
            self._update_preview(); return
        try:   xid = int(raw)
        except (ValueError, tk.TclError): return
        self.selected_extra = xid
        stem = EXTRA_SPRITES.get(xid, "")
        if stem:
            p    = os.path.join(SPRITES_DIR, stem + ".png")
            img  = Image.open(p).convert("RGBA").resize((_SWATCH, _SWATCH), Image.NEAREST)
            name = _sprite_label(stem, stem)
        else:
            img  = self._solid_swatch("#45475a")
            name = f"extra_{xid}" if xid != 0 else "—"
        self._set_swatch(self._sw_extra, ImageTk.PhotoImage(img), "extra")
        self._info_extra.configure(text=name)
        self._update_preview(); self._update_selection()

    def _on_gold_changed(self):
        raw = self.gold_var.get().strip()
        if raw == "":
            self.selected_gold = 0
            self._blank_swatch(self._sw_gold, "gold", self._info_gold)
            self._update_preview(); return
        try:   gld = int(raw)
        except (ValueError, tk.TclError): return
        self.selected_gold = gld
        if gld > 0:
            p   = os.path.join(SPRITES_DIR, "gold.png")
            img = (Image.open(p).convert("RGBA").resize((_SWATCH, _SWATCH), Image.NEAREST)
                   if os.path.exists(p) else self._solid_swatch("#f9e2af"))
            self._set_swatch(self._sw_gold, ImageTk.PhotoImage(img), "gold")
            self._info_gold.configure(text=str(gld))
        else:
            self._blank_swatch(self._sw_gold, "gold", self._info_gold)
        self._update_preview(); self._update_selection()

    def _update_preview(self):
        try:
            tid = int(self.type_var.get());  var = int(self.var_var.get())
            oid = int(self.obj_var.get());   eid = int(self.enemy_var.get())
            xid = int(self.extra_var.get()); gld = int(self.gold_var.get())
        except (ValueError, tk.TclError): return
        img   = self._composite_layers(tid, var, oid, eid, xid, gld, _PREVIEW)
        photo = ImageTk.PhotoImage(img)
        self._swatch_imgs["preview"] = photo
        self._preview_lbl.configure(image=photo, width=_PREVIEW, height=_PREVIEW)

    def _update_selection(self):
        def _get(var, default=0):
            try:    return int(var.get())
            except: return default
        self.selected_tile_type = _get(self.type_var,  1)
        self.selected_variant   = _get(self.var_var,   0)
        self.selected_object    = _get(self.obj_var,   0)
        self.selected_enemy     = _get(self.enemy_var, 0)
        self.selected_gold      = _get(self.gold_var,  0)
        self.selected_extra     = _get(self.extra_var, 0)

    # ── Map I/O ───────────────────────────────────────────────────────────────

    def _new_map(self):
        self.grid_data       = [[[1, 0, 0, 0, 0, 0] for _ in range(MAP_SIZE)]
                                 for _ in range(MAP_SIZE)]
        self.current_file    = None
        self.player_class_id = 1
        self.title("The Quest — Level Editor — [New Map]")
        self._set_player_start_visible(False)
        self._redraw()

    _VALID_FILE = _re.compile(r'^(L0000[1-7]|SAVE\d+)\.DAT$', _re.IGNORECASE)

    def _open(self):
        path = filedialog.askopenfilename(
            initialdir=DATA_DIR,
            title="Open Level or Save File",
            filetypes=[("Quest data files", ("L0000?.dat", "SAVE*.dat",
                                             "l0000?.dat", "save*.dat")),
                       ("All files", "*.*")])
        if not path:
            return
        if not self._VALID_FILE.match(os.path.basename(path)):
            messagebox.showerror("Unsupported File",
                "Only L00001.dat – L00007.dat and SAVE*.dat files are supported.")
            return
        try:
            self.grid_data    = load_map(path)
            self.current_file = path
            name = os.path.basename(path)
            if is_save_file(path):
                with open(path, 'rb') as fh:
                    raw_lines = fh.read().split(b'\r\n')
                pos                  = read_player_pos(raw_lines)
                self.player_class_id = read_player_class(raw_lines)
                self.start_pos       = pos if pos else (1, 1)
                self.start_pos_lbl.configure(
                    text=f"({self.start_pos[0]}, {self.start_pos[1]})")
                self._set_player_start_visible(True)
                self.status_var.set(f"Opened save: {name}  |  Player at {self.start_pos}")
            else:
                self.start_pos       = (1, 1)
                self.player_class_id = 1
                self._set_player_start_visible(False)
                self.status_var.set(f"Opened level: {name}")
            self.title(f"The Quest — Level Editor — {name}")
            self._redraw()
            if is_save_file(path):
                # Scroll to centre on the player position after the canvas is drawn
                self.after(20, lambda: self._scroll_to_tile(*self.start_pos))
        except Exception as e:
            messagebox.showerror("Error", f"Could not load file:\n{e}")

    def _save(self):
        if not self.current_file:
            self._save_as()
            return
        self._do_save(self.current_file)

    def _save_as(self):
        path = filedialog.asksaveasfilename(
            initialdir=DATA_DIR, title="Save Level As",
            defaultextension=".dat", filetypes=[("DAT files", "*.dat")])
        if path:
            self._do_save(path)
            self.current_file = path
            self.title(f"The Quest — Level Editor — {os.path.basename(path)}")

    def _do_save(self, path: str):
        try:
            if is_save_file(path):
                save_save_file(path, self.grid_data, self.start_pos)
                px, py = self.start_pos
                self.status_var.set(
                    f"Saved: {os.path.basename(path)}  |  Player at ({px}, {py})")
            else:
                save_map(path, self.grid_data)
                self.status_var.set(f"Saved: {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not save:\n{e}")

    def _export_png(self):
        if self.grid_data is None:
            messagebox.showwarning("No map", "Open or create a map first.")
            return
        default = ""
        if self.current_file:
            base    = os.path.splitext(os.path.basename(self.current_file))[0]
            default = os.path.join(os.path.dirname(self.current_file), base + ".png")
        path = filedialog.asksaveasfilename(
            initialfile=os.path.basename(default) if default else "map.png",
            initialdir=os.path.dirname(default) if default else DATA_DIR,
            title="Export map as PNG", defaultextension=".png",
            filetypes=[("PNG image", "*.png")])
        if not path:
            return
        self.status_var.set("Rendering map image…")
        self.update_idletasks()
        try:
            from PIL import ImageDraw
            size = MAP_SIZE * CELL
            canvas_img = Image.new("RGBA", (size, size))
            for y in range(MAP_SIZE):
                for x in range(MAP_SIZE):
                    tile = self.grid_data[y][x]
                    tile_type, variant, obj_id, enemy_id, gold, extra_id = tile
                    canvas_img.paste(
                        self._composite_layers(tile_type, variant, obj_id, enemy_id, extra_id, gold, CELL),
                        (x * CELL, y * CELL))
            draw = ImageDraw.Draw(canvas_img)
            if self.show_tile_grid.get():
                for i in range(MAP_SIZE + 1):
                    draw.line([(0, i*CELL), (size, i*CELL)], fill="#2a2a3e", width=1)
                    draw.line([(i*CELL, 0), (i*CELL, size)], fill="#2a2a3e", width=1)
            if self.show_screen_grid.get():
                for i in range(0, MAP_SIZE + 1, 10):
                    draw.line([(0, i*CELL), (size, i*CELL)], fill="#000000", width=2)
                    draw.line([(i*CELL, 0), (i*CELL, size)], fill="#000000", width=2)
            canvas_img.convert("RGB").save(path, "PNG")
            self.status_var.set(f"Exported {size}×{size} px → {os.path.basename(path)}")
        except Exception as e:
            messagebox.showerror("Export failed", str(e))

    def _apply_safe_mode(self):
        safe = self.safe_mode.get()
        mappings = [
            (self._sp_type,  self.type_var,  TILE_TYPE_SPRITES),
            (self._sp_var,   self.var_var,   VARIANT_SPRITES),
            (self._sp_obj,   self.obj_var,   OBJECT_SPRITES),
            (self._sp_enemy, self.enemy_var, ENEMY_SPRITES),
            (self._sp_extra, self.extra_var, EXTRA_SPRITES),
        ]
        saved = [(var, var.get()) for _, var, _ in mappings]
        for sp, var, sdict in mappings:
            lo, hi = self._sp_ranges[sp]
            if safe and sdict:
                keys = sorted(set(sdict.keys()) | {0})
                sp.configure(values=[str(k) for k in keys], from_=min(keys), to=max(keys))
            else:
                sp.configure(values=[], from_=lo, to=hi)

        def _restore():
            for var, val in saved:
                var.set(val)
            self._update_all_swatches()

        self.after(1, _restore)
        self.status_var.set("Safe Mode ON — spinboxes cycle sprite IDs only"
                            if safe else "Safe Mode OFF — free numeric input")

    # ── Drawing ───────────────────────────────────────────────────────────────

    def _redraw(self):
        """Full canvas redraw. Tagged layers ensure grids are always above tiles
        and the start marker is always on top."""
        if self.grid_data is None:
            return
        cs    = self.cell_size
        total = MAP_SIZE * cs

        # Delete every tagged layer; the canvas is fully rebuilt below
        self.canvas.delete("tile", "grid_tile", "grid_screen", "start_marker", "hover")
        self.canvas.configure(scrollregion=(0, 0, total, total))

        for y in range(MAP_SIZE):
            for x in range(MAP_SIZE):
                self._draw_tile(x, y)

        # Fine tile grid — drawn once after all tiles, always on top of them
        if cs >= 4 and self.show_tile_grid.get():
            for i in range(MAP_SIZE + 1):
                self.canvas.create_line(0, i*cs, total, i*cs,
                                        fill="#2a2a3e", width=1, tags="grid_tile")
                self.canvas.create_line(i*cs, 0, i*cs, total,
                                        fill="#2a2a3e", width=1, tags="grid_tile")

        # Screen boundary grid — on top of tile grid
        if self.show_screen_grid.get():
            for i in range(0, MAP_SIZE + 1, 10):
                self.canvas.create_line(0, i*cs, total, i*cs,
                                        fill="#000000", width=2, tags="grid_screen")
                self.canvas.create_line(i*cs, 0, i*cs, total,
                                        fill="#000000", width=2, tags="grid_screen")

        self._draw_start_marker()

    def _draw_start_marker(self):
        """Draw the class-specific hero sprite at start_pos; 'P' text as fallback."""
        self.canvas.delete("start_marker")
        if self.grid_data is None or not is_save_file(self.current_file or ""):
            return
        cs     = self.cell_size
        sx, sy = self.start_pos
        x0     = (sx - 1) * cs
        y0     = (sy - 1) * cs
        hero   = _load_sprite(_CLASS_SPRITE.get(self.player_class_id, "hero_Knight"), cs)
        if hero:
            self.canvas.create_image(x0, y0, anchor="nw",
                                     image=hero, tags="start_marker")
        else:
            fsz = max(6, min(cs - 4, 18))
            self.canvas.create_text(x0 + cs//2, y0 + cs//2, text="P",
                                    fill="#a6e3a1", font=("Consolas", fsz, "bold"),
                                    tags="start_marker")

    def _draw_tile(self, x: int, y: int):
        cs   = self.cell_size
        tile = self.grid_data[y][x]
        tile_type, variant, obj_id, enemy_id = tile[0], tile[1], tile[2], tile[3]
        x0, y0 = x * cs, y * cs

        # Layer 1: base type
        self.canvas.create_rectangle(x0, y0, x0+cs, y0+cs,
                                     fill=tile_color(tile_type, variant),
                                     outline="", tags="tile")
        spr = _load_sprite(TILE_TYPE_SPRITES.get(tile_type, ""), cs)
        if spr:
            self.canvas.create_image(x0, y0, anchor="nw", image=spr, tags="tile")

        # Layer 2: variant overlay
        spr = _load_sprite(VARIANT_SPRITES.get(variant, ""), cs)
        if spr:
            self.canvas.create_image(x0, y0, anchor="nw", image=spr, tags="tile")

        # Layer 3: extra
        extra_id = tile[5]
        if extra_id != 0:
            spr = _load_sprite(EXTRA_SPRITES.get(extra_id, ""), cs)
            if spr:
                self.canvas.create_image(x0, y0, anchor="nw", image=spr, tags="tile")

        # Layer 4: gold
        gold = tile[4]
        if gold > 0:
            spr = _load_sprite("gold", cs)
            if spr:
                self.canvas.create_image(x0, y0, anchor="nw", image=spr, tags="tile")

        # Layer 5: enemy
        if enemy_id != 0:
            spr = _load_sprite(ENEMY_SPRITES.get(enemy_id, ""), cs)
            if spr:
                self.canvas.create_image(x0, y0, anchor="nw", image=spr, tags="tile")
            else:
                r  = max(2, cs // 6)
                cx, cy = x0 + cs//2, y0 + cs//2
                self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                        fill="#ff4444", outline="", tags="tile")

        # Layer 6: object
        if obj_id != 0:
            spr = _load_sprite(OBJECT_SPRITES.get(obj_id, ""), cs)
            if spr:
                self.canvas.create_image(x0, y0, anchor="nw", image=spr, tags="tile")
            else:
                col = _obj_fallback_color(obj_id)
                if cs >= 8:
                    r  = max(1, cs // 3)
                    cx, cy = x0 + cs//2, y0 + cs//2
                    self.canvas.create_oval(cx-r, cy-r, cx+r, cy+r,
                                            fill=col, outline="", tags="tile")
                else:
                    self.canvas.create_rectangle(x0, y0, x0+cs, y0+cs,
                                                 fill=col, outline="", tags="tile")

    def _draw_hover(self):
        if self.hover_x < 0 or self.grid_data is None:
            return
        cs = self.cell_size
        x0, y0 = self.hover_x * cs, self.hover_y * cs
        self.canvas.delete("hover")
        self.canvas.create_rectangle(x0, y0, x0+cs, y0+cs,
                                     outline="#f5c2e7", width=2, tags="hover")

    # ── Paint — single-tile update without full redraw ─────────────────────────

    def _paint(self, x: int, y: int):
        if self.grid_data is None:
            return
        self._update_selection()
        self.grid_data[y][x] = [
            self.selected_tile_type, self.selected_variant,
            self.selected_object,    self.selected_enemy,
            self.selected_gold,      self.selected_extra,
        ]

        # Remove only the "tile"-tagged items that lie within this cell's pixel rect.
        # Grid lines ("grid_tile", "grid_screen") and the start marker live on
        # separate tags and are never touched here.
        cs = self.cell_size
        x0, y0 = x * cs, y * cs
        tile_ids = set(self.canvas.find_withtag("tile"))
        for iid in self.canvas.find_overlapping(x0, y0, x0+cs-1, y0+cs-1):
            if iid in tile_ids:
                self.canvas.delete(iid)

        self._draw_tile(x, y)

        # Redraw grid lines over this tile so they remain on top
        total = MAP_SIZE * cs
        if cs >= 4 and self.show_tile_grid.get():
            for ex in (x0, x0+cs):
                self.canvas.create_line(ex, y0, ex, y0+cs,
                                        fill="#2a2a3e", width=1, tags="grid_tile")
            for ey in (y0, y0+cs):
                self.canvas.create_line(x0, ey, x0+cs, ey,
                                        fill="#2a2a3e", width=1, tags="grid_tile")
        if self.show_screen_grid.get():
            for edge in (x, x+1):
                if edge % 10 == 0:
                    self.canvas.create_line(edge*cs, 0, edge*cs, total,
                                            fill="#000000", width=2, tags="grid_screen")
            for edge in (y, y+1):
                if edge % 10 == 0:
                    self.canvas.create_line(0, edge*cs, total, edge*cs,
                                            fill="#000000", width=2, tags="grid_screen")

        # If we painted over the start marker tile, redraw it on top
        sx, sy = self.start_pos
        if (sx - 1) == x and (sy - 1) == y:
            self._draw_start_marker()

        self._draw_hover()

    # ── Viewport helpers ──────────────────────────────────────────────────────

    def _scroll_to_tile(self, tile_x: int, tile_y: int):
        """Scroll so that map tile (tile_x, tile_y) [1-based] is centred."""
        self.canvas.update_idletasks()
        cs    = self.cell_size
        total = MAP_SIZE * cs
        vw    = self.canvas.winfo_width()
        vh    = self.canvas.winfo_height()
        px    = (tile_x - 1) * cs + cs // 2
        py    = (tile_y - 1) * cs + cs // 2
        self.canvas.xview_moveto(max(0.0, min(1.0, (px - vw / 2) / total)))
        self.canvas.yview_moveto(max(0.0, min(1.0, (py - vh / 2) / total)))

    # ── Zoom ──────────────────────────────────────────────────────────────────

    def _set_zoom_idx(self, idx: int, *,
                      center: bool = False,
                      pivot_canvas: tuple[float, float] | None = None):
        """Change zoom level and adjust scroll to keep the pivot point stable.

        pivot_canvas — (cx, cy) canvas-coord point to zoom toward (mouse zoom).
        center       — keep the current viewport centre stable (button zoom).
        """
        old_cs = self.cell_size
        self._zoom_idx = idx
        self.cell_size = ZOOM_STEPS[idx]
        new_cs = self.cell_size

        pct = round(new_cs / CELL * 100)
        self.title(
            "The Quest — Level Editor"
            + (f" — {os.path.basename(self.current_file)}" if self.current_file else "")
            + f"  [{pct}%]"
        )

        # Capture pivot in fractional tile space BEFORE redraw changes cell_size
        if pivot_canvas is not None:
            tile_fx = pivot_canvas[0] / old_cs
            tile_fy = pivot_canvas[1] / old_cs
            # We want the same screen pixel (pivot_canvas[0/1] relative to viewport)
            # to remain over tile_fx/tile_fy after zoom.
            # However pivot_canvas is already a canvas coord (not widget coord),
            # so the widget offset must be accounted for separately.
            # Store the widget-space offset of the pivot for post-redraw use.
            vx_before = self.canvas.canvasx(0)   # canvas x of viewport left edge
            vy_before = self.canvas.canvasy(0)
            widget_px = pivot_canvas[0] - vx_before   # pixel inside viewport
            widget_py = pivot_canvas[1] - vy_before
        elif center:
            self.canvas.update_idletasks()
            vw = self.canvas.winfo_width()
            vh = self.canvas.winfo_height()
            cx_before = self.canvas.canvasx(vw / 2)
            cy_before = self.canvas.canvasy(vh / 2)
            tile_fx = cx_before / old_cs
            tile_fy = cy_before / old_cs
            widget_px = vw / 2
            widget_py = vh / 2
        else:
            tile_fx = tile_fy = widget_px = widget_py = None

        self._redraw()

        if tile_fx is not None:
            self.canvas.update_idletasks()
            total = MAP_SIZE * new_cs
            # New canvas position of the pivoted tile
            new_canvas_px = tile_fx * new_cs
            new_canvas_py = tile_fy * new_cs
            # We want 'new_canvas_px' to appear at 'widget_px' inside the viewport
            want_left = new_canvas_px - widget_px
            want_top  = new_canvas_py - widget_py
            self.canvas.xview_moveto(max(0.0, min(1.0, want_left / total if total > 0 else 0.0)))
            self.canvas.yview_moveto(max(0.0, min(1.0, want_top  / total if total > 0 else 0.0)))

    # ── Mouse / scroll events ─────────────────────────────────────────────────

    def _canvas_to_tile(self, event) -> tuple[int, int]:
        cx = int(self.canvas.canvasx(event.x))
        cy = int(self.canvas.canvasy(event.y))
        return cx // self.cell_size, cy // self.cell_size

    def _on_hover(self, event):
        tx, ty = self._canvas_to_tile(event)
        if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
            if tx != self.hover_x or ty != self.hover_y:
                self.hover_x, self.hover_y = tx, ty
                self._draw_hover()
                self._update_info(tx, ty)
                self.status_var.set(f"Tile ({tx+1}, {ty+1})")
        if self.is_painting and 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
            self._paint(tx, ty)

    def _on_leave(self, event):
        self.canvas.delete("hover")
        self.hover_x = self.hover_y = -1

    def _on_paint_start(self, event):
        tx, ty = self._canvas_to_tile(event)
        if self.mode == "set_start":
            if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
                self._set_start_at(tx, ty)
            return
        if self.mode == "copy_tile":
            if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
                self._load_tile_into_palette(tx, ty)
                self.status_var.set(f"Copied tile ({tx+1}, {ty+1}) into palette")
                self._cancel_mode()
            return
        self.is_painting = True
        if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
            self._paint(tx, ty)

    def _on_paint_drag(self, event):
        if self.mode == "set_start":
            return
        tx, ty = self._canvas_to_tile(event)
        if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE:
            self._paint(tx, ty)

    def _on_paint_end(self, event):
        self.is_painting = False

    def _load_tile_into_palette(self, tx: int, ty: int):
        t = self.grid_data[ty][tx]
        self.type_var.set(t[0]);  self.var_var.set(t[1])
        self.obj_var.set(t[2]);   self.enemy_var.set(t[3])
        self.gold_var.set(t[4]);  self.extra_var.set(t[5])
        self._update_selection()

    def _on_pick(self, event):
        tx, ty = self._canvas_to_tile(event)
        if 0 <= tx < MAP_SIZE and 0 <= ty < MAP_SIZE and self.grid_data:
            self._load_tile_into_palette(tx, ty)

    def _toggle_copy_mode(self):
        if self.mode == "copy_tile":
            self._cancel_mode()
        else:
            self.mode = "copy_tile"
            self.copy_tile_btn.configure(bg="#89b4fa", fg="#1e1e2e",
                                         text="Copy Tile  [click tile]  [Esc cancels]")
            self.canvas.configure(cursor="crosshair")
            self.status_var.set("COPY MODE — click any tile to load it into the palette")

    def _on_scroll(self, event):
        if event.state & 0x1:  # Shift → horizontal scroll
            self.canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:  # default → zoom toward mouse cursor
            new_idx = self._zoom_idx + (1 if event.delta > 0 else -1)
            new_idx = max(0, min(len(ZOOM_STEPS) - 1, new_idx))
            if new_idx != self._zoom_idx:
                mx = self.canvas.canvasx(event.x)
                my = self.canvas.canvasy(event.y)
                self._set_zoom_idx(new_idx, pivot_canvas=(mx, my))

    def _on_pan_start(self, event):
        self.canvas.scan_mark(event.x, event.y)

    def _on_pan_drag(self, event):
        # gain=-1 inverts the drag so the map follows the mouse direction
        self.canvas.scan_dragto(event.x, event.y, gain=1)

    # ── Player start mode ─────────────────────────────────────────────────────

    def _toggle_set_start_mode(self):
        if self.mode == "set_start":
            self._cancel_mode()
        else:
            self.mode = "set_start"
            self.set_start_btn.configure(bg="#a6e3a1", fg="#1e1e2e",
                                         text="Click tile to set start  [Esc cancels]")
            self.canvas.configure(cursor="crosshair")
            self.status_var.set("START MODE — click any tile to place the player start")

    def _cancel_mode(self):
        self.mode = "paint"
        if hasattr(self, "set_start_btn"):
            self.set_start_btn.configure(bg="#313244", fg="#cdd6f4",
                                         text="Click tile to set start")
        if hasattr(self, "copy_tile_btn"):
            self.copy_tile_btn.configure(bg="#45475a", fg="#cdd6f4", text="Copy Tile")
        self.canvas.configure(cursor="crosshair")

    def _set_start_at(self, tx: int, ty: int):
        self.start_pos = (tx + 1, ty + 1)
        self.start_pos_lbl.configure(text=f"({tx+1}, {ty+1})")
        self._cancel_mode()
        self._draw_start_marker()
        self.status_var.set(f"Player start → ({tx+1}, {ty+1}) — save to apply")

    # ── Info panel ────────────────────────────────────────────────────────────

    def _update_info(self, x: int, y: int):
        if self.grid_data is None:
            return
        t, v, obj, ene, fl, ex = self.grid_data[y][x]
        floor_stem = TILE_TYPE_SPRITES.get(t, "")
        wall_stem  = VARIANT_SPRITES.get(v, "")
        obj_stem   = OBJECT_SPRITES.get(obj, "")
        ene_stem   = ENEMY_SPRITES.get(ene, "")
        extra_stem = EXTRA_SPRITES.get(ex, "")
        floor_str  = f"{t} ({_sprite_label(floor_stem, floor_stem)})" if floor_stem else str(t)
        wall_str   = f"{v} ({_sprite_label(wall_stem,  wall_stem)})"  if wall_stem  else str(v)
        obj_str    = f"{obj} ({_sprite_label(obj_stem,   obj_stem)})"  if obj_stem   else (str(obj) if obj else "—")
        ene_str    = f"{ene} ({_sprite_label(ene_stem,   ene_stem)})"  if ene_stem   else (str(ene) if ene else "—")
        extra_str  = f"{ex}  ({_sprite_label(extra_stem, extra_stem)})" if extra_stem else (str(ex)  if ex  else "—")
        info = (f"Position : ({x+1}, {y+1})\n"
                f"Floor    : {floor_str}\n"
                f"Wall     : {wall_str}\n"
                f"Object   : {obj_str}\n"
                f"Enemy    : {ene_str}\n"
                f"Extra    : {extra_str}\n"
                f"Gold     : {fl if fl else '—'}")
        self.info_text.configure(state="normal")
        self.info_text.delete("1.0", "end")
        self.info_text.insert("1.0", info)
        self.info_text.configure(state="disabled")


if __name__ == "__main__":
    app = LevelEditor()
    app.mainloop()
