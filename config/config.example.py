# Standard Library
from dataclasses import dataclass


@dataclass
class MyAnimeListSecrets:
    CLIENT_ID: str = "CLIENT_ID"
    CLIENT_SECRET: str = "CLIENT_SECRET"
