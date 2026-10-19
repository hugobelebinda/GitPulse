package com.omnidoc.ingestion.domain;

import org.springframework.data.annotation.Id;
import org.springframework.data.mongodb.core.mapping.Document;

import java.time.Instant;
import java.util.List;

@Document(collection = "documents")
public class DocumentRecord {

    @Id
    private String id;
    private String originalFilename;
    private String contentType;
    private long sizeBytes;
    private String bucket;
    private String objectKey;
    private DocumentStatus status;
    private String errorMessage;
    private String summary;
    private List<String> keyInformation;
    private Instant createdAt;
    private Instant updatedAt;

    public DocumentRecord() {
    }

    public DocumentRecord(
            String id,
            String originalFilename,
            String contentType,
            long sizeBytes,
            String bucket,
            String objectKey,
            DocumentStatus status,
            Instant createdAt
    ) {
        this.id = id;
        this.originalFilename = originalFilename;
        this.contentType = contentType;
        this.sizeBytes = sizeBytes;
        this.bucket = bucket;
        this.objectKey = objectKey;
        this.status = status;
        this.createdAt = createdAt;
        this.updatedAt = createdAt;
    }

    public void markFailed(String message, Instant when) {
        this.status = DocumentStatus.FAILED;
        this.errorMessage = message;
        this.updatedAt = when;
    }

    public String getId() {
        return id;
    }

    public String getOriginalFilename() {
        return originalFilename;
    }

    public String getContentType() {
        return contentType;
    }

    public long getSizeBytes() {
        return sizeBytes;
    }

    public String getBucket() {
        return bucket;
    }

    public String getObjectKey() {
        return objectKey;
    }

    public DocumentStatus getStatus() {
        return status;
    }

    public String getErrorMessage() {
        return errorMessage;
    }

    public String getSummary() {
        return summary;
    }

    public List<String> getKeyInformation() {
        return keyInformation;
    }

    public Instant getCreatedAt() {
        return createdAt;
    }

    public Instant getUpdatedAt() {
        return updatedAt;
    }
}
