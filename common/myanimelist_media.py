from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Literal, Optional, Type, TypeVar, Union

    GENRE_TYPEVAR = TypeVar("GENRE_TYPEVAR", bound=Union["AnimeGenres", "MangaGenres"])
    PICTURES_TYPEVAR = TypeVar("PICTURES_TYPEVAR", bound=Union["AnimePictures", "MangaPictures"])
    SUPER_GENERIC = TypeVar("SUPER_GENERIC")
    RECS_TYPEVAR = TypeVar("RECS_TYPEVAR", bound=Union["AnimeRecs", "MangaRecs"])
    IMAGE_TYPEVAR = TypeVar("IMAGE_TYPEVAR", bound=Union[str, None])
    from typing_extensions import Self

import random
import time
import urllib.request
from abc import abstractmethod
from datetime import date, datetime, timedelta
from functools import cache
from urllib.error import HTTPError

from django.db import transaction

import common.extended_re as re
from common.anime_typed_dict import AnimeDataClass
from common.constants import DOWNLOADED_FILES_DIR
from common.extended_path import ExtendedPath
from common.manga_typed_dict import MangaDataClass
from common.shared_type_dict import (
    AlternativeTitle,
    GenericEntry,
    Picture,
    Recommendation,
    RelatedMedia,
)
from config.config import MyAnimeListSecrets
from main.models import (
    Anime,
    AnimeGenreList,
    AnimeGenres,
    AnimePictures,
    AnimeRecs,
    AnimeRelatedAnime,
    AnimeRelatedManga,
    AnimeStudios,
    AnimeSynonyms,
    ImportQue,
    Manga,
    MangaGenreList,
    MangaGenres,
    MangaPictures,
    MangaRecs,
    MangaRelatedAnime,
    MangaRelatedManga,
    MangaSynonyms,
    Studio,
)


