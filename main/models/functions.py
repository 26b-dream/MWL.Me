from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from typing import Any

import inspect

from django.db import models

import common.extended_re as re


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
    key_name = inspect.stack()[1][4][0].strip().split(" =")[0]  # type: ignore
    main_model = inspect.stack()[1][3]
    related_name = f"{main_model}_{fk_model.__name__}_{key_name}"

    return models.ForeignKey(fk_model, on_delete=models.CASCADE, related_name=related_name)
