# config.py — Pure Holographic Orange Theme Constants

APP_NAME = "ULTRON"
APP_VERSION = "2.0.0"

# ---------------------------------------------------------------------------
# Color Palette — Pure Holographic Orange
# ---------------------------------------------------------------------------
COLOR_BG         = "#050400"        # Near-black background
COLOR_BG_PANEL   = "#0A0800"        # Slightly lighter panel bg
COLOR_BG_GLASS   = "#120C00"        # Glass panel interior

COLOR_PRIMARY    = "#FF6A00"        # Core orange
COLOR_BRIGHT     = "#FF8C00"        # Bright orange (hover, highlights)
COLOR_GLOW       = "#FFA040"        # Soft glow / bloom
COLOR_DIM        = "#993D00"        # Dimmed orange (inactive / secondary text)
COLOR_FAINT      = "#3D1800"        # Very faint orange (borders, tracks)

COLOR_ACCENT     = "#FFB347"        # Warm accent / telemetry highlight
COLOR_WHITE      = "#FFF5E0"        # Warm near-white
COLOR_WARN       = "#FF2200"        # Warning red-orange
COLOR_OK         = "#FF6A00"        # OK state (same as primary)
COLOR_CRITICAL   = "#FF0000"        # Critical alert

COLOR_TEXT_HI    = "#FFCC88"        # Primary text
COLOR_TEXT_MID   = "#CC7733"        # Secondary text
COLOR_TEXT_LO    = "#663300"        # Tertiary / disabled text

COLOR_GRID       = "#1A0D00"        # Background grid lines
COLOR_BORDER     = "#331A00"        # Panel border

# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------
FONT_MONO        = "Courier New"
FONT_HUD         = "Courier New"
FONT_SIZE_TITLE  = 11
FONT_SIZE_BODY   = 9
FONT_SIZE_SMALL  = 8
FONT_SIZE_LARGE  = 14

# ---------------------------------------------------------------------------
# Timing
# ---------------------------------------------------------------------------
TELEMETRY_INTERVAL_MS  = 800    # System data refresh
ANIMATION_TICK_MS      = 33     # ~30 fps animation tick
LOG_UPDATE_INTERVAL_MS = 1500   # Log event injection interval

# ---------------------------------------------------------------------------
# Layout
# ---------------------------------------------------------------------------
PANEL_RADIUS    = 4
PANEL_PADDING   = 8
LEFT_PANEL_W    = 280
RIGHT_PANEL_W   = 280
BOTTOM_H        = 110
