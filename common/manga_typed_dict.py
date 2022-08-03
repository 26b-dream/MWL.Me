from typing import Literal, Optional

from pydantic import BaseModel, Field

from common.shared_type_dict import GenericEntry, RelatedMedia, Shared


class AuthorNode(BaseModel):
    id_: int = Field(..., alias="id")
    first_name: str
    last_name: str


class Author(BaseModel):
    node: AuthorNode
    role: Literal["Art", "Story", "Story & Art"]


class Serialization(BaseModel):
    node: GenericEntry


class MangaDataClass(Shared):
    media_type: Literal[
        "unknown",
        "manga",
        "novel",
        "one_shot",
        "doujinshi",
        "manhwa",
        "manhua",
        "oel",
        # Not listed in the official API documentation
        "light_novel",
    ]
    status: Literal[
        "finished",
        "currently_publishing",
        "not_yet_published",
        # Not listed in the official API documentation
        "discontinued",
        "on_hiatus",
    ]
    num_volumes: int
    num_chapters: int
    authors: Optional[list[Author]]

    related_manga: list[RelatedMedia]
    serialization: list[Serialization]
