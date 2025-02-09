import colorama

from .cli_app import App, Parameter
from .common import choose_string
from .errors import *
from .legacy import *
from .markup import GLOBAL_STYLES, escape, unescape
from .menu import select, select_multiple
from .shell_escape import *
from .style import *

colorama.init()

__all__ = [
    "print",
    "print_chapter",
    "input",
    "success",
    "warning",
    "error",
    "fatal",
]
