from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field


class AlternativeTitle(BaseModel):
    synonyms: list[str]
    en: str
    ja: str


class Picture(BaseModel):
    medium: str
    large: Optional[str]


class Node(BaseModel):
    id_: int = Field(..., alias="id")
    title: str
    main_picture: Optional[Picture]


class Recommendation(BaseModel):
    node: Node
    num_recommendations: int


class GenericEntry(BaseModel):
    id_: int = Field(..., alias="id")
    name: str


class RelatedMedia(BaseModel):
    node: Node
    relation_type: Literal[
        "sequel",
        "prequel",
        "alternative_setting",
        "alternative_version",
        "side_story",
        "parent_story",
        "summary",
        "full_story",
        # Not listed in the official API documentation
        "character",
        "other",
        "spin_off",
    ]
    relation_type_formatted: Literal[
        "Sequel",
        "Prequel",
        "Alternative setting",
        "Alternative version",
        "Side story",
        "Parent story",
        "Summary",
        "Full story",
        # Not listed in the official API documentation
        "Character",
        "Other",
        "Spin-off",
    ]


class Shared(BaseModel):
    id_: int = Field(..., alias="id")
    title: str
    main_picture: Optional[Picture]
    alternative_titles: AlternativeTitle
    start_date: Optional[str]
    end_date: Optional[str]
    synopsis: Optional[str]
    mean: Optional[float]
    rank: Optional[int]
    popularity: Optional[int]
    num_list_users: int
    num_scoring_users: int
    nsfw: Literal["white", "gray", "black"]
    genres: Optional[list[GenericEntry]]
    created_at: datetime
    updated_at: datetime

    pictures: list[Picture]
    background: Optional[str]

    recommendations: list[Recommendation]
