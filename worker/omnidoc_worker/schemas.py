from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class EntitySpan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    label: Literal["NAME", "DATE", "ORG", "VALUE"]
    score: float = Field(ge=0.0, le=1.0)
    start: int = Field(ge=0)
    end: int = Field(ge=0)

    @model_validator(mode="after")
    def end_follows_start(self) -> "EntitySpan":
        if self.end < self.start:
            raise ValueError("entity end is before start")
        return self


class ExtractedEntities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    names: list[str]
    dates: list[str]
    orgs: list[str]
    values: list[str]
    entities: list[EntitySpan]


class DocumentInsight(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    summary: str = Field(min_length=1)
    key_information: list[str] = Field(min_length=1, alias="keyInformation")