class MyAnimeListMedia:
    # Abstract constants
    FIELDS: list[str]
    MEDIA_TYPE: Literal["anime", "manga"]
    JSON_FIELDS: str
    GENRES_MODEL: Type[MangaGenres | AnimeGenres]
    GENRES_LIST_MODEL: Type[MangaGenreList | AnimeGenreList]
    RELATED_ANIME_MODEL: Type[AnimeRelatedAnime | MangaRelatedAnime]
    RELATED_MANGA_MODEL: Type[MangaRelatedManga | AnimeRelatedManga]
    PICTURES_MODEL: Type[MangaPictures | AnimePictures]
    REC_MODEL: Type[AnimeRecs | MangaRecs]
    SYNONYMS_MODEL: Type[AnimeSynonyms | MangaSynonyms]
    MODEL: Type[Anime | Manga]

    # Abstract instance variables
    media_id: int
    db_object: Anime | Manga
    sparse_import: bool

    # Actual constants
    DOMAIN = "https://myanimelist.net"
    API_DOMAIN = "https://api.myanimelist.net"
    HEADERS = {"X-MAL-CLIENT-ID": MyAnimeListSecrets.CLIENT_ID}
    URL_REGEX = re.compile(
        r"^(?:https:\/\/myanimelist\.net)?\/?(?P<media_type>anime|manga)\/(?P<media_id>\d+?)(?:\/|$)"
    )

    @classmethod
    def from_url(cls, url: str, sparse_import: bool) -> Self:
        regex_search = re.strict_search(cls.URL_REGEX, url)
        media_type = str(regex_search.group("media_type"))
        media_id = int(regex_search.group("media_id"))

        if media_type == "anime":
            return MyAnimeListAnime(media_id, sparse_import)
        elif media_type == "manga":
            return MyAnimeListManga(media_id, sparse_import)
        # This should be impossible, but it guarantees type safety
        else:
            raise ValueError(f"Invalid media type from URL: {url}\nMedia type detected as {media_type}")

    @classmethod
    def from_object(cls, object: Anime | Manga, sparse_import: bool) -> Self:
        if isinstance(object, Anime):
            return MyAnimeListManga(object.id, sparse_import)
        elif isinstance(object, Anime):
            return MyAnimeListAnime(object.id, sparse_import)
        # This should be impossible, but it guarantees type safety
        else:
            raise ValueError(f"Invalid media type from object {object}: {type(object)}")

    @classmethod
    def from_simple(cls, media_type: Literal["anime", "manga"], media_id: int, sparse_import: bool) -> Self:
        if media_type == "manga":
            return MyAnimeListManga(media_id, sparse_import)
        else:
            return MyAnimeListAnime(media_id, sparse_import)

    @abstractmethod
    def json_file_parsed(self) -> AnimeDataClass | MangaDataClass:
        ...

    @cache
    def html_url(self) -> str:
        return f"{self.MEDIA_TYPE}/{self.media_id}"

    @cache
    def partial_userrecs_html_url(self) -> str:
        return f"{self.html_url()}/userrecs/userrecs"

    @cache
    def userrecs_html_url(self) -> str:
        return f"{self.DOMAIN}/{self.partial_userrecs_html_url()}"

    @cache
    def userrecs_html_file_path(self) -> ExtendedPath:
        return DOWNLOADED_FILES_DIR / self.MEDIA_TYPE / str(self.media_id) / "userrecs.html"

    @cache
    def partial_json_url(self) -> str:
        return f"v2/{self.MEDIA_TYPE}/{self.media_id}"

    @cache
    def json_url(self) -> str:
        return f"{self.API_DOMAIN}/{self.partial_json_url()}?fields={self.JSON_FIELDS}"

    @cache
    def json_file_is_valid(self) -> bool:
        # not_found is the only error message I have seen so just check for that
        return not self.json_file_path().parsed_json().get("error") == "not_found"

    @cache
    def json_file_path(self) -> ExtendedPath:
        return (DOWNLOADED_FILES_DIR / self.partial_json_url()).with_suffix(".json")

    @cache
    def userrecs_on_html(self) -> bool:
        return len(self.json_file_path().parsed_json()["recommendations"]) == 10

    def full_download(self, minimum_timestamp: Optional[datetime] = None) -> None:
        # Check if the file needs downloading according to database information
        if self.db_object.information_oudated(minimum_timestamp):
            # Check if file needs downloading according to file information
            if self.json_file_path().outdated(minimum_timestamp):
                print(f"Downloading: {self.json_url()}")
                request = urllib.request.Request(self.json_url(), headers=self.HEADERS)
                try:
                    content = urllib.request.urlopen(request).read()
                except HTTPError as error_msg:
                    content = error_msg.read()
                self.json_file_path().write(content)

                time.sleep(1)  # No listed API limits but trying to keep myself safe
        # Check if the file needs downloading according to database information
        # self.db_object.sparse may be None or False
        if self.db_object.information_oudated(minimum_timestamp) or self.db_object.sparse:
            # Check if file needs downloading according to file information
            if (
                not self.sparse_import
                and self.userrecs_on_html()
                and self.userrecs_html_file_path().outdated(minimum_timestamp)
            ):
                print(f"Downloading: {self.userrecs_html_url()}")
                request = urllib.request.Request(self.userrecs_html_url())
                content = urllib.request.urlopen(request).read()
                self.userrecs_html_file_path().write(content)
                time.sleep(5)  # HTML scraping is sketchy so sleep for 5 seconds

    def get_oldest_file(self) -> ExtendedPath:
        # These are all the files used for importing information
        files = [self.json_file_path(), self.userrecs_html_file_path()]

        # Remove files that do not exist from list
        files = [file for file in files if file.exists()]

        # Find the oldest file
        return min(files, key=lambda file: file.aware_mtime())

    @transaction.atomic
    def update(
        self,
        minimum_info_timestamp: Optional[datetime] = None,
        minimum_modified_timestamp: Optional[datetime] = None,
    ) -> None:
        # Update information if it is outdated or a full import is being done on a sparse database entry
        if self.db_object.information_oudated(minimum_info_timestamp, minimum_modified_timestamp) or (
            self.sparse_import == False and self.db_object.sparse
        ):
            # Only attempt to import information on valid JSON files
            if self.json_file_is_valid():
                # Add timestamps first for easier comparisons later on
                self.db_object.add_timestamps(self.get_oldest_file())

                self.simple_import()
                self.db_object.sparse = self.sparse_import

                # Save information now so all of the child information has a foriegn key
                self.db_object.add_timestamps_and_save(self.json_file_path())

    def date_within(self, date: Optional[datetime], delta: timedelta) -> bool:
        if date is None:
            return False
        return date + delta > datetime.now()

    def add_to_import_quees(self) -> None:
        note = "Yearly update"
        # Using the media_id as the seed randomly pick a datetime that will be specifically used for this anime to update information
        random.seed(self.media_id)
        offset = random.randrange(31_536_000)  # There are 31,536,00 seconds in a year

        # If there is no airing date do a best guess based on other information
        if self.db_object.start_date is None:
            # If the information was changed on the website within the last 6 months update it on a monthly schedule
            if (self.db_object.updated_at + timedelta(days=180)) > self.db_object.info_timestamp:
                update_frequency = 30
                note = "Monthly update, unknown start date"
            # If the information hasn't changed in the last 6 months just go back to yearly
            else:
                update_frequency = 365
                note = "Yearly update, unknown start date"
        # If there is an airing date use that to determine the update frequency
        else:
            # If the date was before 1971 only update it yearly
            # This is done to make sure every datetime created is valid because dates before 1970 are invalid
            if self.db_object.start_date < date(1971, 1, 1):
                update_frequency = 365
                note = "Yearly update, unknown start date"
            else:
                start_as_datetime = datetime.combine(self.db_object.start_date, datetime.min.time()).astimezone()
                # If the show started airing within the lasy 6 months update the value monthly
                if start_as_datetime + timedelta(days=180) > self.db_object.info_timestamp:
                    update_frequency = 30
                    note = "Monthly update, recently aired"
                # All other shows update once per year
                else:
                    update_frequency = 365
                    note = "Yearly update, not recently aired"

        # Grab the first date of the year from a year ago
        update_date = datetime(datetime.now().year - 1, 1, 1).astimezone()

        # Apply the offset
        update_date += timedelta(seconds=offset)

        # Increment date until it is after the current file's timestamp
        while update_date < self.db_object.info_timestamp:
            update_date += timedelta(days=update_frequency)

        if not self.sparse_import:
            ImportQue.objects.update_or_create(
                type=self.MEDIA_TYPE,
                key=self.media_id,
                defaults={
                    "minimum_info_timestamp": update_date,
                    "minimum_modified_timestamp": None,  # Information was just imported, this value was used
                    "note": note,
                },
            )

    def parse_date(self, date_string: Optional[str]) -> Optional[date]:
        if date_string is None:
            return None
        # Sometimes dates are just years
        # For simplicity mark these as January 1st
        if re.match(re.compile(r"^\d\d\d\d$"), date_string):
            return date(*[int(x) for x in date_string.split("-")], month=1, day=1)

        # Sometimes dates are just years and a month
        # For simplicity mark these as the first of the month
        elif re.match(re.compile(r"^\d\d\d\d-\d\d$"), date_string):
            return date(*[int(x) for x in date_string.split("-")], day=1)

        # Good, complete dates
        else:
            return date(*[int(x) for x in date_string.split("-")])

    def simple_import(self) -> None:
        json = self.json_file_parsed()

        # I could hand wave all this away with setattr and getattr
        # Doing it this way garuntees more type safety
        self.db_object.id = json.id_
        self.db_object.title = json.title
        if json.main_picture:
            self.db_object.main_picture_medium = self.image_cleaner(json.main_picture.medium)
            self.db_object.main_picture_large = self.image_cleaner(json.main_picture.large)
        if json.alternative_titles:
            self.import_alternative_titles_synonyms(json.alternative_titles)

        self.db_object.start_date = self.parse_date(json.start_date)
        self.db_object.end_date = self.parse_date(json.end_date)
        self.db_object.synopsis = json.synopsis
        self.db_object.mean = json.mean
        self.db_object.rank = json.rank
        self.db_object.popularity = json.popularity
        self.db_object.num_list_users = json.num_list_users
        self.db_object.num_scoring_users = json.num_scoring_users
        self.db_object.nsfw = json.nsfw
        self.import_genres(json.genres)
        self.db_object.created_at = json.created_at
        self.db_object.updated_at = json.updated_at
        self.db_object.media_type = json.media_type
        self.db_object.status = json.status
        self.import_pictures(json.pictures)
        self.db_object.background = json.background

        if not self.sparse_import:
            self.import_recommendations(json.recommendations)

        if isinstance(self.db_object, Anime) and isinstance(json, AnimeDataClass):
            self.db_object.num_episodes = json.num_episodes
            if json.start_season:
                self.db_object.start_season_year = json.start_season.year
                self.db_object.start_season_season = json.start_season.season
            if json.broadcast:
                self.db_object.broadcast_day_of_the_week = json.broadcast.day_of_the_week
                self.db_object.broadcast_start_time = json.broadcast.start_time
            self.db_object.source = json.source
            self.db_object.average_episode_duration = json.average_episode_duration
            self.db_object.rating = json.rating
            self.import_studios(json.studios)

            self.db_object.statistics_status_watching = json.statistics.status.watching
            self.db_object.statistics_status_completed = json.statistics.status.completed
            self.db_object.statistics_status_on_hold = json.statistics.status.on_hold
            self.db_object.statistics_status_dropped = json.statistics.status.dropped
            self.db_object.statistics_status_plan_to_watch = json.statistics.status.plan_to_watch
            self.db_object.statistics_num_list_users = json.statistics.num_list_users

            if not self.sparse_import:
                self.update_relationships("anime", AnimeRelatedAnime, json.related_anime)
        elif isinstance(self.db_object, Manga) and isinstance(json, MangaDataClass):
            self.db_object.num_volumes = json.num_volumes
            self.db_object.num_chapters = json.num_chapters
            # TODO: json.authors
            if not self.sparse_import:
                self.update_relationships("manga", MangaRelatedManga, json.related_manga)
            # TODO: json.serialization

    def image_cleaner(self, url: IMAGE_TYPEVAR) -> IMAGE_TYPEVAR:
        if isinstance(url, str):
            url = url.removeprefix(f"https://api-cdn.myanimelist.net/images/{self.MEDIA_TYPE}/").removesuffix(".jpg")

        return url

    def import_pictures(self, value: list[Picture]) -> None:
        # TODO: Find a way to simplify this while still being type safe
        if self.PICTURES_MODEL == MangaPictures:
            bulk = [
                self.PICTURES_MODEL(
                    media_id=self.media_id, large=self.image_cleaner(x.large), medium=self.image_cleaner(x.medium)
                )
                for x in value
            ]
            # Delete old entries and import new ones
            self.PICTURES_MODEL.objects.filter(media_id=self.media_id).delete()
            self.PICTURES_MODEL.objects.bulk_create(bulk)  # type: ignore - This is type safe

    def import_genres(self, value: Optional[list[GenericEntry]]) -> None:
        if value:
            bulk = [
                self.GENRES_MODEL(
                    media_id=self.media_id,
                    genre=self.GENRES_LIST_MODEL.objects.get_or_create(id=x.id_, name=x.name)[0],
                )
                for x in value
            ]
            self.GENRES_MODEL.objects.filter(media_id=self.media_id).delete()
            self.GENRES_MODEL.objects.bulk_create(bulk)  # type: ignore - This is type safe

    def import_studios(self, value: list[GenericEntry]) -> None:
        bulk = [
            AnimeStudios(
                media_id=self.media_id,
                studio=Studio.objects.get_or_create(id=x.id_, name=x.name)[0],
            )
            for x in value
        ]

        # Delete old entries and import new ones
        AnimeStudios.objects.filter(media_id=self.media_id).delete()
        AnimeStudios.objects.bulk_create(bulk)

    def import_alternative_titles_synonyms(self, value: AlternativeTitle) -> None:
        bulk = [self.SYNONYMS_MODEL(media_id=self.media_id, synonym=x) for x in value.synonyms]
        # Delete old entries and import new ones
        self.SYNONYMS_MODEL.objects.filter(media_id=self.media_id).delete()
        self.SYNONYMS_MODEL.objects.bulk_create(bulk)  # type: ignore - This is type safe

    def update_relationships(
        self,
        type: Literal["anime", "manga"],
        model: Type[MangaRelatedAnime | AnimeRelatedManga | AnimeRelatedAnime | MangaRelatedManga],
        value: list[RelatedMedia],
    ) -> None:
        relationships_to_import: list[
            MangaRelatedAnime | AnimeRelatedManga | AnimeRelatedAnime | MangaRelatedManga
        ] = []

        # Clear out old entries to easily keep data in sync
        model.objects.filter(media_id=self.media_id).delete()
        for related_entry in value:
            # Import a sparse version of the related entry if required
            related_media = MyAnimeListMedia.from_simple(
                media_type=type, media_id=related_entry.node.id_, sparse_import=True
            )
            related_media.import_info()

            # If the information is fully updated, but the information on this page is newer
            if (
                related_media.db_object.sparse == False
                and related_media.db_object.info_timestamp
                and related_media.db_object.info_timestamp < self.db_object.info_timestamp
            ):
                # Check if this reference is on the other page
                if not model.objects.filter(media=related_media.db_object, related_media=self.db_object).exists():
                    # Some entries on MAL only show relationships in one direction for some reason
                    # Backdate the import queue by one hour to avoid forever downloading 2 pages
                    # Technically this can cause missing information but the likelyhood is very low
                    ImportQue.objects.filter(key=related_media.db_object.id, type=self.MEDIA_TYPE).update(
                        minimum_info_timestamp=self.db_object.info_timestamp - timedelta(hours=1),
                        note=f"Relationships: {self.db_object}",
                    )

            # Import the relationship
            relationships_to_import.append(
                model(
                    media=self.db_object,
                    related_media=related_media.db_object,
                    relationship=related_entry.relation_type_formatted,
                )
            )
        model.objects.bulk_create(relationships_to_import)  # type: ignore - This is type safe

    def import_recommendations(self, value: list[Recommendation]) -> None:
        bulk: list[AnimeRecs | MangaRecs] = []

        if self.userrecs_on_html():
            parsed_html = self.userrecs_html_file_path().parsed_html()
            for related in parsed_html.select("div[class='picSurround']"):
                # Sparsely import recommended entries
                url = related.strict_select_one("a").attrs["href"]
                recommended_media = MyAnimeListMedia.from_url(url, sparse_import=True)
                recommended_media.import_info()

                parent = related.strict_parent().strict_parent()
                rec_count = len(parent.strict_select("div[class='spaceit_pad detail-user-recs-text']"))

                bulk += self.compile_rec_info(recommended_media, rec_count)

        else:
            for rec in value:
                # Sparsely import recommended entries
                # Just ignore the type because I am passing a dictinary straight from the json file
                recommended_media = MyAnimeListMedia.from_simple(self.MEDIA_TYPE, rec.node.id_, sparse_import=True)
                recommended_media.import_info()

                # Just ignore the type because I am passing a dictinary straight from the json file
                bulk += self.compile_rec_info(recommended_media, rec.num_recommendations)

        self.REC_MODEL.objects.bulk_create(bulk, ignore_conflicts=True)  # type: ignore - This is type safe

    def compile_rec_info(self, rec: MyAnimeListMedia, recommendations: int) -> list[AnimeRecs | MangaRecs]:
        bulk: list[AnimeRecs | MangaRecs] = []
        bulk.append(
            self.REC_MODEL(media=self.db_object, recommended_media=rec.db_object, recommendations=recommendations)
        )

        # If the information is fully updated, but the information on this page is newer
        if rec.db_object.sparse == False and rec.db_object.info_timestamp < self.db_object.info_timestamp:
            # If the data does not match update the other value
            if not self.REC_MODEL.objects.filter(
                media=rec.db_object, recommended_media=self.db_object, recommendations=recommendations
            ).exists():

                # This information probably does not need to be backdated one hour because it seems like it is always in sync
                # Just in case though, backdate it one hour to match the strategy used for relationships
                ImportQue.objects.filter(key=rec.db_object.id, type=self.MEDIA_TYPE).update(
                    minimum_info_timestamp=self.db_object.info_timestamp - timedelta(hours=1),
                    note=f"Recommendations: {self.db_object}",
                )

        return bulk

    def import_info(
        self,
        minimum_info_timestamp: Optional[datetime] = None,
        minimum_modified_timestamp: Optional[datetime] = None,
    ) -> None:
        # If the value is outdated it needs to be updated
        if self.db_object.information_oudated(minimum_info_timestamp, minimum_modified_timestamp):
            self.full_download(minimum_info_timestamp)
            self.update(minimum_info_timestamp, minimum_modified_timestamp)
        # If a full import is being run on a sparse entry do it needs to be updated
        elif not self.sparse_import and self.db_object.sparse:
            self.full_download(minimum_info_timestamp)
            self.update(minimum_info_timestamp, minimum_modified_timestamp)
        self.add_to_import_quees()


