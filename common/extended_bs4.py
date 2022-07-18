from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    # Third Party
    from bs4.element import ResultSet

# Third Party
from bs4 import BeautifulSoup  # type: ignore # noqa F401 - Imported to export
from bs4.element import Tag as Tag

# Common
from common.extend_class import extend_class


class StrictBeautifulSoupFaiure(Exception):
    pass


# Because of the way BS4 is designed I have to monkey patch the features into Tag and BeautifulSoup
# Creating a new class will return original Tag objects that do not have the extra functions
# This will overwrite the original Tag and BeautifulSoup classes
# The alternative is digging into how Tag objects are created and replacing them, but it's not worth the time
class ExtendedTag(Tag):
    def strict_select(self: Tag, selector: str) -> ResultSet[Tag]:
        """Same as .select but it will raise an exception if no match is found"""
        output = self.select(selector)
        if len(output) == 0:
            raise StrictBeautifulSoupFaiure(f"No matches found for strict_select({selector})")
        else:
            return output

    def strict_select_one(self: Tag, selector: str) -> Tag:
        """Same as .select but it will raise an exception the number of matches is not 1"""
        output = self.select(selector)
        number_of_matches = len(output)
        if number_of_matches == 1:
            return output[0]
        else:
            raise StrictBeautifulSoupFaiure(
                f"Wrong number of matches found for strict_select({selector}), found {number_of_matches}"
            )

    def strict_get(self: Tag, key: str) -> str:
        """Same as .get but it will raise an exception if no match is found"""
        output = self.get(key)
        if isinstance(output, str):
            return output
        else:
            raise StrictBeautifulSoupFaiure(f"No matches found for strict_get({key})")

    def strict_parent(self: Tag) -> Tag:
        """Same as .parent but it will raise an exception if no match is found"""
        output = self.parent
        if isinstance(output, Tag):
            return output
        else:
            raise StrictBeautifulSoupFaiure("No matches found for strict_parent()")


ORIGINAL_TAG_FUNCTIONS = dir(Tag)
extend_class(Tag, ExtendedTag)
