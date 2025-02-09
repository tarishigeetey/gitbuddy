import inspect
import re
import types
from dataclasses import dataclass
from typing import *  # type: ignore
from typing import Any

import revel

from . import common, legacy, menu
from .errors import (
    AmbiguousOptionError,
    ArgumentError,
    NoOptionGivenError,
    NoSuchOptionError,
)

T = TypeVar("T")
P = ParamSpec("P")


NO_DEFAULT = object()


PATTERN_LONG_FLAG = re.compile(r"--([a-zA-Z0-9\-]+)(=(.*))?")
PATTERN_SHORT_FLAG = re.compile(r"-([a-zA-Z\-]+)(=(.*))?")


@dataclass
class Parameter:
    # Name, as presented to the user
    name: str

    # Optionally a single-character shorthand for the parameter
    shorthand: str | None

    # How the parameter is called in python. This is needed when passing it to
    # a function as a keyword argument.
    python_name: str

    # If asking interactively for this parameter, this text will be used as the
    # prompt. Falls back to the name if not specified.
    prompt: str | None

    type: Type

    is_flag: bool
    is_variadic: bool

    default_value: Any

    def __hash__(self) -> int:
        return hash(id(self))


def parameters_from_function(
    function: Callable,
) -> Iterable[tuple[inspect.Parameter, Parameter]]:
    """
    Converts the given function's parameter list into a list of `Parameter`s.
    """
    signature = inspect.signature(function)
    type_hints = get_type_hints(function)

    for name, parameter in signature.parameters.items():
        param_type = type_hints.get(name, Any)

        # Parse the name. If it contains a double underscore, use it to split
        # the name into shorthand and name
        splits = name.split("__", maxsplit=1)

        if len(splits) == 1:
            shorthand = None
        else:
            shorthand, name = splits

            if len(shorthand) != 1:
                raise ValueError(
                    f"Shorthands must be exactly one character long, not `{shorthand}`"
                )

        # Convert the name to how it would be used in the console
        name = common.python_name_to_console(name)

        # Default value?
        if parameter.default is inspect.Parameter.empty:
            default_value = NO_DEFAULT
        else:
            default_value = parameter.default

        # What kind of parameter is this?
        if parameter.kind == inspect.Parameter.VAR_POSITIONAL:
            is_variadic = True
            is_flag = False
        elif parameter.kind == inspect.Parameter.POSITIONAL_ONLY:
            is_variadic = False
            is_flag = False
        elif parameter.kind == inspect.Parameter.POSITIONAL_OR_KEYWORD:
            is_variadic = False
            is_flag = False
        elif parameter.kind == inspect.Parameter.KEYWORD_ONLY:
            is_variadic = False
            is_flag = True
        elif parameter.kind == inspect.Parameter.VAR_KEYWORD:
            is_variadic = True
            is_flag = True
        else:
            raise NotImplementedError(f"Unsupported parameter kind: {parameter.kind}")

        # Build the result
        yield parameter, Parameter(
            name=name,
            shorthand=shorthand,
            python_name=parameter.name,
            prompt=None,
            type=param_type,
            is_flag=is_flag,
            is_variadic=is_variadic,
            default_value=default_value,
        )


def _parse_literal(raw: str, typ: Type) -> str:
    options = get_args(typ)

    # Figure out which option the user is referring to
    try:
        selected_index = common.choose_string(
            options=[[value] for value in options],
            selection=raw,
        )

    # No match?
    except NoSuchOptionError:
        options_str = common.comma_separated_list(options, "and", "`")
        raise ArgumentError(
            f"`{raw}` is not valid here. Please provide one of {options_str}"
        )

    # Multiple matches? Ambiguous
    except AmbiguousOptionError as err:
        options_str = common.comma_separated_list(err.matching_options, "and", "`")
        raise ArgumentError(
            f"`{raw}` is ambiguous here. It could refer to either of {options_str}"
        )

    # There was a match. Return it
    return options[selected_index]


def _parse_bool(raw: str) -> bool:
    raw = raw.lower()

    if raw in ("true", "t", "yes", "y", "1"):
        return True

    if raw in ("false", "f", "no", "n", "0"):
        return False

    raise ArgumentError(f"`{raw}` is not a valid boolean value. Use `true` or `false`")