class MyAnimeListAnime(MyAnimeListMedia):
    def __init__(self, media_id: int, sparse_import: bool):
        self.media_id = media_id
        self.db_object = Anime().get_or_new(id=self.media_id)[0]
        self.sparse_import = sparse_import

    @cache  # type: ignore
    def json_file_parsed(self) -> AnimeDataClass:
        return AnimeDataClass(**self.json_file_path().parsed_json())

    FIELDS = [f.name for f in Anime._meta.get_fields()]
    JSON_FIELDS = "id,title,main_picture,alternative_titles,start_date,end_date,synopsis,mean,rank,popularity,num_list_users,num_scoring_users,nsfw,created_at,updated_at,media_type,status,genres,my_list_status,num_episodes,start_season,broadcast,source,average_episode_duration,rating,pictures,background,related_anime,related_manga,recommendations,studios,statistics"
    RELATED_ANIME_MODEL = AnimeRelatedAnime
    RELATED_MANGA_MODEL = AnimeRelatedManga
    REC_MODEL = AnimeRecs
    GENRES_MODEL = AnimeGenres
    GENRES_LIST_MODEL = AnimeGenreList
    PICTURES_MODEL = AnimePictures
    MEDIA_TYPE = "anime"
    SYNONYMS_MODEL = AnimeSynonyms


