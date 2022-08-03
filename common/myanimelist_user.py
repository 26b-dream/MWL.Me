from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Callable, Literal, Optional, Type, TypeVar

    MEDIA_TYPES = Literal["anime", "manga"]
    USER_MEDIA_TYPES = TypeVar("USER_MEDIA_TYPES", "UserManga", "UserAnime")

import urllib.request
from datetime import datetime
from functools import cache
from urllib.error import HTTPError

from django.db import transaction

import common.configure_django  # type: ignore # noqa: F401 - Modified global values
from common.constants import DOWNLOADED_FILES_DIR
from common.extended_path import ExtendedPath
from config.config import MyAnimeListSecrets
from main.models import Anime, ImportQue, Manga, User, UserAnime, UserManga


class MyAnimeListUser:
    DOMAIN = "https://myanimelist.net"
    API_DOMAIN = "https://api.myanimelist.net"
    HEADERS = {"X-MAL-CLIENT-ID": MyAnimeListSecrets.CLIENT_ID}
    STATUS_VALUES = {
        "reading": 1,
        "watching": 1,
        "completed": 2,
        "on_hold": 3,
        "dropped": 4,
        "plan_to_read": 5,
        "plan_to_watch": 5,
    }

    def __init__(self, identifier: Optional[str]):
        if isinstance(identifier, str):
            self.username = identifier

        get_or_new_model = User().get_or_new(name=self.username)
        self.model_exists = not get_or_new_model[1]
        self.model = get_or_new_model[0]
        self.anime_scores: list[int] = []
        self.manga_scores: list[int] = []

    @cache
    def partial_anime_json_url(self, offset: int = 0) -> str:
        return f"v2/users/{self.username}/animelist?offset={offset}"

    @cache
    def partial_manga_json_url(self, offset: int = 0) -> str:
        return f"v2/users/{self.username}/mangalist?offset={offset}"

    @cache
    def anime_json_url(self, offset: int = 0) -> str:
        return f"{self.API_DOMAIN}/{self.partial_anime_json_url(offset)}&fields=list_status&limit=1000&nsfw=true"

    @cache
    def manga_json_url(self, offset: int = 0) -> str:
        return f"{self.API_DOMAIN}/{self.partial_manga_json_url(offset)}&fields=list_status&limit=1000&nsfw=true"

    @cache
    def manga_json_path(self, offset: int = 0) -> ExtendedPath:
        return (DOWNLOADED_FILES_DIR / self.partial_manga_json_url(offset).replace("?", "-")).with_suffix(".json")

    @cache
    def anime_json_path(self, offset: int = 0) -> ExtendedPath:
        return (DOWNLOADED_FILES_DIR / self.partial_anime_json_url(offset).replace("?", "-")).with_suffix(".json")

    @cache
    def lazy_json_path(self, type: MEDIA_TYPES, offset: int = 0) -> ExtendedPath:
        if type == "anime":
            return (DOWNLOADED_FILES_DIR / self.partial_anime_json_url(offset).replace("?", "-")).with_suffix(".json")
        else:
            return (DOWNLOADED_FILES_DIR / self.partial_manga_json_url(offset).replace("?", "-")).with_suffix(".json")

    def download_all(self, minimum_timestamp: Optional[datetime] = None) -> None:
        self.download_list(self.anime_json_path, self.anime_json_url, 0, minimum_timestamp)
        self.download_list(self.manga_json_path, self.manga_json_url, 0, minimum_timestamp)

    def download_list(
        self,
        path: Callable[[int], ExtendedPath],
        url: Callable[[int], str],
        offset: int = 0,
        minimum_timestamp: Optional[datetime] = None,
    ) -> None:
        if path(offset).outdated(minimum_timestamp):
            print(f"Downloading: {url(offset)}")
            request = urllib.request.Request(url(offset), headers=self.HEADERS)
            try:
                content = urllib.request.urlopen(request).read()
            except HTTPError as error_msg:
                content = error_msg.read()

            path(offset).write(content)
            # No sleep here because I want users to be able to get instant results as fast as possible

        # Recursively download every page
        if path(offset).parsed_json().get("paging", {}).get("next"):
            self.download_list(path, url, offset + 1000, minimum_timestamp)

    # Make this a transaction to avoid partially imported lists
    @transaction.atomic
    def update_all(
        self, minimum_info_timestamp: Optional[datetime] = None, minimum_modified_timestamp: Optional[datetime] = None
    ) -> None:
        if self.model.information_oudated(minimum_info_timestamp, minimum_modified_timestamp):
            # By default assume lists are private for simplicity
            self.model.anime_list_private = True
            self.model.manga_list_private = True
            self.model.add_timestamps_and_save(self.anime_json_path())

            # If there are no errors downloading the anime list use the information
            if not self.anime_json_path().parsed_json().get("error"):
                UserAnime.objects.filter(user=self.model).delete()
                self.update_single_user_list("anime", UserAnime)

                self.model.anime_list_private = False
                self.model.anime_count = len(self.anime_scores)
                scored_anime = len([x for x in self.anime_scores if x])
                if scored_anime:
                    self.model.average_anime_score = sum(self.anime_scores) / scored_anime
                self.model.last_successful_anime_list_import = self.anime_json_path().aware_mtime()

            # If there are no errors downloading the manga list use the information
            if not self.manga_json_path().parsed_json().get("error"):
                UserManga.objects.filter(user=self.model).delete()
                self.update_single_user_list("manga", UserManga)

                self.model.manga_list_private = False
                self.model.manga_count = len(self.manga_scores)
                scored_manga = len([x for x in self.manga_scores if x])
                if scored_manga:
                    self.model.average_manga_score = sum(self.manga_scores) / scored_manga
                self.model.last_successful_manga_list_import = self.manga_json_path().aware_mtime()

            # TODO: Get timestamp from paginated and manga and find a timestmap between them
            self.model.add_timestamps_and_save(self.anime_json_path())

    def json_media_ids(self, type: MEDIA_TYPES, media_ids: list[int], offset: int = 0) -> list[int]:
        parsed_json = self.lazy_json_path(type, offset).parsed_json()
        for media in parsed_json.get("data", []):
            media_ids.append(media["node"]["id"])

        # Recursively scrape every page
        if parsed_json.get("paging", {}).get("next"):
            self.json_media_ids(type, media_ids, offset + 1000)
        return media_ids

    @cache
    def existing_medias(self, type: MEDIA_TYPES, sparse: bool):
        # Use one query to get all the anime/manga
        media_ids = self.json_media_ids(type, [])
        if type == "anime":
            return Anime.objects.filter(id__in=media_ids, sparse=sparse).values_list("id", flat=True)
        else:
            return Manga.objects.filter(id__in=media_ids, sparse=sparse).values_list("id", flat=True)

    def update_single_user_list(self, type: MEDIA_TYPES, the_class2: Type[USER_MEDIA_TYPES]) -> None:
        offset = 0
        json_path = self.lazy_json_path(type, offset)
        bulk_media: list[USER_MEDIA_TYPES] = []
        bulk_que: list[ImportQue] = []

        while json_path.exists():
            parsed_json = json_path.parsed_json()
            for media in parsed_json["data"]:
                media_id = media["node"]["id"]

                # Update the score counter
                # This does some extra dynamic nonsense just so I don't have to check the media type
                attribute_name = f"{type}_scores"

                # The ugliest way you have every seen to append a list
                getattr(self, attribute_name).append(media["list_status"]["score"])
                setattr(self, attribute_name, getattr(self, attribute_name))

                # If the media already exists in some way use that information
                if media_id in self.existing_medias(type, False) or media_id in self.existing_medias(type, True):
                    bulk_media.append(the_class2(user=self.model, media_id=media["node"]["id"]))

                    # Save the user's list information
                    for key, value in media["list_status"].items():
                        # Convert status to an integer so it takes up less space
                        if key == "status":
                            setattr(bulk_media[-1], key, self.STATUS_VALUES[value])
                        # Leave other values as they are
                        else:
                            setattr(bulk_media[-1], key, value)
                # If the information for an entry on the user's list is not fully imported add it to the queue
                if not media_id in self.existing_medias(type, False):
                    bulk_que.append(
                        ImportQue(
                            type=type,
                            key=media_id,
                            minimum_modified_timestamp=datetime.now().astimezone(),
                            note=f"User list: {self.model}",
                        )
                    )

            offset += 1000
            json_path = self.lazy_json_path(type, offset)

        # TODO: Why does this create a type error?
        the_class2.objects.bulk_create(bulk_media)  # type: ignore

        # Insert new values into the que
        ImportQue.objects.bulk_create(bulk_que, ignore_conflicts=True)

    def import_all(
        self, minimum_info_timestamp: Optional[datetime] = None, minimum_modified_timestamp: Optional[datetime] = None
    ) -> None:
        self.download_all(minimum_info_timestamp)
        self.update_all(minimum_info_timestamp, minimum_modified_timestamp)

        # Once a user's information is update it can be remove from the queue
        ImportQue.objects.filter(type="user", key=self.username).delete()