def _parse_int(raw: str) -> int:
    try:
        return int(raw)
    except ValueError:
        raise ArgumentError(f"`{raw}` is not a valid integer number") from None


def _parse_float(raw: str) -> float:
    try:
        return float(raw)
    except ValueError:
        raise ArgumentError(f"`{raw}` is not a valid number") from None


def parse_value(value: str, typ: Type) -> Any:
    type_key = get_origin(typ)
    if type_key is None:
        type_key = typ

    if hasattr(types, "UnionType") and type_key is types.UnionType:
        type_key = Union

    if type_key in (str, Any):
        return str(value)

    if type_key is Literal:
        return _parse_literal(value, typ)

    if type_key is bool:
        return _parse_bool(value)

    if type_key is int:
        return _parse_int(value)

    if type_key is float:
        return _parse_float(value)

    if type_key is Union:
        for option in get_args(typ):
            # Special case: `NoneType` can be part of a union, but can't be parsed
            if option is type(None):
                continue

            try:
                return parse_value(value, option)
            except ArgumentError:
                pass

        raise ArgumentError(f"`{value}` is not a valid value for `{typ}`")

    raise TypeError(f"`{typ}` is not a supported type")


class Parser:
    def __init__(self, parameters: Iterable[Parameter]):
        self.parameters = list(parameters)

        # All parameters, by their name, shorthand, and position
        self.parameters_by_name: dict[str, Parameter] = {}
        self.parameters_by_shorthand: dict[str, Parameter] = {}
        self.positional_parameters: list[Parameter] = []

        for parameter in self.parameters:
            # Positional or flag?
            if parameter.is_flag:
                self.parameters_by_name[parameter.name] = parameter

                if parameter.shorthand is not None:
                    self.parameters_by_shorthand[parameter.shorthand] = parameter
            else:
                self.positional_parameters.append(parameter)

        # Maps already assigned values to parameters
        self.assigned_parameters: dict[str, list[str]] = {}

        # If not `None`, this is the parameter that is currently looking for a
        # value
        self.current_parameter: str | None = None

        # Whether any more flags are allowed
        self.allow_flags = True

        # Any superfluous values which cannot be assigned to any parameter
        self.rest: list[str] = []

        # Any errors that occurred during parsing
        self.errors: list[str] = []

        # The index of the next positional parameter to assign a value to
        self.next_positional_parameter_index = 0

    def _feed_flags(
        self,
        flag_names: Iterable[str],
        flag_value: str | None,
        use_shorthands: bool,
    ) -> None:
        flag_names = list(flag_names)
        flag_by_name_dict = (
            self.parameters_by_shorthand if use_shorthands else self.parameters_by_name
        )

        assert len(flag_names) >= 1, flag_names
        assert (
            not self.current_parameter
        ), "Parsing a flag, while one is still looking for a value?"

        # If multiple short flags are specified in the same value, all but the
        # last one have to be booleans
        for bool_flag in flag_names[:-1]:
            try:
                parameter = flag_by_name_dict[bool_flag]
            except KeyError:
                is_bool_parameter = False
            else:
                is_bool_parameter = parameter.type is bool

            if not is_bool_parameter:
                self.errors.append(f"Missing value for `-{bool_flag}`")
            else:
                existing = self.assigned_parameters.setdefault(bool_flag, [])
                existing.append("true")

        # If a value was specified, use it
        last_flag = flag_names[-1]
        if flag_value is not None:
            existing = self.assigned_parameters.setdefault(last_flag, [])
            existing.append(flag_value)
            return

        # If this parameter is a boolean, the very existence of the flag
        # means it's `True`
        try:
            parameter = flag_by_name_dict[last_flag]
        except KeyError:
            pass
        else:
            if parameter.type == bool:
                existing = self.assigned_parameters.setdefault(last_flag, [])
                existing.append("true")
                return

        # Otherwise, the next value is the value for this flag
        assert self.current_parameter is None, self.current_parameter
        self.current_parameter = last_flag
        return

    def feed_one(self, value: str) -> None:
        """
        Process a single value, updating the parser's state accordingly.
        """

        # If a parameter is still looking for a value, this is the value
        if self.current_parameter is not None:
            existing = self.assigned_parameters.setdefault(self.current_parameter, [])
            existing.append(value)
            self.current_parameter = None
            return

        # These only apply if flags are still accepted
        if self.allow_flags:
            # "--" marks the end of flags
            if value == "--":
                self.allow_flags = False
                return

            # Long flag?
            match = PATTERN_LONG_FLAG.fullmatch(value)
            if match is not None:
                self._feed_flags(
                    flag_names=[match.group(1)],
                    flag_value=match.group(3),
                    use_shorthands=False,
                )
                return

            # Short flag?
            match = PATTERN_SHORT_FLAG.fullmatch(value)
            if match is not None:
                self._feed_flags(
                    flag_names=list(match.group(1)),
                    flag_value=match.group(3),
                    use_shorthands=True,
                )
                return

        # Positional argument
        try:
            param = self.positional_parameters[self.next_positional_parameter_index]
        except IndexError:
            self.rest.append(value)
            return

        # Assign the value to the parameter
        existing = self.assigned_parameters.setdefault(param.name, [])
        existing.append(value)

        # If the parameter isn't variadic, move on to the next one
        if not param.is_variadic:
            self.next_positional_parameter_index += 1

    def feed_many(self, values: Iterable[str]) -> None:
        """
        Process multiple values, updating the parser's state accordingly.
        """

        for value in values:
            self.feed_one(value)

    def finish(
        self,
        *,
        allow_missing_arguments: bool = False,
    ) -> dict[Parameter, Any]:
        """
        Complete the parsing process and return the assigned values.
        """

        # Make sure no parameter is still looking for a value
        if self.current_parameter is not None:
            self.errors.append(f"Missing value for `{self.current_parameter}`")
            self.current_parameter = None

        # Parse the assigned values
        result = {}

        for param in self.parameters:
            # Has a value been assigned to this parameter?
            try:
                raw_assigned = self.assigned_parameters.pop(param.name)
            except KeyError:
                # Impute the default
                if param.default_value is not NO_DEFAULT:
                    result[param] = param.default_value
                    continue

                # Is it okay for arguments to be missing?
                if allow_missing_arguments:
                    continue

                # No default, and no value assigned
                self.errors.append(f"Missing value for `{param.name}`")
                continue

            # Make sure the correct number of values has been assigned
            if not param.is_variadic and len(raw_assigned) > 1:
                self.errors.append(f"Too many values for `{param.name}`")
                continue

            # Parse the values
            values = []

            for raw_value in raw_assigned:
                try:
                    value = parse_value(raw_value, param.type)
                except ArgumentError as e:
                    self.errors.append(f"Invalid value for `{param.name}`: {e}")
                    continue

                values.append(value)

            # Assign the value(s)
            if param.is_variadic:
                result[param] = tuple(values)
            elif values:
                result[param] = values[0]

        # Make sure no superfluous values are left
        if self.assigned_parameters:
            for name, values in self.assigned_parameters.items():
                self.errors.append(f"Unexpected value `{values[0]}`")

        # Done
        return result


