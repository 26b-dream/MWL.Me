from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from django.db.models.query import QuerySet
    from typing_extensions import Self
    from typing import Any

import inspect

from django.db import models

import common.extended_re as re
from common.model_helper import GetOrNew
from common.model_templates import ModelWithIdAndTimestamp


# This is kinda sketch because it relies on stack inspection
def lazy_db_table() -> str:

    # Trying to add a little bit of safety to this sketchy code
    # This part of the stack should always be Meta
    if inspect.stack()[1][3] != "Meta":
        raise ValueError("sketchy_lazy_namer has lived up to it's name and somethign went wrong")

    original_class_name = inspect.stack()[2][3]
    # Regex is beautiful, this converts CamelCase to snake_case
    snake_case_class_name = re.sub(r"(?<!^)(?=[A-Z])", "_", original_class_name).lower()
    return snake_case_class_name


# This is kinda sketch because it relies on stack inspection
def lazy_unique(*fields: str) -> list[models.UniqueConstraint]:
    # Trying to add a little bit of safety to this sketchy code
    # This part of the stack should always be Meta
    if inspect.stack()[1][3] != "Meta":
        raise ValueError("sketchy_lazy_namer has lived up to it's name and somethign went wrong")

    return [models.UniqueConstraint(fields=fields, name=f"{inspect.stack()[2][3]}_{'_'.join(fields)}")]


# This is extra sketch because it relies on stack inspection and it has no extra checks
# TODO: Types on these variables, need to figure out what values are normally accepted
def lazy_fk(fk_model: Any, on_delete: Any = models.CASCADE) -> models.ForeignKey[Any]:
    # The stated return type does not match with the actual value so ignore the type error
    key_name = inspect.stack()[1][4][0].strip().split(" =")[0]  # type ignore
    main_model = inspect.stack()[1][3]
    related_name = f"{main_model}_{fk_model.__name__}_{key_name}"

    return models.ForeignKey(fk_model, on_delete=models.CASCADE, related_name=related_name)


class User(ModelWithIdAndTimestamp, GetOrNew):  # type: ignore - Composing abstract models always throws type errors
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta always throws type errors
        db_table = lazy_db_table()

    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=255, unique=True)
    anime_count = models.PositiveSmallIntegerField(null=True)
    manga_count = models.PositiveSmallIntegerField(null=True)
    average_anime_score = models.FloatField(null=True)
    average_manga_score = models.FloatField(null=True)
    anime_list_private = models.BooleanField()
    manga_list_private = models.BooleanField()
    last_successful_anime_list_import = models.DateTimeField(null=True)
    last_successful_manga_list_import = models.DateTimeField(null=True)

    def user_anime(self) -> QuerySet[UserAnime]:
        return UserAnime.objects.filter(user=self, media__sparse=False)

    def user_manga(self) -> QuerySet[UserManga]:
        return UserManga.objects.filter(user=self)


