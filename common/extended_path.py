from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Optional
    from common.extended_bs4 import BeautifulSoup


# Standard Library
import io
import json
import os
import random
import re
import shutil
import string
from datetime import date, datetime
from pathlib import Path


# There's a weird issue where with Path when you try to make a subclass of it
# It's impossible to subclass Path and instead need to subclass the concrete implementation
# See: https://newbedev.com/subclass-pathlib-path-fails
class ExtendedPath((type(Path()))):
    """Extended version of Path that adds a couple of extra features"""

    ILLEGAL_STRINGS = [
        "CON",
        "PRN",
        "AUX",
        "NUL",
        "COM1",
        "COM2",
        "COM3",
        "COM4",
        "COM5",
        "COM6",
        "COM7",
        "COM8",
        "COM9",
        "LPT1",
        "LPT2",
        "LPT3",
        "LPT4",
        "LPT5",
        "LPT6",
        "LPT7",
        "LPT8",
        "LPT9",
    ]

    def up_to_date(self, timestamp: Optional[datetime] = None) -> bool:
        """Check if a file exists and is up to date"""
        # If file does not exist it can't be up to date
        if not self.exists():
            return False

        # If no timestamp is given and the file exists it is up to date
        if timestamp is None:
            return True

        # Make timestampa date time aware
        timestamp = timestamp.astimezone()

        # If file is older it is not up to date
        if datetime.fromtimestamp(self.stat().st_mtime).astimezone() < timestamp:
            return False

        # File exists and is newer
        return True

    def outdated(self, timestamp: Optional[datetime]) -> bool:
        """Check if a file does not exist or is outdated"""
        return not self.up_to_date(timestamp)

    def file_count(self: ExtendedPath) -> int:
        """Count the number of files in a folder"""
        return len(list(self.glob("*")))

    def write(self, content: bytes | str):
        """Write a bytes or a str object to a file, and will automatically create the directory if needed

        This is useful because str and byte objects need to be written to files with different parameters"""
        ExtendedPath(self.parent).mkdir(parents=True, exist_ok=True)

        if isinstance(content, bytes):
            f = io.open(self, "wb")
            f.write(content)
        else:
            f = io.open(self, "w", encoding="utf-8")
            f.write(content)
        f.close()

    def write_json(self, content: bytes | str):
        """Write json to a file"""
        self.write(json.dumps(content))

    def move(self, destination: ExtendedPath):
        """Move a file and automatically create the directory for the file if needed"""
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(self, destination)

    def copy(self, destination: ExtendedPath):
        """Copy a file and automatically create the directory for the file if needed"""
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(self, destination)

    def copy_dir(self, destination: ExtendedPath):
        """Copy a file and automatically create the directory for the file if needed"""
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(self, destination)

    def parsed_html(self, update: bool = False) -> BeautifulSoup:
        """Read and parse an html file"""
        # Import bs4 here so there are no required external dependencies for ExtendedPath
        # Common
        from common.extended_bs4 import BeautifulSoup

        if not hasattr(self, "_parsed_json") or update:
            self._parsed_html = BeautifulSoup(self.read_bytes(), "lxml")
        return self._parsed_html

    def parsed_json(self, update: bool = False) -> Any:
        """Read and parse a json file"""
        if not hasattr(self, "_parsed_json") or update:
            self._parsed_json = json.loads(self.read_bytes())
        return self._parsed_json

    def delete(self):
        """Delete a folder or a file without having to worry about which it is\n
        This is useful because normally files and folders need to be deleted differently"""
        if self.exists():
            if self.is_file():
                os.remove(self)
            else:
                shutil.rmtree(self)

    @classmethod
    def convert_to_path(
        cls,
        folder_name: str | int | datetime | float | ExtendedPath | date,
        prepend: str = "",
        append: str = "",
        max_length: int = 255,
    ) -> ExtendedPath:
        "Converts multiple different objects into a a ExtendedPath object"
        # Date, Integer and paths can just be cast to a string
        if isinstance(folder_name, int) or isinstance(folder_name, ExtendedPath) or isinstance(folder_name, date):
            return cls.convert_to_path(str(folder_name), prepend, append, max_length)

        # Datetime needs to be converted to a float then an integer
        elif isinstance(folder_name, datetime):
            return cls.convert_to_path(int(folder_name.timestamp()), prepend, append, max_length)

        # Floats need to be converted to int
        elif isinstance(folder_name, float):
            return cls.convert_to_path(int(folder_name), prepend, append, max_length)

        # Strings need to be cleaned up and made into a legal path
        else:
            return cls.__str_to_path(folder_name, prepend, append, max_length)

    @classmethod
    def __str_to_path(cls, string: str, prepend: str = "", append: str = "", max_length: int = 255) -> ExtendedPath:
        """Convert a string into a legal ExtendedPath object\n
        This is made for Windows because it has extra limitations compared to other operating systems"""
        # Calculate how long the string must be before prepend and append values are added
        truncate_length = max_length - len(prepend.encode("utf-8")) - len(append.encode("utf-8"))

        # Truncate the string until it fits in the correct number of bytes
        # Use bytes not characters because bytes are what is used for path lengths
        while len(string.encode("utf-8")) > truncate_length:
            string = string[:-1]

        # Join strings together to make final file name
        output = prepend + string + append

        # Delete characters that are illegal on Windows
        output = re.sub(r'[/\\:*?"<>|]', "", output)

        # If file has trailing space/period append an underscore or replace it with an underscore
        # If the file name is illegal on Windows append an underscore or replace the last character with an underscore
        while output.endswith((".", " ")) or output in cls.ILLEGAL_STRINGS:
            if len(output.encode("utf-8")) < max_length:
                output = output + "_"
            else:
                output = output[:-1] + "_"

        return ExtendedPath(output)

    @classmethod
    def temporary_file_path(cls, base_dir: ExtendedPath, extension: str = "") -> ExtendedPath:
        """Get a ExtendedPath using a randomly generated value that can be used as temporary storage"""
        # Generate a 32 character random string user just upper case letters and numbers
        temp_name = "".join(random.choices(string.ascii_uppercase + string.digits, k=32))

        # If an extension is given add it to the temporary name
        # This makes it easier to parse through temporary files when debugging
        if extension:
            # For parameter consistency force extension values to never start with a dot
            if extension.startswith("."):
                raise ValueError("Extension should not start with a dot")
            else:
                temp_name = f"{temp_name}.{extension}"

        return base_dir / "temp" / f"{temp_name}"

    # TODO: This can probably be sped up
    def remove_parent(self, parents_to_remove: int = 1) -> ExtendedPath:
        output = ExtendedPath()
        for i, x in enumerate(self.parts):
            # Ignore the first value to remove the top level directory
            if i > parents_to_remove - 1:
                # Rebuild path using the remaining parts
                output = output / x
        return output

    def legalize(self) -> ExtendedPath:
        output = ExtendedPath()
        for x in self.parts:
            # Rebuild path using the remaining parts
            output = output / ExtendedPath.convert_to_path(x)
        return output

    def aware_mtime(self) -> datetime:
        """Create an aware timestamp from the file's mtime"""
        return datetime.fromtimestamp(self.stat().st_mtime).astimezone()

    def depth(self) -> int:
        """Get the depth of the path"""
        return len(self.parts)
