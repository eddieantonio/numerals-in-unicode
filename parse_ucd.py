"""
Parses files from the Unicode property database

See: http://www.unicode.org/reports/tr44/#Format_Conventions
"""

from fractions import Fraction
from math import nan
from typing import NamedTuple

# https://www.unicode.org/reports/tr44/#UnicodeData.txt
NAME = 1
GENERAL_CATEGORY = 2
BIDI_CLASS = 4
NUMERICAL_VALUE_DECIMAL = 6
NUMERICAL_VALUE_DIGIT = 7
NUMERICAL_VALUE_NUMERIC = 8
BIDI_MIRRORED = 9
# https://www.unicode.org/reports/tr24/#Data_File_SC
SCRIPT = 1


class CodepointRange(NamedTuple):
    start: int
    end_inclusive: int

    @property
    def is_single_code_point(self):
        return self.start == self.end_inclusive

    @property
    def is_range(self):
        return self.start != self.end_inclusive

    def contains(self, codepoint: int) -> bool:
        """
        >>> ascii_digits = CodepointRange(0x0030, 0x0039)
        >>> ascii_digits.contains(0x30)
        True
        >>> ascii_digits.contains(0x39)
        True
        >>> ascii_digits.contains(0x35)
        True
        >>> ascii_digits.contains(0x20)
        False
        >>> ascii_digits.contains(0x2000)
        False
        """
        return self.start <= codepoint <= self.end_inclusive

    def iter_codepoints(self):
        """
        Yields successive codepoints (ints) in a Unicode range.

        >>> list(CodepointRange(0x0030, 0x0039).iter_codepoints())
        [48, 49, 50, 51, 52, 53, 54, 55, 56, 57]
        """
        return iter(range(self.start, self.end_inclusive + 1))


def parse_line(line: str):
    r"""
    Parses a line from a Unicode Character Database text file.

    See: http://www.unicode.org/reports/tr44/#Format_Conventions

    >>> parse_line("\n")
    >>> parse_line("# I'm a comment\n")
    >>> parse_line("0020          ; Common # Zs       SPACE")
    (CodepointRange(start=32, end_inclusive=32), ['0020', 'Common'])
    >>> parse_line("1D2E0..1D2F3  ; Common # No  [20] MAYAN NUMERAL ZERO..MAYAN NUMERAL NINETEEN")
    (CodepointRange(start=119520, end_inclusive=119539), ['1D2E0..1D2F3', 'Common'])
    """

    line = line.rstrip("\n")
    content, _, _comment = line.partition("#")

    if content == "":
        return None

    # "Each line of data consists of fields separated by semicolons."
    # "Leading and trailing spaces within a field are not significant."
    # From: http://www.unicode.org/reports/tr44/#Data_Fields
    fields = [field.strip() for field in content.split(";")]
    assert len(fields) >= 2, f"Did not find enough fields in line: {line!r}"

    range_expression = fields[0]

    start_hex, range_marker, end_hex = range_expression.partition("..")
    start = int(start_hex, base=16)

    if range_marker:
        # Found a range like 0030..0039:
        end = int(end_hex, base=16)
        code_point_range = CodepointRange(start, end)
    else:
        # Found a single codepoint.
        code_point_range = CodepointRange(start, start)

    return code_point_range, fields


# Sentinels
RaiseIndexError = object()
UsesNameRule = object()