def ask_value_for_parameter(
    param: Parameter,
    *,
    prompt: str | None = None,
) -> Any:
    """
    Ask the user for a value for the given parameter, parse and return it.
    """
    if prompt is None:
        prompt = " ".join(param.name.split("-")).title()

    # Extract the type to ask for
    type_key = get_origin(param.type)
    if type_key is None:
        type_key = param.type

    # Optional?
    #
    # Note that this doesn't handle unions in any special way. In general,
    # it's not clear how to ask for a union value, so just ask for any string
    # and then try to parse it.
    args = get_args(param.type)
    if type_key is Union and len(args) == 2 and type(None) in args:
        type_key = args[0]

    # Keep asking until a valid value is given
    while True:
        # Boolean?
        if type_key is bool:
            return legacy.select_yes_no(prompt)

        # Literal?
        if type_key is Literal:
            return menu.select(
                prompt=prompt,
                options={
                    common.python_name_to_pretty(value): value
                    for value in get_args(param.type)
                },
            )

        # Anything else
        value = legacy.input(prompt)

        try:
            return parse_value(value, param.type)
        except ArgumentError as e:
            revel.error(e.message)


def parse_function_parameters(
    params: list[Parameter],
    raw_args: Iterable[str],
    *,
    interactive: bool = False,
) -> tuple[list[Any], dict[str, Any]]:
    """
    Given a list of parameters, parse the given arguments and return them in a
    form usable to call the function. If `interactive` is `True`, ask for any
    missing values interactively.

    The result is a tuple of args and kwargs, which can be used to call the
    target function as `target(*args, **kwargs)`.

    Raises:
        ArgumentError: If the arguments are invalid
    """
    # Create a parser
    parser = Parser(params)

    # Assign the arguments
    parser.feed_many(raw_args)
    assignments = parser.finish(allow_missing_arguments=interactive)

    # Any errors?
    #
    # TODO: Print or raise, but not both. But then how does the caller know the
    #       details of what has happened.
    for err in parser.errors:
        revel.error(err)

    if parser.errors:
        raise ArgumentError("Invalid arguments")

    # If any arguments are missing, either ask for them or scream and die
    missing_params = set(params) - assignments.keys()

    if missing_params:
        # Can't ask, raise an exception
        if not interactive:
            raise ArgumentError(
                "Missing arguments: "
                + common.comma_separated_list(
                    [param.name for param in missing_params], "and", "`"
                )
            )

        # Ask interactively
        for param in missing_params:
            assignments[param] = ask_value_for_parameter(
                param,
                prompt=param.prompt,
            )

    # Bring the parameters into a form usable to call the function
    by_position = []
    by_name = {}

    for param in params:
        value = assignments[param]

        if param.is_flag:
            by_name[param.python_name] = value
        else:
            by_position.append(value)

    # Done
    return by_position, by_name


