import re
import textwrap
from typing import *  # type: ignore

from . import errors


def comma_separated_list(
    values: Iterable[str],
    conjunction: str | None,
    quote: str | None,
) -> str:
    """
    Given a list of values, return a human-readable list of them. If the list
    contains only one value, that value is returned. Otherwise, the values are
    joined with commas, and the conjunction is inserted before the last value.

    The list is a comma-separated list of the values, with the conjunction
    inserted before the last value. For example, if the conjunction is "or", the
    list will be "A, B or C".

    If `quote` is not `None`, each value will be surrounded with the quote
    character.
    """

    assert values, "Cannot create a list from an empty iterable"

    # Wrap all values in quotes
    if quote is not None:
        values = [quote + value + quote for value in values]
    else:
        values = list(values)

    # Special case: Only one value
    if len(values) == 1:
        return values[0]

    # Join all but the last value with commas
    if conjunction is None:
        return ", ".join(values[:-1])
    else:
        return ", ".join(values[:-1]) + " " + conjunction + " " + values[-1]


def choose_string(
    options: Sequence[str | list[str]],
    selection: str,
) -> int:
    """
    Given a list of choices and user input, find the choice the user wanted to
    select. This is a best-effort method, which does it's best to give the user
    leeway in what they type, without accidentally selecting an option they
    didn't want to select.

    If the function is confident in what the user wanted to select, it returns
    the index of the choice. Otherwise, it raises an exception.

    ## Raises

    `NoSuchOptionError`: If the user's input doesn't match any of the choices.

    `AmbiguousOptionError`: If the user's input matches multiple choices.
    """
    # TODO: This method needs a lot of improvement. Consider using some sort of
    # scoring system to determine which choice is the best match. It also
    # currently cannot distinguish between uppercase and lowercase inputs.
    #
    # - exact match over wrong case
    # - starts with over contains
    # - consider user's uppercase as uppercase, but lowercase as undecided
    # - ...
    #
    # Error reporting could also be better.
    #
    # I'll shut up now.

    # Expand the options
    expanded_options: list[list[str]] = [
        [option] if isinstance(option, str) else option for option in options
    ]

    # Normalize the user input
    def normalize(value: str) -> str:
        return value.strip().lower().replace(" ", "-").replace("_", "-")

    selection = normalize(selection)

    # Find all choices that match the user's input. If one matches exactly, go
    # with that.
    matching_indices: Set[int] = set()
    matching_values: Set[str] = set()

    for ii, choice_set in enumerate(expanded_options):
        for choice in choice_set:
            choice = normalize(choice)

            # Exact match? This is it
            if choice == selection:
                return ii

            # Partial match? Add it to the list of possible matches
            if selection in choice:
                matching_indices.add(ii)
                matching_values.add(choice)

    # If there are no matches, return an error message
    if not matching_indices:
        raise errors.NoSuchOptionError(selection, [x[0] for x in expanded_options])

    # If there is only one match, return it
    if len(matching_indices) == 1:
        return next(iter(matching_indices))

    # If there are multiple matches, return an error message
    raise errors.AmbiguousOptionError(
        selection,
        list(matching_values),
        [x[0] for x in expanded_options],
    )


def python_name_to_console(name: str) -> str:  #
    """
    Convert a name as it would be used in Python to how it would be used in the
    console. For example, `foo_bar` becomes `foo-bar`.
    """
    name = name.strip("_")
    name = name.replace("_", "-")
    return name


def python_name_to_pretty(name: str) -> str:
    """
    Convert a name as it would be used in Python to a nice, human-readable name.
    """
    name = name.strip("_")
    name = name.replace("_", " ")
    return name.title()


def multiline_strip(value: str) -> str:
    """
    Clean up a user-provided multi-line string, such as a description.
    """

    # Remove leading indentation
    value = textwrap.dedent(value)

    # Remove leading and trailing whitespace
    value = value.strip()

    # Remove single newlines & replace multiple newlines with a single one
    value = re.sub(
        r"\n+",
        lambda match: " " if match.group(0) == "\n" else "\n\n",
        value,
    )

    return value


def an(noun: str) -> str:
    """
    Given a noun, return the correct indefinite article to use before it.
    """
    if noun[0].lower() in "aeiou":
        return "an"
    else:
        return "a"
