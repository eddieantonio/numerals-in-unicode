"""
Parses files from the Unicode property database

See: http://www.unicode.org/reports/tr44/#Format_Conventions
"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class CodepointRange:
    start: int
    end_inclusive: int

    @property
    def is_singleton(self):
        return self.start == self.end_inclusive

    def __iter__(self):
        """
        Yields successive codepoints (ints) in a Unicode range.

        >>> list(CodepointRange(0x0030, 0x0039))
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
    (CodepointRange(start=32, end_inclusive=32), ['Common'])
    >>> parse_line("1D2E0..1D2F3  ; Common # No  [20] MAYAN NUMERAL ZERO..MAYAN NUMERAL NINETEEN")
    (CodepointRange(start=119520, end_inclusive=119539), ['Common'])
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

    range_expression, *data_fields = fields

    start_hex, range_marker, end_hex = range_expression.partition("..")
    start = int(start_hex, base=16)

    if range_marker:
        # Found a range like 0030..0039:
        end = int(end_hex, base=16)
        codepoint_range = CodepointRange(start, end)
    else:
        # Found a single codepoint.
        codepoint_range = CodepointRange(start, start)

    return codepoint_range, data_fields
