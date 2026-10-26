"""Single source of truth for the demo colour palette.

The page canvas is pure white; the four brand hues paint every component,
card and piece of text on top of it:

    APP_BG    #FFFFFF  canvas            -> the main app background
    PURPLE    #722F99  primary / accent  -> headers, active tabs, primary
                                         buttons, Planner output, FINAL ANSWER
    SILVER    #C5C1C1  neutral           -> borders, secondary text, disabled
                                         states, Observation blocks
    PEACH     #FEE7C8  surface           -> cards, chat/trace bubbles,
                                         Thought blocks
    SOFT_RED  #FF9292  alert             -> error states, missing information,
                                         Verifier rejections, Action blocks
"""

APP_BG = "#FFFFFF"
PURPLE = "#722F99"
SILVER = "#C5C1C1"
PEACH = "#FEE7C8"
SOFT_RED = "#FF9292"

INK = "#2A2233"
PURPLE_DEEP = "#4A1E66"
SILVER_LIGHT = "#F0D8C8"

PALETTE = {
    "app_bg": APP_BG,
    "purple": PURPLE,
    "silver": SILVER,
    "peach": PEACH,
    "soft_red": SOFT_RED,
}


def rgba(hex_color: str, alpha: float) -> str:
    """Convert #RRGGBB into an rgba() string so the palette can be layered."""
    h = hex_color.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    return f"rgba({r}, {g}, {b}, {alpha})"
