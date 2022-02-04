from unicodedata import bidirectional, decimal, digit, numeric

from unicodedata2 import script

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
    def plane_number(self) -> int:
        """
        >>> Codepoint(0x61).plane_number
        0
        >>> Codepoint(0x01F4A9).plane_number
        1
        """
        return (0xFF0000 & self.value) >> 16

    @property
    def script(self) -> str:
        return script(self.character)

    @property
    def bidirectional_class(self) -> str:
        return bidirectional(self.character)

    def to_decimal(self, *args) -> int:
        return decimal(self.character, *args)

    def to_digit(self, *args) -> int:
        return digit(self.character, *args)

    def to_numeric(self, *args) -> float:
        return numeric(self.character, *args)

    def to_uplus_notation(self) -> str:
        if self.value <= 0xFFFF:
            return f"U+{self.value:04X}"
        else:
            assert 0xFFFF < self.value <= 0x10FFFF
            return f"U+{self.value:06X}"

    def __str__(self) -> str:
        return self.to_uplus_notation()

    def __repr__(self) -> str:
        clsname = type(self).__qualname__
        return f"{clsname}(0x{self.value:04X})"

    @staticmethod
    def iterate_all_codepoints():
        return (Codepoint(cp) for cp in range(Codepoint.MAX_CODE_POINT + 1))
