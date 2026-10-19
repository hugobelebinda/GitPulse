package com.omnidoc.ingestion.service;

import com.omnidoc.ingestion.config.MinioProperties;
import com.omnidoc.ingestion.domain.DocumentRecord;
import com.omnidoc.ingestion.domain.DocumentStatus;
import com.omnidoc.ingestion.domain.DocumentUploadedEvent;
import com.omnidoc.ingestion.error.DocumentNotFoundException;
import com.omnidoc.ingestion.error.EventPublishException;
import com.omnidoc.ingestion.error.InvalidDocumentException;
import com.omnidoc.ingestion.error.StorageException;
import com.omnidoc.ingestion.messaging.DocumentEventPublisher;
import com.omnidoc.ingestion.repository.DocumentRepository;
import com.omnidoc.ingestion.storage.ObjectStorage;
import com.omnidoc.ingestion.web.DocumentResponse;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.http.MediaType;
import org.springframework.stereotype.Service;
import org.springframework.web.multipart.MultipartFile;

import java.io.ByteArrayInputStream;
import java.io.IOException;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import java.util.UUID;

@Service
public class DocumentIngestionService {

    private static final Logger log = LoggerFactory.getLogger(DocumentIngestionService.class);
    private static final byte[] PDF_HEADER = {'%', 'P', 'D', 'F', '-'};

    private final ObjectStorage objectStorage;
    private final DocumentRepository documentRepository;
    private final DocumentEventPublisher eventPublisher;
    private final MinioProperties minioProperties;

    public DocumentIngestionService(
            ObjectStorage objectStorage,
            DocumentRepository documentRepository,
            DocumentEventPublisher eventPublisher,
            MinioProperties minioProperties
    ) {
        this.objectStorage = objectStorage;
        this.documentRepository = documentRepository;
        this.eventPublisher = eventPublisher;
        this.minioProperties = minioProperties;
    }

    public DocumentResponse ingest(MultipartFile file) {
        byte[] content = readContent(file);
        validate(file, content);

        String documentId = UUID.randomUUID().toString();
        String filename = sanitizeFilename(file.getOriginalFilename());
        String objectKey = "documents/" + documentId + "/" + filename;
        String contentType = MediaType.APPLICATION_PDF_VALUE;
        String bucket = minioProperties.bucket();
        Instant uploadedAt = Instant.now();

        if (!objectStorage.bucketExists(bucket)) {
            throw new StorageException("MinIO bucket does not exist: " + bucket, null);
        }

        objectStorage.put(bucket, objectKey, new ByteArrayInputStream(content), content.length, contentType);

        DocumentRecord record = new DocumentRecord(
                documentId,
                filename,
                contentType,
                content.length,
                bucket,
                objectKey,
                DocumentStatus.PENDING,
                uploadedAt
        );

        try {
            documentRepository.save(record);
        } catch (RuntimeException ex) {
            log.error("Failed to save document {}; removing stored object {}", documentId, objectKey, ex);
            deleteQuietly(bucket, objectKey);
            throw ex;
        }

        DocumentUploadedEvent event = new DocumentUploadedEvent(
                documentId,
                bucket,
                objectKey,
                filename,
                contentType,
                uploadedAt
        );
        try {
            eventPublisher.publish(event);
        } catch (RuntimeException ex) {
            log.error("Failed to publish document {}", documentId, ex);
            record.markFailed(ex.getMessage(), Instant.now());
            documentRepository.save(record);
            throw new EventPublishException("Document was stored but could not be queued for processing", ex);
        }

        log.info("Accepted document {} ({}, {} bytes)", documentId, filename, content.length);
        return DocumentResponse.from(record);
    }

    public DocumentResponse get(String documentId) {
        return documentRepository.findById(documentId)
                .map(DocumentResponse::from)
                .orElseThrow(() -> new DocumentNotFoundException(documentId));
    }

    public List<DocumentResponse> listRecent() {
        return documentRepository.findTop20ByOrderByCreatedAtDesc().stream()
                .map(DocumentResponse::from)
                .toList();
    }

    private byte[] readContent(MultipartFile file) {
        if (file == null) {
            throw new InvalidDocumentException("A non-empty PDF file is required");
        }
        try {
            return file.getBytes();
        } catch (IOException ex) {
            throw new InvalidDocumentException("Unable to read the uploaded file");
        }
    }

    private void validate(MultipartFile file, byte[] content) {
        if (content.length == 0) {
            throw new InvalidDocumentException("A non-empty PDF file is required");
        }
        if (!isPdf(content)) {
            throw new InvalidDocumentException("File is not a PDF");
        }
        String filename = file.getOriginalFilename();
        boolean pdfName = filename != null && filename.toLowerCase(Locale.ROOT).endsWith(".pdf");
        String contentType = file.getContentType();
        boolean pdfType = contentType == null
                || contentType.isBlank()
                || MediaType.APPLICATION_PDF_VALUE.equalsIgnoreCase(contentType)
                || MediaType.APPLICATION_OCTET_STREAM_VALUE.equalsIgnoreCase(contentType);
        if (!pdfName && !MediaType.APPLICATION_PDF_VALUE.equalsIgnoreCase(contentType == null ? "" : contentType)) {
            throw new InvalidDocumentException("Only PDF documents are accepted");
        }
        if (!pdfType) {
            throw new InvalidDocumentException("Only PDF documents are accepted");
        }
    }

    private boolean isPdf(byte[] content) {
        if (content.length < PDF_HEADER.length) {
            return false;
        }
        for (int i = 0; i < PDF_HEADER.length; i++) {
            if (content[i] != PDF_HEADER[i]) {
                return false;
            }
        }
        return true;
    }

    static String sanitizeFilename(String original) {
        String name = original == null ? "" : Paths.get(original).getFileName().toString().trim();
        name = name.replaceAll("[^A-Za-z0-9._-]", "_");
        if (name.isBlank() || ".".equals(name) || "..".equals(name)) {
            return "document.pdf";
        }
        return name;
    }

    private void deleteQuietly(String bucket, String objectKey) {
        try {
            objectStorage.delete(bucket, objectKey);
        } catch (RuntimeException ex) {
            log.error("Failed to remove orphan object {}", objectKey, ex);
        }
    }
}
