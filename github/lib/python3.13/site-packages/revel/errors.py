from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import *  # type: ignore

from . import common

__all__ = [
    "RevelError",
    "NoOptionGivenError",
    "NoSuchOptionError",
    "AmbiguousOptionError",
    "ArgumentError",
]


@dataclass
class RevelError(Exception, ABC):
    """Base class for all Revel exceptions."""

    @property
    @abstractmethod
    def message(self) -> str:
        """The error message."""
        raise NotImplementedError


@dataclass
class NoOptionGivenError(RevelError):
    """Raised when the user doesn't specify a command."""

    available_options: list[str]

    def message(self, *, option_name: str = "option") -> str:
        an = common.an(option_name)
        return f"Please specify {an} {option_name}. Possible options are {common.comma_separated_list(self.available_options, 'and', '`')}."


@dataclass
class NoSuchOptionError(RevelError):
    """Raised when the user passes an invalid option."""

    entered_option: str
    available_options: list[str]

    def message(self, *, option_name: str = "option") -> str:
        return f"`{self.entered_option}` is not a valid {option_name}."


@dataclass
class AmbiguousOptionError(RevelError):
    """Raised when the user passes an ambiguous option."""

    entered_option: str
    matching_options: list[str]
    available_options: list[str]

    def message(self, *, option_name: str = "option") -> str:
        return f"`{self.entered_option}` is ambiguous. It could refer to {common.comma_separated_list(self.matching_options, 'or', '`')}."


class ArgumentError(RevelError):
    """
    Raised when attempting to call a function with invalid arguments. The
    message is human-readable and meant to be directly passed to the user
    """

    def __init__(self, message: str):
        self._message = message

    @property
    def message(self) -> str:
        return self._message
