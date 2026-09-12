from typing import Annotated

from pydantic import BaseModel, ConfigDict, StringConstraints

# Trimmed, non-empty strings for user-entered text.
ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
MediumText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
LongText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=10000)]
Phone = Annotated[str, StringConstraints(strip_whitespace=True, max_length=32, pattern=r"^[0-9+()\-\s]{0,32}$")]


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
