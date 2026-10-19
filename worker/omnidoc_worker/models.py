from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class DocumentUploadedEvent(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    document_id: str = Field(alias="documentId")
    bucket: str
    object_key: str = Field(alias="objectKey")
    original_filename: str = Field(alias="originalFilename")
    content_type: str = Field(alias="contentType")
    uploaded_at: datetime = Field(alias="uploadedAt")

    @field_validator("uploaded_at", mode="before")
    @classmethod
    def trim_fractional_seconds(cls, value: object) -> object:
        if not isinstance(value, str) or "." not in value:
            return value
        head, fraction = value.split(".", 1)
        digits: list[str] = []
        suffix = ""
        for index, char in enumerate(fraction):
            if char.isdigit() and len(digits) < 6:
                digits.append(char)
            elif char.isdigit():
                continue
            else:
                suffix = fraction[index:]
                break
        if not digits:
            return value
        return f"{head}.{''.join(digits)}{suffix}"
