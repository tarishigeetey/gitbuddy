class Format:
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINED = "\033[4m"
    INVERTED = "\033[7m"
    STRIKETHROUGH = "\033[9m"

    RESET_BOLD = "\033[22m"
    RESET_DIM = "\033[22m"
    RESET_ITALIC = "\033[23m"
    RESET_UNDERLINED = "\033[24m"
    RESET_INVERTED = "\033[27m"
    RESET_STRIKETHROUGH = "\033[29m"


class Fore:
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    RESET = "\033[39m"


class Back:
    BLACK = "\033[40m"
    RED = "\033[41m"
    GREEN = "\033[42m"
    YELLOW = "\033[43m"
    BLUE = "\033[44m"
    MAGENTA = "\033[45m"
    CYAN = "\033[46m"
    WHITE = "\033[47m"

    RESET = "\033[49m"


RESET_ALL = "\033[0m"
