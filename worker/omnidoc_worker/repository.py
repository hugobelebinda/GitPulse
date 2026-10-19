import asyncio
import logging
from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorClient
from pymongo.errors import PyMongoError

from omnidoc_worker.extraction import ExtractionResult
from omnidoc_worker.schemas import DocumentInsight

log = logging.getLogger(__name__)


class RepositoryError(Exception):
    def __init__(self, message: str, *, transient: bool) -> None:
        super().__init__(message)
        self.transient = transient


class DocumentRepository:
    def __init__(self, uri: str, database: str) -> None:
        self._uri = uri
        self._database = database
        self._loop = asyncio.new_event_loop()
        self._client: AsyncIOMotorClient | None = None

    def connect(self) -> None:
        async def _connect() -> None:
            self._client = AsyncIOMotorClient(self._uri, serverSelectionTimeoutMS=5000)
            await self._client.admin.command("ping")

        self._run(_connect())
        log.info("Connected to MongoDB database %s", self._database)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
        self._loop.close()

    def save_cleaned_text(self, document_id: str, cleaned_text: str, extraction: ExtractionResult) -> None:
        async def _save() -> None:
            result = await self._collection().update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "cleanedText": cleaned_text,
                        "rawText": extraction.raw_text,
                        "extractionMethod": extraction.method,
                        "pageCount": extraction.page_count,
                        "textExtractedAt": datetime.now(timezone.utc),
                        "updatedAt": datetime.now(timezone.utc),
                    }
                },
            )
            if result.matched_count == 0:
                log.warning("No MongoDB document %s; cleaned text was not stored", document_id)
            else:
                log.info(
                    "Stored cleaned text for %s (%s chars, %s)",
                    document_id,
                    len(cleaned_text),
                    extraction.method,
                )

        self._run(_save())

    def complete(
        self,
        document_id: str,
        cleaned_text: str,
        extraction: ExtractionResult,
        insight: DocumentInsight,
        summary_model: str,
    ) -> None:
        payload = insight.model_dump(by_alias=True)

        async def _complete() -> None:
            result = await self._collection().update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "cleanedText": cleaned_text,
                        "rawText": extraction.raw_text,
                        "extractionMethod": extraction.method,
                        "pageCount": extraction.page_count,
                        "textExtractedAt": datetime.now(timezone.utc),
                        "summary": payload["summary"],
                        "keyInformation": payload["keyInformation"],
                        "summaryModel": summary_model,
                        "status": "COMPLETED",
                        "errorMessage": None,
                        "updatedAt": datetime.now(timezone.utc),
                    }
                },
            )
            if result.matched_count == 0:
                log.warning("No MongoDB document %s; extraction was not stored", document_id)
            else:
                log.info(
                    "Completed document %s with %s key facts",
                    document_id,
                    len(payload["keyInformation"]),
                )

        self._run(_complete())

    def mark_failed(self, document_id: str, message: str) -> None:
        async def _fail() -> None:
            await self._collection().update_one(
                {"_id": document_id},
                {
                    "$set": {
                        "status": "FAILED",
                        "errorMessage": message,
                        "updatedAt": datetime.now(timezone.utc),
                    }
                },
            )

        try:
            self._run(_fail())
        except RepositoryError:
            log.exception("Unable to mark document %s as FAILED", document_id)

    def _collection(self):
        if self._client is None:
            raise RepositoryError("MongoDB client is not connected", transient=True)
        return self._client[self._database]["documents"]

    def _run(self, awaitable) -> None:
        try:
            self._loop.run_until_complete(awaitable)
        except PyMongoError as exc:
            raise RepositoryError(str(exc), transient=True) from exc
