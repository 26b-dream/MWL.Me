from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any, Literal, Optional, Type

import random
import time
import urllib.request
from datetime import date, datetime, timedelta
from functools import cache
from urllib.error import HTTPError

import common.extended_re as re
from common.constants import DOWNLOADED_FILES_DIR
from common.extended_path import ExtendedPath
from config.config import MyAnimeListSecrets
from main.models import (
    Anime,
    AnimeRecs,
    AnimeRelatedAnime,
    AnimeRelatedManga,
    ImportQue,
    Manga,
    MangaRecs,
    MangaRelatedAnime,
    MangaRelatedManga,
)


class MyAnimeListMedia:
    DOMAIN = "https://myanimelist.net"
    API_DOMAIN = "https://api.myanimelist.net"
    HEADERS = {"X-MAL-CLIENT-ID": MyAnimeListSecrets.CLIENT_ID}
    SHOW_URL_REGEX = re.compile(
        r"^(?:https:\/\/myanimelist\.net)?\/?(?P<media_type>anime|manga)\/(?P<media_id>\d+?)(?:\/|$)"
    )
    MYSQL_ANIME_FIELDS = [f.name for f in Anime._meta.get_fields()]
    MYSQL_MANGA_FIELDS = [f.name for f in Manga._meta.get_fields()]
    SIMLPE_JSON_MANGA_FIELDS = "id,title,main_picture,alternative_titles,start_date,end_date,synopsis,mean,rank,popularity,num_list_users,num_scoring_users,nsfw,created_at,updated_at,media_type,status,genres,my_list_status,num_volumes,num_chapters,authors{first_name,last_name},pictures,background,related_anime,related_manga,recommendations,serialization{name}"
    SIMLPE_JSON_ANIME_FIELDS = "id,title,main_picture,alternative_titles,start_date,end_date,synopsis,mean,rank,popularity,num_list_users,num_scoring_users,nsfw,created_at,updated_at,media_type,status,genres,my_list_status,num_episodes,start_season,broadcast,source,average_episode_duration,rating,pictures,background,related_anime,related_manga,recommendations,studios,statistics"

    def __init__(
        self,
        url: Optional[str] = None,
        media_type: Optional[Literal["anime", "manga"]] = None,
        media_id: Optional[int] = None,
        media_object: Optional[Anime | Manga] = None,
    ):
        if url:
            regex_search = re.strict_search(self.SHOW_URL_REGEX, url)
            self.media_type = regex_search.group("media_type")
            self.media_id = regex_search.group("media_id")
        elif media_type and media_id:
            self.media_type = media_type
            self.media_id = str(media_id)
        elif media_object:
            self.media_id = str(media_object.id)
            if isinstance(media_object, Anime):
                self.media_type = "anime"
            elif isinstance(media_object, Anime):
                self.media_type = "manga"
        else:
            raise ValueError("No URL, media_type, or anime_object provided")

        if self.media_type == "anime":
            model = Anime().get_or_new(id=self.media_id)
            self.model = model[0]
            self.model_saved = not model[1]
            self.fields = self.MYSQL_ANIME_FIELDS
            self.json_fields = self.SIMLPE_JSON_ANIME_FIELDS
            self.related_anime_model = AnimeRelatedAnime
            self.related_manga_model = AnimeRelatedManga
            self.recommended_model = AnimeRecs
        elif self.media_type == "manga":
            model = Manga().get_or_new(id=self.media_id)
            self.model = model[0]
            self.model_saved = not model[1]
            self.fields = self.MYSQL_MANGA_FIELDS
            self.json_fields = self.SIMLPE_JSON_MANGA_FIELDS
            self.related_anime_model = MangaRelatedAnime
            self.related_manga_model = MangaRelatedManga
            self.recommended_model = MangaRecs
        else:
            raise ValueError(f"Unknown media type: {self.media_type}")

    @cache
    def partial_json_url(self) -> str:
        return f"v2/{self.media_type}/{self.media_id}"

    @cache
    def json_url(self) -> str:
        return f"{self.API_DOMAIN}/{self.partial_json_url()}?fields={self.json_fields}"

    @cache
    def partial_userrecs_html_url(self) -> str:
        return f"{self.media_type}/{self.media_id}/userrecs/userrecs"

    @cache
    def html_url(self) -> str:
        return f"{self.media_type}/{self.media_id}"

    @cache
    def userrecs_html_url(self) -> str:
        return f"{self.DOMAIN}/{self.partial_userrecs_html_url()}"

    @cache
    def json_file_path(self) -> ExtendedPath:
        return (DOWNLOADED_FILES_DIR / self.partial_json_url()).with_suffix(".json")

    @cache
    def userrecs_html_file_path(self) -> ExtendedPath:
        return DOWNLOADED_FILES_DIR / self.media_type / self.media_id / "userrecs.html"

    def sparse_download(self, minimum_timestamp: Optional[datetime] = None) -> None:
        if self.json_file_path().outdated(minimum_timestamp):
            print(f"Downloading: {self.json_url()}")
            request = urllib.request.Request(self.json_url(), headers=self.HEADERS)
            try:
                content = urllib.request.urlopen(request).read()
            except HTTPError as error_msg:
                content = error_msg.read()
            self.json_file_path().write(content)

            time.sleep(1)  # No listed API limits but trying to keep myself safe

    def full_download(self, minimum_timestamp: Optional[datetime] = None) -> None:
        self.sparse_download(minimum_timestamp)
        if self.userrecs_html_file_path().outdated(minimum_timestamp):
            print(f"Downloading: {self.userrecs_html_url()}")
            request = urllib.request.Request(self.userrecs_html_url())
            content = urllib.request.urlopen(request).read()
            self.userrecs_html_file_path().write(content)
            time.sleep(5)  # HTML scraping is sketchy so use sleeps

    def sparse_update(
        self, minimum_info_timestamp: Optional[datetime] = None, minimum_modified_timestamp: Optional[datetime] = None
    ) -> None:
        if not self.model.information_up_to_date(minimum_info_timestamp, minimum_modified_timestamp):
            # If the information was not found just ignore
            if not self.json_file_path().parsed_json().get("error") == "not_found":
                self.recursive_import_info(self.json_file_path().parsed_json())
                self.model.sparse = True
                self.model.add_timestamps_and_save(self.json_file_path())

    def full_update(
        self, minimum_info_timestamp: Optional[datetime] = None, minimum_modified_timestamp: Optional[datetime] = None
    ) -> None:
        # A full udpate is required if the timestamps are outdated or the previous update was sparse
        if (
            not self.model.information_up_to_date(minimum_info_timestamp, minimum_modified_timestamp)
            or self.model.sparse
        ):
            # Make initial value that can be the parent for related/recommendations
            self.sparse_update(minimum_info_timestamp, minimum_modified_timestamp)

            # Update all related & recommended media
            self.update_relationships("anime", self.related_anime_model)
            self.update_relationships("manga", self.related_manga_model)
            self.update_recommendations()

            # Save information
            self.model.sparse = False
            self.model.add_timestamps_and_save(self.json_file_path())

    def add_to_import_que_for_future_updates(self) -> None:
        # Using the media_id as the seed randomly pick a datetime that will be specifically used for this anime to update information
        random.seed(self.media_id)
        offset = random.randrange(31_536_000)  # There are 31,536,00 seconds in a year

        # Get datetime from January 1st of the current year
        next_update_timestamp = datetime(datetime.now().year, 1, 1).astimezone() + timedelta(seconds=offset)

        # If the timestamp is older than the current file move it a year in the future
        if next_update_timestamp < self.model.info_timestamp:
            next_update_timestamp = datetime(datetime.now().year + 1, 1, 1).astimezone() + timedelta(seconds=offset)

        # If the show aired in the past 6 months update it on a fixed monthly schedule
        # This helps compensate for the fact that this information is the most volatile
        if temp_start_date := self.model.start_date:
            # years before 1970 are invalid datetime values for the database so just ignore them
            if self.model.start_date.year > 1970:
                # Convert date to datetime so comparisons can be done
                temp_start_date = datetime.combine(temp_start_date, datetime.min.time()).astimezone()

                # Add 1/12 of the offset so every show updates at a different time
                temp_start_date = temp_start_date + timedelta(seconds=offset / 12)

                if temp_start_date > datetime.now().astimezone() - timedelta(days=(365 / 2)):
                    # Find the next time of the month that is after the previous update
                    while temp_start_date < self.json_file_path().aware_mtime():
                        temp_start_date = temp_start_date + timedelta(days=30)
                    next_update_timestamp = temp_start_date

        ImportQue.objects.update_or_create(
            type=self.media_type,
            key=self.media_id,
            defaults={
                "minimum_info_timestamp": next_update_timestamp,
                "minimum_modified_timestamp": None,  # Information was just imported, this value was used
                "priority": 0,  # Updates always have a low priority because information is already on the database
            },
        )

    # TODO: This type is just made up and does not actually represent the passed values probably
    def recursive_import_info(self, data: dict[str, str | dict[str, Any]], parent_key: str = "") -> None:
        # TODO: Import missing information later
        for key, value in data.items():
            full_key = f"{parent_key}_{key}" if parent_key else key
            if full_key in self.fields:
                if full_key in ["start_date", "end_date"]:
                    # Sometimes dates are just years
                    # For simplicity mark these as January 1st
                    if re.match(re.compile(r"^\d\d\d\d$"), str(value)):
                        setattr(self.model, full_key, date(*[int(x) for x in str(value).split("-")], month=1, day=1))

                    # Sometimes dates are just years and a month
                    # For simplicity mark these as the first of the month
                    elif re.match(re.compile(r"^\d\d\d\d-\d\d$"), str(value)):
                        setattr(self.model, full_key, date(*[int(x) for x in str(value).split("-")], day=1))
                    # Good, complete dates
                    else:
                        setattr(self.model, full_key, date(*[int(x) for x in str(value).split("-")]))
                # Images need to be modified a little bit because there is redundnat information
                # isinstance check is only required for type sanity
                elif full_key.startswith("main_picture") and isinstance(value, str):
                    value = value.removeprefix(f"https://api-cdn.myanimelist.net/images/{self.media_type}/")
                    value = value.removesuffix(".jpg")
                    setattr(self.model, full_key, value)
                else:
                    setattr(self.model, full_key, value)
            elif isinstance(value, dict):
                self.recursive_import_info(value, full_key)
            else:
                print(f"Need to import {full_key}")

    def update_relationships(
        self,
        type: Literal["anime", "manga"],
        model: Type[MangaRelatedAnime | AnimeRelatedManga | AnimeRelatedAnime | MangaRelatedManga],
    ) -> None:
        # Clear out old entries to easily keep data in sync
        relationships_to_import: list[
            MangaRelatedAnime | AnimeRelatedManga | AnimeRelatedAnime | MangaRelatedManga
        ] = []

        model.objects.filter(media_id=self.media_id).delete()
        for related_entry in self.json_file_path().parsed_json()[f"related_{type}"]:
            # Import a sparse version of the related entry if required
            related_media = MyAnimeListMedia(media_type=type, media_id=related_entry["node"]["id"])
            related_media.sparse_import()

            # If the information is fully updated, but the information on this page is newer
            if related_media.model.info_timestamp and related_media.model.info_timestamp < self.model.info_timestamp:
                # Create a relationship that reverses the main entry and the related entry
                # This keeps data as up to date as possible with as little API calls as possible
                if not model.objects.filter(media=related_media.model, related_media=self.model).first():
                    relationships_to_import.append(
                        model(
                            media=related_media.model,
                            related_media=self.model,
                            # TODO: Make this string actually make sense
                            # TODO: Temporarily using the "Opposite of" to find an example of this working
                            relationship=f"Opposite of {related_entry['relation_type_formatted']}",
                        )
                    )

            # Import the relationship
            if not related_media.json_file_path().parsed_json().get("error") == "not_found":
                relationships_to_import.append(
                    model(
                        media=self.model,
                        related_media=related_media.model,
                        relationship=related_entry["relation_type_formatted"],
                    )
                )
        model.objects.bulk_create(relationships_to_import)  # type: ignore

    def update_recommendations(self) -> None:
        recs_to_import: list[AnimeRecs | MangaRecs] = []

        parsed_html = self.userrecs_html_file_path().parsed_html()
        for related in parsed_html.select("div[class='picSurround']"):
            # Sparsely import recommended entries
            url = related.strict_select_one("a").attrs["href"]
            recommended_media = MyAnimeListMedia(url)
            recommended_media.sparse_import()

            # If the information is fully updated, but the information on this page is newer
            if (
                recommended_media.model.sparse == False
                and recommended_media.model.info_timestamp < self.model.info_timestamp
            ):
                # Create a recommendation that reverses the main entry and the recommended entry
                # This keeps data as up to date as possible with as little API calls as possible
                parent = related.strict_parent().strict_parent()
                recommendations = len(parent.strict_select("div[class='spaceit_pad detail-user-recs-text']"))
                recs_to_import.append(
                    self.recommended_model(
                        media=recommended_media.model,
                        recommended_media=self.model,
                        recommendations=recommendations,
                    )
                )
            # Import the relationship
            parent = related.strict_parent().strict_parent()
            recommendations = len(parent.strict_select("div[class='spaceit_pad detail-user-recs-text']"))
            recs_to_import.append(
                self.recommended_model(
                    media=self.model,
                    recommended_media=recommended_media.model,
                    recommendations=recommendations,
                )
            )
        # TODO: Fix this type error
        self.recommended_model.objects.bulk_create(recs_to_import, ignore_conflicts=True)  # type: ignore

    def sparse_import(
        self, minimum_timestamp: Optional[datetime] = None, minimum_modified_timestamp: Optional[datetime] = None
    ) -> None:
        if self.model.information_oudated(minimum_timestamp, minimum_modified_timestamp):
            self.sparse_download(minimum_timestamp)
            self.sparse_update(minimum_timestamp, minimum_modified_timestamp)

    def full_import(
        self, minimum_info_timestamp: Optional[datetime] = None, minimum_modified_timestamp: Optional[datetime] = None
    ) -> None:
        if self.model.information_oudated(minimum_info_timestamp, minimum_modified_timestamp) or self.model.sparse:
            self.full_download(minimum_info_timestamp)
            self.full_update(minimum_info_timestamp, minimum_modified_timestamp)
        self.add_to_import_que_for_future_updates()