class PropertyLookup:
    def __init__(self, default=RaiseIndexError):
        self._table = []
        self._default = default

    def extend_last(self, range_: CodepointRange, value):
        try:
            (last_start, last_end), previous_value = self._table[-1]
        except IndexError:
            self._table.append((range_, value))
            return

        assert range_.start > last_end

        if range_.start == last_end + 1 and value == previous_value:
            # We can extend the previous range.
            self._table[-1] = (
                CodepointRange(last_start, range_.end_inclusive),
                value,
            )
        else:
            self._table.append((range_, value))

    def __getitem__(self, codepoint: int):
        if codepoint < 0 or codepoint > 0x10FFFF:
            raise IndexError(codepoint)

        try:
            return self._find(codepoint)
        except IndexError:
            if self._default is RaiseIndexError:
                raise
            else:
                return self._default

    def _find(self, codepoint: int):
        table = self._table

        def binary_search(start, end):
            if start >= end:
                raise IndexError(codepoint)

            midpoint = start + ((end - start) // 2)
            range_, value = table[midpoint]

            if range_.contains(codepoint):
                return value
            elif codepoint < range_.start:
                return binary_search(start, midpoint)
            elif codepoint > range_.end_inclusive:
                return binary_search(midpoint + 1, end)

        return binary_search(0, len(table))

    def __len__(self) -> int:
        return len(self._table)


class NamePropertyLookup(PropertyLookup):
    def __getitem__(self, codepoint: int) -> str:
        name = super().__getitem__(codepoint)
        if name is UsesNameRule:
            raise NotImplementedError(f"need to generate name for U+{codepoint:04X}")
        return name


# https://www.unicode.org/reports/tr44/#Default_Values_Table
_general_category = PropertyLookup(default="Cc")
_name = NamePropertyLookup(default="")
_numeric_type = PropertyLookup(default=None)
_numeric_value = PropertyLookup(default=nan)
_script = PropertyLookup(default="Unknown")


def parse_unicode_data():
    """
    >>> parse_unicode_data()

    >>> _general_category[32]
    'Zs'
    >>> _general_category[ord('1')]
    'Nd'
    >>> _general_category[ord('a')]
    'Ll'
    >>> _general_category[ord('A')]
    'Lu'
    >>> _general_category[ord('💩')]
    'So'
    >>> _general_category[0x1D2E0]
    'No'

    >>> _name[32]
    'SPACE'
    >>> _name[ord('💩')]
    'PILE OF POO'

    >>> _numeric_type[ord('9')]
    'Decimal'
    >>> _numeric_value[ord('9')]
    9
    >>> _numeric_type[0x2155]
    'Numeric'
    >>> _numeric_value[0x2155]
    Fraction(1, 5)

    >>> _numeric_value[0x1D2E0]
    0
    >>> _numeric_value[0x1D2E0 + 19]
    19
    """
    with open("./UnicodeData.txt", encoding="UTF-8") as data_file:
        return parse_unicode_data_lines(iter(data_file))


def parse_scripts():
    """
    >>> parse_scripts()

    >>> _script[ord('a')]
    'Latin'
    >>> _script[ord('-')]
    'Common'
    >>> _script[0xDFE3]
    'Unknown'
    >>> _script[ord('α')]
    'Greek'
    >>> _script[ord('д')]
    'Cyrillic'
    >>> _script[0x0641]
    'Arabic'
    """

    with open("./Scripts.txt", encoding="UTF-8") as data_file:
        # Scripts.txt is ordered BY SCRIPT, and not BY CODE POINT.
        # Slurp all the data first, then sort it to insert ordered into the
        # PropertyLookup
        ordered_lines = [
            result for line in data_file if (result := parse_line(line)) is not None
        ]
        ordered_lines.sort()

        for code_point_range, fields in ordered_lines:
            _script.extend_last(code_point_range, fields[SCRIPT])


def parse_unicode_data_lines(lines):
    while line := next_or_none(lines):
        result = parse_line(line)
        if result is None:
            continue

        range_, fields = result
        assert range_.is_single_code_point
        codepoint, _ = range_

        raw_name = fields[NAME]

        if starts_implied_range(raw_name):
            # Implied ranges are split on two lines and are indicated by the NAME field.
            next_range, next_fields = parse_line(next(lines))
            assert next_range.is_single_code_point
            end_codepoint, _ = next_range
            assert codepoint < end_codepoint
            assert ends_implied_range(next_fields[NAME])
            assert fields[2:] == next_fields[2:]

            range_ = CodepointRange(codepoint, end_codepoint)

        _general_category.extend_last(range_, fields[GENERAL_CATEGORY])
        add_name(range_, raw_name)
        add_numeral(
            range_, *fields[NUMERICAL_VALUE_DECIMAL : NUMERICAL_VALUE_NUMERIC + 1]
        )


def add_name(range_: CodepointRange, raw_name: str):
    """
    See: https://www.unicode.org/reports/tr44/#Name
    """
    if range_.is_range:
        # I'm too lazy to implement codepoint range rules so...
        # https://www.unicode.org/versions/Unicode14.0.0/ch04.pdf
        _name.extend_last(range_, NotImplemented)
    else:
        _name.extend_last(range_, raw_name)


def add_numeral(code_point_range: CodepointRange, decimal, digit, numeral):
    if not numeral:
        # Not a number
        return

    if decimal:
        value = int(decimal)
        assert 0 <= value <= 9
        _numeric_type.extend_last(code_point_range, "Decimal")
        _numeric_value.extend_last(code_point_range, value)
    elif digit:
        # Numeric_Type=Digit is kept for compatibility purposes, but not really useful.
        value = int(digit)
        assert 0 <= value <= 9
        _numeric_type.extend_last(code_point_range, "Digit")
        _numeric_value.extend_last(code_point_range, value)
    elif numeral:
        value = parse_numeral(numeral)
        _numeric_type.extend_last(code_point_range, "Numeric")
        _numeric_value.extend_last(code_point_range, value)


def parse_numeral(numeral: str):
    """
    >>> parse_numeral("1/5")
    Fraction(1, 5)
    >>> parse_numeral("19")
    19
    """
    if "/" in numeral:
        nom, _, denom = numeral.partition("/")
        return Fraction(int(nom), int(denom))

    return int(numeral)


def starts_implied_range(name: str) -> bool:
    return name.endswith(", First>")


def ends_implied_range(name: str) -> bool:
    return name.endswith(", Last>")


####################################### Utilties #######################################


def next_or_none(it):
    try:
        return next(it)
    except StopIteration:
        return None
