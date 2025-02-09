from typing import *  # type: ignore

from . import rapidbaby
from .rapidbaby import escape

# Create a global style set. This allows the user to add or change styles
GLOBAL_STYLES = rapidbaby.StyleSet()


# Add styles used by plaintext highlights
GLOBAL_STYLES.add_alias("primary", ["blue"])
GLOBAL_STYLES.add_alias("bg-primary", ["bg-blue"])
GLOBAL_STYLES.add_alias("url", ["blue", "underlined"])
GLOBAL_STYLES.add_alias("email", ["blue"])
GLOBAL_STYLES.add_alias("number", ["green"])


def unescape(value: Any) -> str:
    """
    Applies markup to a string.
    """
    # Make sure the value is a string
    value = str(value)

    # Apply markup
    baby = rapidbaby.Baby(GLOBAL_STYLES)
    return baby.process(value)
