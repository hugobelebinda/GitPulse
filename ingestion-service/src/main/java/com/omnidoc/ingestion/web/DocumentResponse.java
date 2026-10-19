package com.omnidoc.ingestion.web;

import com.fasterxml.jackson.annotation.JsonInclude;
import com.omnidoc.ingestion.domain.DocumentRecord;

import java.time.Instant;
import java.util.List;

@JsonInclude(JsonInclude.Include.NON_NULL)
public record DocumentResponse(
        String documentId,
        String status,
        String originalFilename,
        String contentType,
        long sizeBytes,
        String bucket,
        String objectKey,
        String errorMessage,
        Instant createdAt,
        String summary,
        List<String> keyInformation
) {

    public static DocumentResponse from(DocumentRecord record) {
        return new DocumentResponse(
                record.getId(),
                record.getStatus().name(),
                record.getOriginalFilename(),
                record.getContentType(),
                record.getSizeBytes(),
                record.getBucket(),
                record.getObjectKey(),
                record.getErrorMessage(),
                record.getCreatedAt(),
                record.getSummary(),
                record.getKeyInformation()
        );
    }
}
