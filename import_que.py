from __future__ import annotations

import time
from datetime import datetime

from django.db.models import Q

import common.configure_django  # type: ignore - Modifies global values
from common.myanimelist_media import MyAnimeListMedia
from common.myanimelist_user import MyAnimeListUser
from main.models import ImportQue

if __name__ == "__main__":
    while True:
        # Get the highest priority entry that has outdated information
        media = (
            ImportQue.objects.filter(
                Q(minimum_info_timestamp__lt=datetime.now().astimezone())
                | Q(minimum_modified_timestamp__lt=datetime.now().astimezone())
            )
            # Modified timestamp is used when brand new information is being imported which should always get priority over updating old information
            # Yes this looks backwards, but the results are correct
            .order_by("minimum_info_timestamp", "minimum_modified_timestamp").first()
        )
        if media:
            if media.type in ["anime", "manga"]:
                print(f"Importing {media.type}: " + media.key)
                # This is not actually required but it keeps Pylance in check
                if media.type == "anime" or media.type == "manga":
                    MyAnimeListMedia.from_simple(
                        media_id=int(media.key), media_type=media.type, sparse_import=False
                    ).import_info(media.minimum_info_timestamp, media.minimum_modified_timestamp)
            elif media.type == "user":
                username = media.key
                print("Importing User: " + username)
                user = MyAnimeListUser(username).import_all(
                    minimum_info_timestamp=media.minimum_info_timestamp,
                    minimum_modified_timestamp=media.minimum_modified_timestamp,
                )
        else:
            # When queue is empty, wait a few seconds before chcking for more entries
            time.sleep(5)
