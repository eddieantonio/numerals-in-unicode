from unicodedata import bidirectional

import parse_ucd

__all__ = ["Codepoint"]


class Codepoint:
    """
    Represents a Unicode character.

    >>> cp = Codepoint(ord('৪'))
    >>> cp.character
    '৪'
    >>> cp.value
    2538
    >>> cp.to_uplus_notation()
    'U+09EA'
    >>> cp
    Codepoint(0x09EA)
    >>> cp.numeric_type
    'Decimal'
    >>> cp.to_numeric()
    4.0
    >>> cp.to_digit()
    4
    >>> cp.to_decimal()
    4
    >>> cp.bidirectional_class
    'L'
    >>> cp.script
    'Bengali'
    >>> print(cp)
    U+09EA

    >>> len(list(Codepoint.iterate_all_codepoints()))
    1114112
    """

    __slots__ = ("_ord",)

    MAX_CODE_POINT = 0x10FFFF

    def __init__(self, codepoint: int):
        assert 0 <= codepoint <= self.MAX_CODE_POINT
        self._ord = codepoint

    @property
    def value(self) -> int:
        return self._ord

    @property
    def character(self) -> str:
        return chr(self._ord)

    @property
    def script(self) -> str:
        return _properties.script[self._ord]

    @property
    def bidirectional_class(self) -> str:
        return bidirectional(self.character)

    @property
    def numeric_type(self):
        return _properties.numeric_type[self._ord]

    def to_decimal(self, *args) -> int:
        if self.numeric_type == "Decimal":
            return _properties.numeric_value[self._ord]

        if not args:
            raise ValueError
        else:
            return args[0]

    def to_digit(self, *args) -> int:
        if self.numeric_type in ("Decimal", "Digit"):
            return _properties.numeric_value[self._ord]

        if not args:
            raise ValueError
        else:
            return args[0]

    def to_numeric(self, *args) -> float:
        if self.numeric_type is not None:
            return float(_properties.numeric_value[self._ord])

        if not args:
            raise ValueError
        else:
            return args[0]

    def to_uplus_notation(self) -> str:
        """
        Returns a string representation of the codepoint in U+ notation.

        See: https://www.unicode.org/versions/Unicode13.0.0/appA.pdf
        """
        return f"U+{self.value:04X}"

    def __str__(self) -> str:
        return self.to_uplus_notation()

    def __repr__(self) -> str:
        clsname = type(self).__qualname__
        return f"{clsname}(0x{self.value:04X})"

    @staticmethod
    def iterate_all_codepoints():
        return (Codepoint(cp) for cp in range(Codepoint.MAX_CODE_POINT + 1))


_properties = parse_ucd.parse_all()
