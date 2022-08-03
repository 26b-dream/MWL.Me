from datetime import time
from typing import Literal, Optional

from pydantic import BaseModel

from common.shared_type_dict import GenericEntry, RelatedMedia, Shared


class Broadcast(BaseModel):
    day_of_the_week: Literal["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "other"]
    start_time: Optional[time]


class StartSeason(BaseModel):
    year: int
    season: Literal["fall", "spring", "summer", "winter"]


class Status(BaseModel):
    watching: int
    completed: int
    on_hold: int
    dropped: int
    plan_to_watch: int


class Statistic(BaseModel):
    status: Status
    num_list_users: int


class AnimeDataClass(Shared):
    media_type: Literal["unknown", "tv", "ova", "movie", "special", "ona", "music"]
    status: Literal["finished_airing", "currently_airing", "not_yet_aired"]
    num_episodes: int

    start_season: Optional[StartSeason]
    source: Optional[
        Literal[
            "other",
            "original",
            "manga",
            "4_koma_manga",
            "web_manga",
            "digital_manga",
            "novel",
            "light_novel",
            "visual_novel",
            "game",
            "card_game",
            "book",
            "picture_book",
            "radio",
            "music",
            # Not listed in the official API documentation
            "mixed_media",
            "web_novel",
        ]
    ]
    average_episode_duration: Optional[int]
    rating: Optional[Literal["g", "pg", "pg_13", "r", "r+", "rx"]]
    studios: list[GenericEntry]

    related_anime: list[RelatedMedia]
    statistics: "Statistic"
    broadcast: Optional[Broadcast] = None
