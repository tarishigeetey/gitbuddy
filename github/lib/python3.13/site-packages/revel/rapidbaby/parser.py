import re
from typing import *  # type: ignore

from .styles import Style, StyleCategory, StyleSet

__all__ = [
    "Baby",
]


TAG_PATTERN = re.compile(r"(?<!\[)(\[\[)*(\[/?[\w\- ]*\])")


def prepare_plaintext_highlights() -> re.Pattern:
    raw = (
        (
            "url",
            r"\b(http|https|ftp|file)://[^\s/$.?#]+\.[^\s]+\b/?",
        ),
        (
            "email",
            r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b",
        ),
        (
            "number",
            r"[+-]?\d*([.,_]\d+)+(?:[eE][+-]?(?:\d*([.,_]\d*)*))?",
        ),
    )

    # Create a combined pattern. Make sure to assign the name to each capture
    # group
    combined_pattern = "|".join([f"(?P<{name}>{pattern})" for name, pattern in raw])

    return re.compile(combined_pattern)


PLAINTEXT_HIGHLIGHT_PATTERN = prepare_plaintext_highlights()


class Baby:
    def __init__(self, styles: StyleSet):
        # All styles known to the parser
        self._styles = styles

        # Contains all partial results that have been processed so far
        self._partial_results: list[str] = []

        # Contains all currently active styles, in the same order they were
        # applied. This is a list of sets, because a single tag can contain
        # multiple styles.
        self._style_stack: list[Set[Style]] = []

        # Counts how often each style is currently active.
        self._style_counter: Counter[str] = Counter()

        # Counts how often each style category is currently active
        self._category_counter: Counter[StyleCategory] = Counter()

    def reset(self) -> None:
        """
        Resets the parser to its initial state. Does not modify the known
        styles.
        """
        self._partial_results = []
        self._style_stack = []
        self._style_counter = Counter()
        self._category_counter = Counter()

    def _process_plain_text(self, text: str) -> None:
        # Remove any double brackets
        text = text.replace("[[", "[")

        # Highlight some common plaintext patterns
        cur_pos = 0

        while True:
            # Find the next match
            match = PLAINTEXT_HIGHLIGHT_PATTERN.search(text, cur_pos)

            # No match? Done
            if match is None:
                break

            # Split up the text
            self._partial_results.append(text[cur_pos : match.start()])
            span = text[match.start() : match.end()]
            cur_pos = match.end()

            # Which styles should be applied?
            for style_name, value in match.groupdict().items():
                if value is not None:
                    break
            else:
                assert False, "Unreachable"

            # Apply the styles
            self._begin_styles([style_name], weak=True)
            self._partial_results.append(span)
            self._close_most_recent_tag()

        # Add the remaining text
        self._partial_results.append(text[cur_pos:])

    def _close_most_recent_tag(self) -> None:
        # Which styles should be closed?
        try:
            styles = self._style_stack.pop()
        except IndexError:
            styles = set()

        # Close them
        for style in styles:
            self._style_counter[style.name] -= 1
            self._category_counter[style.category] -= 1

            if self._style_counter[style.name] == 0:
                self._partial_results.append(style.stop_string)

    def _begin_styles(
        self,
        style_names: Iterable[str],
        *,
        weak: bool,
    ) -> None:
        # These might be aliases. Expand them
        styles: Set[Style] = set()

        for style_name in style_names:
            try:
                alias_styles = self._styles._styles[style_name]
            except KeyError:
                continue

            for substyle in alias_styles:
                # Skip weak styles if the category is already active
                if weak and self._category_counter[substyle.category] > 0:
                    continue

                styles.add(substyle)

        # Update the style stack
        self._style_stack.append(styles)

        # Apply the styles
        for style in styles:
            # Apply it
            self._style_counter[style.name] += 1
            self._category_counter[style.category] += 1

            if self._style_counter[style.name] == 1:
                self._partial_results.append(style.start_string)

    def feed(self, text: str) -> None:
        previous_end = 0

        # Find all matches using the precompiled pattern
        for match in TAG_PATTERN.finditer(text):
            # Get the matching region
            start_index = match.start(2)
            end_index = match.end(2)
            span = text[start_index:end_index]

            assert span.startswith("["), (span, start_index, end_index, match.groups())

            # Anything up to that region is plain text
            if start_index > 0:
                self._process_plain_text(text[previous_end:start_index])

            previous_end = end_index

            # Closing tag
            #
            # The contents can be ignored, since RapidBaby only accepts empty
            # closing tags: [/]
            if span.startswith("[/"):
                self._close_most_recent_tag()

            # Opening tag
            else:
                # Fetch all listed styles
                style_names = set(span[1:-1].split())

                # Extract any special case styles
                verbatim = "verbatim" in style_names
                style_names.discard("verbatim")

                weak = "weak" in style_names
                style_names.discard("weak")

                # Verbatim needs special handling
                if verbatim:
                    raise NotImplementedError("TODO: Implement [verbatim]")

                # Apply the styles
                self._begin_styles(style_names, weak=weak)

        # Yield the remaining text
        self._process_plain_text(text[previous_end:])

    def finish(self) -> str:
        """
        Closes all open tags and returns the final result.

        This function leaves the parser in an undefined state. Make sure to
        `reset` it before using it again.
        """
        # Close any remaining styles
        #
        # Take care to only close each style once.
        #
        # This could be done using a single reset code, but that wouldn't allow
        # concatenating multiple markup strings together.
        remaining_styles_flat: Set[Style] = set()

        for styles in self._style_stack:
            remaining_styles_flat.update(styles)

        for style in remaining_styles_flat:
            self._partial_results.append(style.stop_string)

        # Return the final result
        return "".join(self._partial_results)

    def process(self, value: str) -> str:
        """
        Applies markup to a string and returns the result. This is a convenience
        method that combines `reset`, `feed`, and `finish`.
        """
        self.reset()
        self.feed(value)
        return self.finish()
