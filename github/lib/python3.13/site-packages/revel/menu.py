import sys
from abc import ABC, abstractmethod
from typing import *  # type: ignore

import blessed

from . import legacy
from . import markup as markup_module

T = TypeVar("T")


class Menu(ABC):
    def __init__(
        self,
        n_options: int,
        footer: str,
    ):
        assert n_options > 0, "There must be at least one option"
        self.n_options = n_options
        self.footer = footer

        self.current_index = 0
        self.term = blessed.Terminal()

    @abstractmethod
    def draw_line(self, index: int) -> None:
        raise NotImplementedError

    def on_move_up_or_down(self, previous_index: int) -> None:
        pass

    def on_input(self, key: str) -> bool:
        """
        Run arbitrary code to handle the given key. If this returns `True`, the
        menu will be closed.
        """
        return False

    def force_redraw_line(self, index: int) -> None:
        # Move to the correct line
        offset = self.n_options - index + 1
        sys.stdout.write(self.term.move_up * offset)
        sys.stdout.write(self.term.move_x(legacy._start_x))

        # Clear the line
        sys.stdout.write(self.term.clear_eol())

        # Draw the line
        self.draw_line(index)

        # Move back down
        sys.stdout.write(self.term.move_down * offset)
        sys.stdout.write(self.term.move_x(0))
        sys.stdout.flush()

    def run(self, prompt: str) -> None:
        previous_index = 0

        # Display the prompt
        if prompt:
            sys.stdout.write(self.term.move_x(legacy._start_x))
            sys.stdout.write(markup_module.unescape(prompt))
            sys.stdout.write("\n\n")

        # Display the initial menu
        for index in range(self.n_options):
            sys.stdout.write(self.term.move_x(legacy._start_x))
            self.draw_line(index)
            sys.stdout.write("\n")

        sys.stdout.write("\n")
        sys.stdout.write(self.term.move_x(legacy._start_x))
        sys.stdout.write(markup_module.unescape(self.footer))
        sys.stdout.write(self.term.move_x(0))
        sys.stdout.flush()

        # Hand control to the user
        with self.term.cbreak(), self.term.hidden_cursor():
            while True:
                previous_index = self.current_index

                # Listen for user inputs
                key = self.term.inkey()
                if key.name == "KEY_UP" or key == "k":
                    self.current_index = max(self.current_index - 1, 0)

                elif key.name == "KEY_DOWN" or key == "j":
                    self.current_index = min(self.current_index + 1, self.n_options - 1)

                elif key.name == "KEY_ENTER":
                    sys.stdout.write(self.term.clear_eol())
                    sys.stdout.flush()
                    return

                else:
                    finish = self.on_input(key)

                    if finish:
                        return

                # Update the display
                if self.current_index != previous_index:
                    self.on_move_up_or_down(previous_index)

        assert False, "Should never get here"


class SingleSelectMenu(Menu):
    def __init__(self, options: list[str]):
        super().__init__(
            n_options=len(options),
            footer=f"[dim]⇅ or 1-{min(9, len(options))} to move, ↩ to confirm[/dim]",
        )
        self.options = options

    def draw_line(self, index: int) -> None:
        option = self.options[index]
        is_selected = index == self.current_index

        if is_selected:
            line = f"[bg-primary]{index + 1}. {option}  [/]"
        else:
            line = f"[primary]{index + 1}.[/] {option}"

        sys.stdout.write(markup_module.unescape(line))

    def on_input(self, key: str) -> bool:
        # Allow using 0-9 to select an option
        try:
            number = int(key)
        except ValueError:
            pass
        else:
            if number == 0:
                number = 10

            if 1 <= number <= self.n_options:
                sys.stdout.write(self.term.clear_eol())
                sys.stdout.flush()
                self.current_index = number - 1
                return True

        # Unrecognized key
        return False

    def on_move_up_or_down(self, previous_index: int) -> None:
        self.force_redraw_line(previous_index)
        self.force_redraw_line(self.current_index)


def select(options: dict[str, T], *, prompt: str = "") -> T:
    """
    Asks the user to select one of the given options. If `prompt` is given, it
    is displayed first. The options are displayed as a numbered list, and the
    user is asked to select one of them.
    """

    if not options:
        raise ValueError("Please provide at least one option")

    # Delegate to the interactive menu class
    opt_list = list(options.items())
    menu = SingleSelectMenu([name for name, _ in opt_list])
    menu.run(prompt)

    # Return the selected option
    return opt_list[menu.current_index][1]


class MultiSelectMenu(Menu):
    def __init__(
        self,
        options: list[str],
    ):
        super().__init__(
            n_options=len(options) + 1,
            footer=f"[dim]Use ⇅ to move, ␣ space to select, ↩ to confirm[/dim]",
        )
        self.options: list[str] = options
        self.checked: list[bool] = [False] * len(options)

    def draw_line(self, index: int) -> None:
        is_selected = index == self.current_index

        # Is this the "Done" option?
        if index == self.n_options - 1:
            if is_selected:
                line = f"[bg-primary]    Done  [/]"
            else:
                line = f"    Done"

        # Otherwise, it's a regular option
        else:
            option = self.options[index]
            is_checked = self.checked[index]

            checked_str = (
                "[dim][[[/][bold]✓[/][dim]][/]" if is_checked else "[dim][[ ][/]"
            )

            if is_selected:
                line = f"[bg-primary]{checked_str} {option}  [/]"
            else:
                line = f"[primary]{checked_str}[/] {option}"

        sys.stdout.write(markup_module.unescape(line))

    def on_input(self, key: str) -> bool:
        # Spacebar toggles the current option
        if key == " " and self.current_index < self.n_options - 1:
            self.checked[self.current_index] = not self.checked[self.current_index]
            self.force_redraw_line(self.current_index)
            return False

        # ...or confirms, if the last option is selected
        elif key == " " and self.current_index == self.n_options - 1:
            return True

        # Unrecognized key
        return False

    def on_move_up_or_down(self, previous_index: int) -> None:
        self.force_redraw_line(previous_index)
        self.force_redraw_line(self.current_index)


def select_multiple(options: dict[str, T], *, prompt: str = "") -> list[T]:
    """
    Allows the user to choose between a set of options. A menu will be displayed
    on the screen with all the options, and the user can select multiple options
    by toggling them on and off.
    """

    if not options:
        raise ValueError("Please provide at least one option")

    # Delegate to the interactive menu class
    opt_list = list(options.items())
    menu = MultiSelectMenu([name for name, _ in opt_list])
    menu.run(prompt)

    # Return the selected option
    return [opt_list[i][1] for i, checked in enumerate(menu.checked) if checked]
