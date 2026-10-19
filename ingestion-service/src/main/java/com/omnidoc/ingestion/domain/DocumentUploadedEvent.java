package com.omnidoc.ingestion.domain;

import java.time.Instant;

public record DocumentUploadedEvent(
        String documentId,
        String bucket,
        String objectKey,
        String originalFilename,
        String contentType,
        Instant uploadedAt
) {
}
