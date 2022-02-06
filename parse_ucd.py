"""
Parses files from the Unicode property database

See: http://www.unicode.org/reports/tr44/#Format_Conventions
"""

from fractions import Fraction
from math import nan
from types import SimpleNamespace
from typing import Any, NamedTuple

###################################### Constants #######################################

CODE_POINT_MIN = 0
CODE_POINT_MAX = 0x10FFFF

# https://www.unicode.org/reports/tr44/#UnicodeData.txt
NAME = 1
GENERAL_CATEGORY = 2
BIDI_CLASS = 4
DECOMPOSITION_MAPPING = 5
NUMERICAL_VALUE_DECIMAL = 6
NUMERICAL_VALUE_DIGIT = 7
NUMERICAL_VALUE_NUMERIC = 8
BIDI_MIRRORED = 9
# https://www.unicode.org/reports/tr24/#Data_File_SC
SCRIPT = 1

###################################### Sentinels #######################################
UsesNameRule = object()


class CodepointRange(NamedTuple):
    """
    Represents a range of code points from a Unicode Character Database file.
    Ranges are INCLUSIVE on both sides!
    """

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


class PropertyLookup:
    """
    Enables lookups of Unicode character properties using a sparse data structure with
    defaults for missing entries.
    """

    def __init__(self, *, default):
        self._table = []
        self._default = default

        # Cache results when iterating sequentially throuh properties:
        self._previous_record = InvalidPropertyRecord()
        self._previous_index = None

    def extend_last(self, code_point_range: CodepointRange, value):
        try:
            last_start, last_end, previous_value = self._table[-1]
        except IndexError:
            self._table.append(PropertyRecord.from_range(code_point_range, value))
            return

        assert code_point_range.start > last_end

        if code_point_range.start == last_end + 1 and value == previous_value:
            # We can extend the previous range.
            self._table[-1] = PropertyRecord(
                last_start, code_point_range.end_inclusive, value
            )
        else:
            self._table.append(PropertyRecord.from_range(code_point_range, value))

    def __getitem__(self, codepoint: int):
        if codepoint < CODE_POINT_MIN or codepoint > CODE_POINT_MAX:
            raise IndexError(codepoint)

        return self._find(codepoint)

    def _find(self, codepoint: int):
        record = self._previous_record

        if record.contains(codepoint):
            # Sequential access AND we're in the same range!
            return record.value

        if record.directly_before(codepoint):
            # Sequential access! We just want the NEXT range, if it exists.
            try:
                record = self._table[self._previous_index + 1]
            except IndexError:
                # After the end of stored records. Must create a fake record
                pass
            else:
                if record.contains(codepoint):
                    # The next range EXISTS, so cache it!
                    self._previous_record = record
                    self._previous_index += 1
                    return record.value

        # Not a simple sequential access, so we have to search:
        record, index = self._find_with_binary_search(codepoint)
        self._previous_record = record
        self._previous_index = index

        return record.value

    def _find_with_binary_search(self, codepoint: int):
        table = self._table

        def binary_search(start, end):
            if start >= end:
                # Could not find a record!
                return self._create_fake_record(codepoint, start)

            midpoint = start + ((end - start) // 2)
            record = table[midpoint]

            if record.contains(codepoint):
                return record, midpoint
            elif codepoint < record.start:
                return binary_search(start, midpoint)
            elif codepoint > record.end_inclusive:
                return binary_search(midpoint + 1, end)

        return binary_search(0, len(table))

    def _create_fake_record(self, codepoint: int, index: int):
        """
        Returns a synthesized PropertyRecord that is not actually stored.

        Should only be called with the index to the NEXT stored entry.
        """

        # Assume these are the store records:
        #
        # [
        #     # start  end  value
        #     (    31,  31, 'X'),  # index 0
        #     (    65,  90, 'X'),  # index 1
        # ]
        #
        # We synthesize a record by looking at the neighbours of the failed binary
        # search.
        #
        # Example:
        # Binary search failed looking for a value for 48. It will fail at index 1.
        #
        #   codepoint = 48
        #   index = 1
        #
        # We create a fake record by looking at its neighbours:
        #
        # [
        #     # start  end  value
        #     (    31,  31, 'X'), # index 0
        #                          <- (32, 64, 'Default')
        #     (    65,  90, 'X'), # index 1
        # ]

        if index > 0:
            # The fake entry must start after the PREVIOUS stored entry.
            fake_start = self._table[index - 1].end_inclusive + 1
        else:
            fake_start = CODE_POINT_MIN

        try:
            # The fake entry must end before the CURRENT stored entry.
            fake_end = self._table[index].start - 1
        except IndexError:
            fake_end = CODE_POINT_MAX

        assert fake_start <= codepoint <= fake_end

        return PropertyRecord(fake_start, fake_end, self._default), index

    def __len__(self) -> int:
        return len(self._table)


class PropertyRecord(NamedTuple):
    """
    An entry in the PropertyLookup table.
    """

    start: int
    end_inclusive: int
    value: Any

    contains = CodepointRange.contains

    def directly_before(self, codepoint: int) -> bool:
        return self.end_inclusive + 1 == codepoint

    @classmethod
    def from_range(cls, r: CodepointRange, value: Any):
        start, end = r
        return cls(start, end, value)


class InvalidPropertyRecord:
    """
    Sentinel value
    """

    def contains(self, codepoint: int) -> bool:
        return False

    def directly_before(self, codepoint: int) -> bool:
        return False

    def _raise(self):
        raise AssertionError("Should not access property of InvalidPropertyRecord")

    start = property(_raise)
    end_inclusive = property(_raise)
    value = property(_raise)


class NamePropertyLookup(PropertyLookup):
    """
    Specialized property lookup for the Name property.

    Some of the values here are algorithmically generated.
    """

    def __getitem__(self, codepoint: int) -> str:
        name = super().__getitem__(codepoint)
        if name is UsesNameRule:
            raise NotImplementedError(f"need to generate name for U+{codepoint:04X}")
        return name


# https://www.unicode.org/reports/tr44/#Default_Values_Table
_general_category = PropertyLookup(default="Cc")
_name = NamePropertyLookup(default="")
_decomposition = PropertyLookup(default="")
_numeric_type = PropertyLookup(default=None)
_numeric_value = PropertyLookup(default=nan)
_script = PropertyLookup(default="Unknown")


def parse_all():
    parse_unicode_data()
    parse_scripts()

    return SimpleNamespace(
        general_category=_general_category,
        name=_name,
        decomposition=_decomposition,
        numeric_type=_numeric_type,
        numeric_value=_numeric_value,
        script=_script,
    )


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

    >>> _decomposition[ord('A')]
    ''
    >>> _decomposition[0x212B]
    '00C5'
    >>> _decomposition[ord('ở')]
    '01A1 0309'
    >>> _decomposition[0x01A1]
    '006F 031B'
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


def parse_unicode_data_lines(lines):
    while line := next_or_none(lines):
        result = parse_line(line)
        if result is None:
            continue

        code_point_range, fields = result
        assert code_point_range.is_single_code_point
        codepoint, _ = code_point_range

        raw_name = fields[NAME]

        if starts_implied_range(raw_name):
            # Implied ranges are split on two lines and are indicated by the NAME field.
            next_range, next_fields = parse_line(next(lines))
            assert next_range.is_single_code_point
            end_codepoint, _ = next_range
            assert codepoint < end_codepoint
            assert ends_implied_range(next_fields[NAME])
            assert fields[2:] == next_fields[2:]

            code_point_range = CodepointRange(codepoint, end_codepoint)

        _general_category.extend_last(code_point_range, fields[GENERAL_CATEGORY])
        add_name(code_point_range, raw_name)
        add_numeral(
            code_point_range,
            *fields[NUMERICAL_VALUE_DECIMAL : NUMERICAL_VALUE_NUMERIC + 1],
        )
        if decomposition := fields[DECOMPOSITION_MAPPING]:
            _decomposition.extend_last(code_point_range, decomposition)


def add_name(code_point_range: CodepointRange, raw_name: str):
    """
    See: https://www.unicode.org/reports/tr44/#Name
    """
    if code_point_range.is_range:
        # I'm too lazy to implement codepoint range rules so...
        # https://www.unicode.org/versions/Unicode14.0.0/ch04.pdf
        _name.extend_last(code_point_range, NotImplemented)
    else:
        _name.extend_last(code_point_range, raw_name)


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
