from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Optional

# Standard Library
from datetime import datetime

# Django
from django.db import models

# Common
from common.extended_path import ExtendedPath


class ModelWithIdAndTimestamp(models.Model):
    """Basic Model that includes an auto incrmeented id, info_timestamp, and info_modified_timestamp"""

    # Required to be able to subclass models.Model
    class Meta:  # type: ignore - Meta class always throws type errors
        abstract = True

    # Automatically genenrated ID
    id = models.AutoField(primary_key=True)

    # Timestamps
    info_timestamp = models.DateTimeField()
    info_modified_timestamp = models.DateTimeField()

    def information_up_to_date(
        self,
        minimum_info_timestamp: Optional[datetime] = None,
        minimum_modified_timestamp: Optional[datetime] = None,
    ) -> bool:
        """Check if the information in a model is up to date"""
        # If a timestmap is missing the information has to be outdated
        if self.info_timestamp is None or self.info_modified_timestamp is None:
            return False

        # Make sure the information is up to date
        if minimum_info_timestamp is not None and minimum_info_timestamp > self.info_timestamp:
            return False

        # CHeck if the imported information
        if minimum_modified_timestamp is not None and minimum_modified_timestamp > self.info_modified_timestamp:
            return False

        # If other tests passed information is up to date
        return True

    def information_oudated(
        self,
        minimum_info_timestamp: Optional[datetime] = None,
        minimum_modified_timestamp: Optional[datetime] = None,
    ) -> bool:
        return not self.information_up_to_date(minimum_info_timestamp, minimum_modified_timestamp)

    def add_timestamps_and_save(self, file: ExtendedPath | datetime) -> None:
        """Add timestamps to a model object and save it"""
        self.add_timestamps(file)
        self.save()

    def add_timestamps(self, file: ExtendedPath | datetime) -> None:
        """Add timestamps to a model object"""
        if isinstance(file, ExtendedPath):
            self.info_timestamp = file.aware_mtime()
        else:
            self.info_timestamp = file.astimezone()

        self.info_modified_timestamp = datetime.now().astimezone()
