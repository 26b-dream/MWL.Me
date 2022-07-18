# re isn't actually a class it's just a collection of functions
# The easiest way to add a function to it is to import everything and create additional functions
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Match, Pattern

# Standard Library
import re as re  # Imported so re.search works

# Importing re with an asterisk gives a warning, just ignore it because I really want everything imported
from re import *  # type: ignore # noqa - Imported to export


class StrictPatternFailure(Exception):
    pass


# TODO: Remove code that uses Pattern[str] because it creates a pointless extra step maybe?
def strict_search(pattern: Pattern[str] | str, string: str) -> Match[str]:
    """Like .search but will raise an error if no match is found"""
    output = re.search(pattern, string)
    if output is None:
        raise StrictPatternFailure(f"{string} did not include {pattern}")
    else:
        return output