class MyAnimeListManga(MyAnimeListMedia):
    def __init__(self, media_id: int, sparse_import: bool):
        self.media_id = media_id
        self.db_object = Manga().get_or_new(id=self.media_id)[0]
        self.sparse_import = sparse_import

    @cache  # type: ignore - Caching abstract functions causes issues
    def json_file_parsed(self) -> MangaDataClass:
        return MangaDataClass(**self.json_file_path().parsed_json())

    FIELDS = [f.name for f in Manga._meta.get_fields()]
    JSON_FIELDS = "id,title,main_picture,alternative_titles,start_date,end_date,synopsis,mean,rank,popularity,num_list_users,num_scoring_users,nsfw,created_at,updated_at,media_type,status,genres,my_list_status,num_volumes,num_chapters,authors{first_name,last_name},pictures,background,related_anime,related_manga,recommendations,serialization{name}"
    RELATED_ANIME_MODEL = MangaRelatedAnime
    RELATED_MANGA_MODEL = MangaRelatedManga
    REC_MODEL = MangaRecs
    GENRES_MODEL = MangaGenres
    GENRES_LIST_MODEL = MangaGenreList
    PICTURES_MODEL = MangaPictures
    MEDIA_TYPE = "manga"
    SYNONYMS_MODEL = MangaSynonyms
