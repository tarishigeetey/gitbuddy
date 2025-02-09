from typing import *  # type: ignore


def escape(value: Any) -> str:
    """
    Escapes a string to prevent markup from being interpreted.
    """
    # Make sure the value is a string
    value = str(value)

    # Double up brackets
    return value.replace("[", "[[")