# This is sharedb etween anime and manga
class Genres(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta always throws type errors
        db_table = lazy_db_table()

    id = models.PositiveSmallIntegerField(primary_key=True)
    name = models.CharField(max_length=255)


class Media(ModelWithIdAndTimestamp, GetOrNew):  # type: ignore - Composing abstract models always throws type errors
    class Meta:  # type: ignore - Meta class always throws type errors
        abstract = True

    id = models.PositiveSmallIntegerField(primary_key=True)
    title = models.CharField(max_length=255)
    main_picture_medium = models.CharField(max_length=255)
    main_picture_large = models.CharField(max_length=255)
    start_date = models.DateField(null=True)
    end_date = models.DateField(null=True)
    synopsis = models.TextField()
    mean = models.FloatField(null=True)
    rank = models.PositiveSmallIntegerField(null=True)
    popularity = models.PositiveSmallIntegerField()
    num_list_users = models.PositiveSmallIntegerField()
    num_scoring_users = models.PositiveSmallIntegerField()
    nsfw = models.CharField(max_length=255)
    created_at = models.DateTimeField()
    updated_at = models.DateTimeField()
    media_type = models.CharField(max_length=255)
    status = models.CharField(max_length=255)
    background = models.TextField()
    sparse = models.BooleanField()

    def __str__(self) -> str:
        return self.title


class Anime(Media):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta always throws type errors
        db_table = lazy_db_table()

    num_episodes = models.PositiveSmallIntegerField()
    start_season_year = models.PositiveSmallIntegerField(null=True)
    start_season_season = models.CharField(max_length=255)
    broadcast_day_of_the_week = models.CharField(max_length=255)
    broadcast_start_time = models.TimeField(null=True)
    source = models.CharField(max_length=255)
    average_episode_duration = models.PositiveSmallIntegerField()
    rating = models.CharField(max_length=255)


class Manga(Media):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta always throws type errors
        db_table = lazy_db_table()

    alternative_titles_en_title = models.CharField(max_length=255)
    alternative_titles_ja_title = models.CharField(max_length=255)
    num_volumes = models.PositiveSmallIntegerField()
    num_chapters = models.PositiveSmallIntegerField()


class RelatedAnime(models.Model):
    class Meta:  # type: ignore - Meta class always throws type errors
        abstract = True

    id = models.AutoField(primary_key=True)
    relationship = models.CharField(max_length=255)

    # Abstract attributes to avoid type errors
    media: models.ForeignKey[Anime]
    related_media: models.ForeignKey[Anime]

    def __str__(self) -> str:
        return f"{self.media} {self.related_media} {self.relationship}"


class AnimeRelatedAnime(RelatedAnime):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("media", "related_media", "relationship")

    media = lazy_fk(Anime)
    related_media = lazy_fk(Anime)


class AnimeRelatedManga(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("media", "related_media", "relationship")

    id = models.AutoField(primary_key=True)
    media = lazy_fk(Anime)
    related_media = lazy_fk(Manga)
    relationship = models.CharField(max_length=255)


class MangaRelatedAnime(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("media", "related_media", "relationship")

    def __str__(self) -> str:
        return f"{self.media} {self.related_media} {self.relationship}"

    id = models.AutoField(primary_key=True)
    media = lazy_fk(Manga)
    related_media = lazy_fk(Anime)
    relationship = models.CharField(max_length=255)


class MangaRelatedManga(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("media", "related_media", "relationship")

    id = models.AutoField(primary_key=True)
    media = lazy_fk(Manga)
    related_media = lazy_fk(Manga)
    relationship = models.CharField(max_length=255)

    def __str__(self) -> str:
        return f"{self.media} {self.related_media} {self.relationship}"


class AnimeRecs(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("media", "recommended_media")

    id = models.AutoField(primary_key=True)
    media = lazy_fk(Anime)
    recommended_media = lazy_fk(Anime)
    recommendations = models.PositiveSmallIntegerField()


class MangaRecs(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("media", "recommended_media")

    id = models.AutoField(primary_key=True)
    media = lazy_fk(Manga)
    recommended_media = lazy_fk(Manga)
    recommendations = models.PositiveSmallIntegerField()


class AnimeAlternativeTitles(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta always throws type errors
        db_table = lazy_db_table()

    anime = models.ForeignKey(Anime, on_delete=models.CASCADE)
    title = models.CharField(max_length=255)


class AnimeGenres(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta always throws type errors
        db_table = lazy_db_table()

    anime = models.ForeignKey(Anime, on_delete=models.CASCADE)
    genre = models.ForeignKey(Genres, on_delete=models.CASCADE)


class UserMedia(GetOrNew):
    class Meta:  # type: ignore - Meta class always throws type errors
        abstract = True

    objects: QuerySet[Self]
    id = models.AutoField(primary_key=True)
    status = models.PositiveSmallIntegerField()
    score = models.PositiveSmallIntegerField()
    updated_at = models.DateTimeField()
    finish_date = models.DateField(null=True)


class UserAnime(UserMedia):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("user", "media")

    user = lazy_fk(User)
    media = lazy_fk(Anime)
    num_episodes_watched = models.PositiveSmallIntegerField(null=True)
    is_rewatching = models.BooleanField()


class UserManga(UserMedia):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("user", "media")

    user = lazy_fk(User)
    media = lazy_fk(Manga)
    is_rereading = models.BooleanField()
    num_volumes_read = models.PositiveSmallIntegerField()
    num_chapters_read = models.PositiveSmallIntegerField()


class ImportQue(models.Model):
    objects: QuerySet[Self]

    class Meta:  # type: ignore - Meta class always throws type errors
        db_table = lazy_db_table()
        constraints = lazy_unique("type", "key")

    id = models.AutoField(primary_key=True)
    type = models.CharField(max_length=255, null=False)
    key = models.CharField(max_length=255, null=False)
    priority = models.PositiveSmallIntegerField()
    minimum_info_timestamp = models.DateTimeField(null=True)
    minimum_modified_timestamp = models.DateTimeField(null=True)
