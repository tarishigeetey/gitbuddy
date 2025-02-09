from __future__ import annotations

import bisect
import typing as t
import weakref

import u

from ._utils import cached, join_symbols, parse_symbol
from .quantity import Quantity
from .capital_quantities import QUANTITY, DIV, MUL, Q2


__all__ = ["Unit"]


Q_co = t.TypeVar("Q_co", bound=QUANTITY, covariant=True)


units_by_symbol: t.MutableMapping[str, Unit] = weakref.WeakValueDictionary()


class Unit(t.Generic[Q_co]):
    """
    Represents a unit of measurement for a certain `Quantity`.

    To create your own unit, simply create an instance of this class:

    ```
    seconds = Unit(Duration, "s", 1)
    minutes = Unit(Duration, "min", 60)
    coulombs = Unit(ElectricCharge, "C", seconds.multiplier * amperes.multiplier)
    ```
    """

    @t.overload
    def __init__(
        self,
        quantity: t.Type[Quantity[Q_co]],
        symbol: str,
        multiplier: float,
    ):
        pass

    @t.overload
    def __init__(
        self,
        unit: Unit[Q_co],
        /,
        symbol: str,
    ):
        pass

    def __init__(  # type: ignore (redeclaration)
        self,
        quantity: t.Type[Quantity[Q_co]] | Unit[Q_co],
        symbol: str,
        multiplier: float | None = None,
    ):
        self.symbol = symbol

        if isinstance(quantity, Unit):
            self.quantity = quantity.quantity
            self.multiplier = quantity.multiplier
        else:
            self.quantity = quantity

            assert isinstance(multiplier, (int, float))
            self.multiplier = multiplier

        if not isinstance(self, UnregisteredUnit):
            units_by_symbol[symbol] = self

            # Register this unit with the Quantity
            units = t.cast(list[Unit[Q_co]], self.quantity.units)
            bisect.insort(units, self, key=lambda unit: unit.multiplier)

    @staticmethod
    def _from_symbol(symbol: str) -> Unit:
        try:
            return units_by_symbol[symbol]
        except KeyError:
            pass

        # Check if it starts with a prefix
        if len(symbol) > 1:
            prefix_symbol = symbol[0]
            try:
                prefix = u.Prefix.from_symbol(prefix_symbol)
            except ValueError:
                pass
            else:
                symbol = symbol[1:]
                try:
                    unit = units_by_symbol[symbol]
                except KeyError:
                    pass
                else:
                    return prefix(unit)

        raise ValueError(f"The symbol {symbol!r} doesn't correspond to a known Unit")

    @classmethod
    def parse(cls, symbol: str, /, quantity: t.Type[Quantity[Q2]] = Quantity) -> Unit[Q2]:
        exponents = parse_symbol(symbol)

        unit: Unit

        # Try to start with a positive exponent
        try:
            sym = next(sym for sym, exponent in exponents.items() if exponent > 0)
        except StopIteration:
            unit = u.one
        else:
            unit = Unit._from_symbol(sym) ** exponents.pop(sym)

        for sym, exponent in exponents.items():
            if exponent > 0:
                unit *= Unit._from_symbol(sym) ** exponent
            elif exponent < 0:
                unit /= Unit._from_symbol(sym) ** -exponent

        if quantity is Quantity or unit.is_compatible_with(quantity):
            return unit  # type: ignore (???)

        raise ValueError(f"{symbol!r} is not a unit of {cls}")

    @t.overload
    def is_compatible_with(self, unit: Unit, /) -> t.TypeGuard[Unit[Q_co]]: ...

    @t.overload
    def is_compatible_with(self, quantity: t.Type[Quantity[Q2]], /) -> t.TypeGuard[Unit[Q2]]: ...

    def is_compatible_with(
        self,
        other: t.Union[Unit[Q2], t.Type[Quantity[Q2]]],
        /,
    ) -> t.TypeGuard[Unit[Q2]]:
        if isinstance(other, Unit):
            return self.quantity.exponents == other.quantity.exponents
        else:
            return self.quantity.exponents == other.exponents

    @t.overload
    def __pow__(self, exponent: t.Literal[-1], /) -> Unit[DIV[u.ONE, Q_co]]: ...

    @t.overload
    def __pow__(self, exponent: t.Literal[0], /) -> Unit[u.ONE]: ...

    @t.overload
    def __pow__(self, exponent: t.Literal[1], /) -> t.Self: ...

    @t.overload
    def __pow__(self, exponent: t.Literal[2], /) -> Unit[MUL[Q_co, Q_co]]: ...

    @t.overload
    def __pow__(self, exponent: t.Literal[3], /) -> Unit[MUL[MUL[Q_co, Q_co], Q_co]]: ...

    @t.overload
    def __pow__(self, exponent: int, /) -> Unit: ...

    def __pow__(self, exponent: int) -> Unit:
        if exponent > 0:
            # Avoid use of `u.one` here because this code runs before the module is completely
            # initialized
            result = self

            for _ in range(exponent - 1):
                result *= self
        else:
            result = u.one

            for _ in range(-exponent):
                result /= self

        return result

    @cached
    def __mul__(self, other: Unit[Q2], /) -> Unit[MUL[Q_co, Q2]]:
        return UnregisteredUnit(
            join_quantities(self.quantity, other.quantity, MUL),
            join_symbols(self.symbol, other.symbol, "*"),
            self.multiplier * other.multiplier,
        )

    @cached
    def __truediv__(self, other: Unit[Q2], /) -> Unit[DIV[Q_co, Q2]]:
        if (
            t.get_args(self.quantity)[0].__name__ == "ONE"
            and "*" not in other.symbol
            and "/" not in other.symbol
        ):
            if "*" in other.symbol or "/" in other.symbol:
                symbol = f"({other.symbol})⁻¹"
            else:
                symbol = other.symbol + "⁻¹"
        elif "*" in other.symbol or "(" in other.symbol:
            symbol = join_symbols(self.symbol, other.symbol, "/(") + ")"
        else:
            symbol = join_symbols(self.symbol, other.symbol, "/")

        return UnregisteredUnit(
            join_quantities(self.quantity, other.quantity, DIV),
            symbol,
            self.multiplier / other.multiplier,
        )

    def __rmul__(self, value: float, /) -> Quantity[Q_co]:
        return Quantity(value, self)

    def __rtruediv__(self, value: t.Literal[1], /) -> Unit[DIV[u.ONE, Q_co]]:
        assert value == 1
        return u.one / self

    def __call__(self, value: float | Quantity[Q_co], /) -> Quantity[Q_co]:
        if isinstance(value, Quantity):
            return Quantity(value.to_number(self), self)
        else:
            return Quantity(value, self)

    def __repr__(self) -> str:
        return f"Unit({self.quantity!r}, {self.symbol!r}, {self.multiplier!r})"

    def __str__(self) -> str:
        return self.symbol


class UnregisteredUnit(Unit):
    """
    Instances of this class won't have their `symbol` registered in the global lookup table.
    """


def join_quantities(q1: type[Quantity], q2: type[Quantity], joiner) -> type[Quantity]:
    [a] = t.get_args(q1)
    [b] = t.get_args(q2)

    return Quantity[joiner[a, b]]
