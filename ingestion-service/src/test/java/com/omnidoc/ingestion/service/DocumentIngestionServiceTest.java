package com.omnidoc.ingestion.service;

import com.omnidoc.ingestion.config.MinioProperties;
import com.omnidoc.ingestion.domain.DocumentRecord;
import com.omnidoc.ingestion.domain.DocumentStatus;
import com.omnidoc.ingestion.domain.DocumentUploadedEvent;
import com.omnidoc.ingestion.error.EventPublishException;
import com.omnidoc.ingestion.error.InvalidDocumentException;
import com.omnidoc.ingestion.messaging.DocumentEventPublisher;
import com.omnidoc.ingestion.repository.DocumentRepository;
import com.omnidoc.ingestion.storage.ObjectStorage;
import com.omnidoc.ingestion.web.DocumentResponse;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.mock.web.MockMultipartFile;

import java.nio.charset.StandardCharsets;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyLong;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.doThrow;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class DocumentIngestionServiceTest {

    private static final byte[] PDF = "%PDF-1.4\ntrailer\n%%EOF\n".getBytes(StandardCharsets.US_ASCII);

    private ObjectStorage objectStorage;
    private DocumentRepository documentRepository;
    private DocumentEventPublisher eventPublisher;
    private DocumentIngestionService service;

    @BeforeEach
    void setUp() {
        objectStorage = mock(ObjectStorage.class);
        documentRepository = mock(DocumentRepository.class);
        eventPublisher = mock(DocumentEventPublisher.class);
        service = new DocumentIngestionService(
                objectStorage,
                documentRepository,
                eventPublisher,
                new MinioProperties("http://localhost:9000", "omnidoc", "omnidoc_dev_password", "omnidoc-documents")
        );
        when(objectStorage.bucketExists("omnidoc-documents")).thenReturn(true);
        when(documentRepository.save(any(DocumentRecord.class))).thenAnswer(invocation -> invocation.getArgument(0));
    }

    @Test
    void storesPendingDocumentAndPublishesEvent() {
        MockMultipartFile file = new MockMultipartFile("file", "invoice.pdf", "application/pdf", PDF);

        DocumentResponse response = service.ingest(file);

        assertThat(response.status()).isEqualTo("PENDING");
        assertThat(response.originalFilename()).isEqualTo("invoice.pdf");
        assertThat(response.bucket()).isEqualTo("omnidoc-documents");
        assertThat(response.objectKey()).startsWith("documents/").endsWith("/invoice.pdf");
        verify(objectStorage).put(eq("omnidoc-documents"), eq(response.objectKey()), any(), eq((long) PDF.length), eq("application/pdf"));
        verify(documentRepository).save(any(DocumentRecord.class));
        verify(eventPublisher).publish(any(DocumentUploadedEvent.class));
    }

    @Test
    void rejectsNonPdfBytes() {
        MockMultipartFile file = new MockMultipartFile("file", "notes.pdf", "application/pdf", "hello".getBytes(StandardCharsets.UTF_8));

        assertThatThrownBy(() -> service.ingest(file))
                .isInstanceOf(InvalidDocumentException.class)
                .hasMessage("File is not a PDF");
        verify(objectStorage, never()).put(anyString(), anyString(), any(), anyLong(), anyString());
    }

    @Test
    void marksDocumentFailedWhenPublishFails() {
        MockMultipartFile file = new MockMultipartFile("file", "invoice.pdf", "application/pdf", PDF);
        doThrow(new IllegalStateException("broker down")).when(eventPublisher).publish(any());

        assertThatThrownBy(() -> service.ingest(file)).isInstanceOf(EventPublishException.class);

        verify(documentRepository, org.mockito.Mockito.times(2)).save(org.mockito.ArgumentMatchers.argThat(record ->
                record.getStatus() == DocumentStatus.PENDING || record.getStatus() == DocumentStatus.FAILED
        ));
    }

    @Test
    void removesStoredObjectWhenMongoSaveFails() {
        MockMultipartFile file = new MockMultipartFile("file", "invoice.pdf", "application/pdf", PDF);
        when(documentRepository.save(any(DocumentRecord.class))).thenThrow(new IllegalStateException("mongo down"));

        assertThatThrownBy(() -> service.ingest(file)).isInstanceOf(IllegalStateException.class);

        verify(objectStorage).delete(eq("omnidoc-documents"), anyString());
        verify(eventPublisher, never()).publish(any());
    }
}
