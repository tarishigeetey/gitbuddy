import enum
from collections import defaultdict
from typing import *  # type: ignore

import revel.style as style


class StyleCategory(enum.Flag):
    FONT_COLOR = enum.auto()
    BACKGROUND_COLOR = enum.auto()
    FONT_WEIGHT = enum.auto()
    ITALIC = enum.auto()
    UNDERLINED = enum.auto()
    STRIKETHROUGH = enum.auto()
    INVERTED = enum.auto()


class Style:
    def __init__(
        self,
        name: str,
        start_string: str,
        stop_string: str,
        category: StyleCategory,
    ):
        self.name = name
        self.start_string = start_string
        self.stop_string = stop_string
        self.category = category


class StyleSet:
    def __init__(self):
        # All known styles
        self._styles: dict[str, Set[Style]] = {}

        # Add all fundamental styles
        self._register_fundamental_styles()

    def _register_fundamental_styles(self) -> None:
        self._add_fundamental_style(
            "bold",
            style.Format.BOLD,
            style.Format.RESET_BOLD,
            StyleCategory.FONT_WEIGHT,
        )
        self._add_fundamental_style(
            "dim",
            style.Format.DIM,
            style.Format.RESET_DIM,
            StyleCategory.FONT_WEIGHT,
        )

        self._add_fundamental_style(
            "italic",
            style.Format.ITALIC,
            style.Format.RESET_ITALIC,
            StyleCategory.ITALIC,
        )

        self._add_fundamental_style(
            "underlined",
            style.Format.UNDERLINED,
            style.Format.RESET_UNDERLINED,
            StyleCategory.UNDERLINED,
        )

        self._add_fundamental_style(
            "inverted",
            style.Format.INVERTED,
            style.Format.RESET_INVERTED,
            StyleCategory.INVERTED,
        )

        self._add_fundamental_style(
            "strikethrough",
            style.Format.STRIKETHROUGH,
            style.Format.RESET_STRIKETHROUGH,
            StyleCategory.STRIKETHROUGH,
        )

        self._add_fundamental_style(
            "black",
            style.Fore.BLACK,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "red",
            style.Fore.RED,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "green",
            style.Fore.GREEN,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "yellow",
            style.Fore.YELLOW,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "blue",
            style.Fore.BLUE,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "magenta",
            style.Fore.MAGENTA,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "cyan",
            style.Fore.CYAN,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )
        self._add_fundamental_style(
            "white",
            style.Fore.WHITE,
            style.Fore.RESET,
            StyleCategory.FONT_COLOR,
        )

        self._add_fundamental_style(
            "bg-black",
            style.Back.BLACK,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-red",
            style.Back.RED,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-green",
            style.Back.GREEN,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-yellow",
            style.Back.YELLOW,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-blue",
            style.Back.BLUE,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-magenta",
            style.Back.MAGENTA,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-cyan",
            style.Back.CYAN,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )
        self._add_fundamental_style(
            "bg-white",
            style.Back.WHITE,
            style.Back.RESET,
            StyleCategory.BACKGROUND_COLOR,
        )

    def _add_fundamental_style(
        self,
        name: str,
        start_string: str,
        stop_string: str,
        category: StyleCategory,
    ) -> None:
        """
        Registers a new style.
        """
        assert name not in self._styles, name
        self._styles[name] = {
            Style(name, start_string, stop_string, category),
        }

    def add_alias(self, name: str, targets: Iterable[str]) -> None:
        """
        Adds a style which is an alias for one or more other styles.
        """
        # Cannot override special styles
        if name in ("weak", "verbatim"):
            raise ValueError(
                f'The style name "{name}" is reserved and cannot be overridden'
            )

        # Make sure all targets exist
        target_instances = set()

        for target in targets:
            try:
                target_instances.update(self._styles[target])
            except KeyError:
                raise ValueError(f"There is no style named `{target}`") from None

        # Add the style
        self._styles[name] = target_instances