def parse_function_name(
    function_names: list[str],
    function_summaries: list[str | None],
    raw_args: list[str],
    *,
    function_aliases: list[Set[str]] | None = None,
    interactive: bool = False,
    option_name: str = "function",
) -> tuple[str, list[str]]:
    """
    Given a list of functions and their names, extract the name of the function
    to call from the given arguments. The function name is expected to be the
    first argument, and the remainder are returned.

    If no function name was provided, and `interactive` is `True`, ask for the
    function name interactively.

    Raises:
        NoOptionGivenError: If the user didn't specify a function name and
            `interactive` is `False`.

        NoSuchOptionError: If the user's input doesn't match any of the function
            names and `interactive` is `False`.

        AmbiguousOptionError: If the user's input matches multiple choices and
            `interactive` is `False`.
    """
    if function_aliases is None:
        function_aliases = [set() for _ in function_names]

    # See if the user has specified a function name
    if raw_args:
        all_names_and_aliases: list[list[str]] = []

        for name, aliases in zip(function_names, function_aliases):
            all_names_and_aliases.append([name] + list(aliases))

        try:
            choice_index = common.choose_string(
                options=all_names_and_aliases,
                selection=raw_args[0],
            )

        except NoSuchOptionError as e:
            # Can't ask, raise an exception
            if not interactive:
                raise e

            legacy.warning(e.message(option_name=option_name))
            print()

        except AmbiguousOptionError as e:
            # Can't ask, raise an exception
            if not interactive:
                raise e

            legacy.warning(e.message(option_name=option_name))
            print()

        else:
            # If the command was referenced via an alias, point the user to the
            # canonical name
            entered_name = raw_args[0]
            proper_name = function_names[choice_index]

            if entered_name != proper_name:
                legacy.warning(
                    f"There is no {option_name} named [primary]{entered_name}[/]. Assuming you meant to type [primary]{proper_name}[/]."
                )
                print()

            return function_names[choice_index], raw_args[1:]

    # Nothing specified, and can't ask -> raise an exception
    if not interactive:
        raise NoOptionGivenError(function_names)

    # Ask interactively
    options = {}
    for name, summary in zip(function_names, function_summaries):
        pretty_name = common.python_name_to_pretty(name)

        if summary is None:
            options[f"[bold]{pretty_name}[/]"] = name
        else:
            options[f"[bold]{pretty_name}[/] - {summary}"] = name

    return (
        menu.select(
            prompt="What would you like to do?",
            options=options,
        ),
        # Drop any passed arguments in this case. They cannot be parsed without
        # knowing the command, and since the command was nonsense they're likely
        # as well.
        [],
    )
