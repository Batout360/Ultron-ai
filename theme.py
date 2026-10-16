# theme.py — ULTRON 3.0 Design Tokens
#
# Two-tier colour system:
#   CYAN  (#65eaff family) — interface chrome: borders, labels, bars, prompts
#   GOLD  (#ffb957 family) — energy core only: AI brain particle swarm
#
# All layout/paint magic numbers must live here.

APP_NAME    = "ULTRON"
APP_VERSION = "3.0"

# ── Interface Chrome (cyan) ───────────────────────────────────────────────────
CYAN            = "#65eaff"
CYAN_DIM        = "#3a8fa6"
CYAN_FAINT      = "#0d2a33"

# ── Energy Core (gold — AI brain only) ───────────────────────────────────────
GOLD            = "#ffb957"
GOLD_BRIGHT     = "#ffd080"
GOLD_DIM        = "#a06020"
GOLD_FAINT      = "#2a1500"

# ── Backgrounds ───────────────────────────────────────────────────────────────
COLOR_BG        = "#00080f"          # full-window background
COLOR_BG_PANEL  = "#040c14"          # panel base
COLOR_BG_GLASS  = "#060e18"          # unused legacy — kept for compat

# Panel glass gradient stops (used in utils.panel_glass_fill)
PANEL_GLASS_TOP = "#0a1822"          # top colour  (alpha 220)
PANEL_GLASS_BOT = "#02070d"          # bottom colour (alpha 190)

# ── Text ──────────────────────────────────────────────────────────────────────
COLOR_TEXT      = "#d9f5ff"
COLOR_TEXT_MID  = "#7396a6"
COLOR_TEXT_LO   = "#3a5560"
COLOR_TEXT_HI   = COLOR_TEXT         # compat alias

# ── Semantic states ───────────────────────────────────────────────────────────
COLOR_OK        = CYAN
COLOR_WARN      = "#ffaa00"
COLOR_CRITICAL  = "#ff3322"

# ── Backward-compat aliases ───────────────────────────────────────────────────
COLOR_PRIMARY   = CYAN
COLOR_BRIGHT    = CYAN
COLOR_GLOW      = "#36dfff"
COLOR_DIM       = CYAN_DIM
COLOR_FAINT     = CYAN_FAINT
COLOR_ACCENT    = GOLD
COLOR_WHITE     = COLOR_TEXT
COLOR_BORDER    = CYAN_DIM
COLOR_GRID      = "#0a1e2a"          # v3.0: brighter grid (was #051015)

# ── Fonts ─────────────────────────────────────────────────────────────────────
# v3.0: Consolas renders more crisply than Courier New at small pt sizes
FONT_MONO       = "Consolas"
FONT_HUD        = "Consolas"

# 5-level type scale
FONT_SIZE_LABEL   = 7    # timestamps, units, eyebrow text
FONT_SIZE_SMALL   = 8    # log messages, metric labels, secondary text
FONT_SIZE_BODY    = 9    # console output, input, normal values
FONT_SIZE_TITLE   = 11   # panel headings
FONT_SIZE_DISPLAY = 16   # centre AI core metric
FONT_SIZE_LARGE   = FONT_SIZE_DISPLAY   # compat alias

# ── Spacing (multiples of 4) ──────────────────────────────────────────────────
SP_1 = 4
SP_2 = 8
SP_3 = 12
SP_4 = 20

# ── Component dimensions ──────────────────────────────────────────────────────
ROW_H          = 24     # MetricRow, StatusDot height
ROW_H_LOG      = 18     # system log entry row
INPUT_H        = 34     # console input field
PANEL_HEAD_H   = 30     # panel title band height
BAR_H          = 5      # metric bar thickness
BAR_TRACK_H    = 5      # metric track thickness
VAL_COL_W      = 48     # value column width in MetricRow (wide enough for "8192 KB/s")

# ── Geometry tokens (replaces magic numbers in paintEvent) ───────────────────
PANEL_CLIP     = 12     # top-right corner clip size (px)
GRID_STEP      = 40     # background grid spacing (px, pre-DPI)
ICON_R         = 12     # reactor icon radius in TopBar
BRACKET_ARM    = 24     # corner bracket arm length
BRACKET_INSET  = 14     # corner bracket offset from screen edge

# ── Timing ────────────────────────────────────────────────────────────────────
TELEMETRY_INTERVAL_MS  = 800
ANIMATION_TICK_MS      = 33
LOG_UPDATE_INTERVAL_MS = 2500        # v3.0: slower fallback (real events take priority)

# ── Layout ────────────────────────────────────────────────────────────────────
PANEL_RADIUS    = 0
PANEL_PADDING   = SP_2
LEFT_PANEL_W    = 264
RIGHT_PANEL_W   = 248
BOTTOM_H        = 124
