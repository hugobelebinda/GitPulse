package com.omnidoc.ingestion.web;

import com.omnidoc.ingestion.error.InvalidDocumentException;
import com.omnidoc.ingestion.service.DocumentIngestionService;
import org.junit.jupiter.api.Test;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.autoconfigure.web.servlet.WebMvcTest;
import org.springframework.http.MediaType;
import org.springframework.mock.web.MockMultipartFile;
import org.springframework.test.context.bean.override.mockito.MockitoBean;
import org.springframework.test.web.servlet.MockMvc;

import java.nio.charset.StandardCharsets;
import java.time.Instant;
import java.util.List;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.multipart;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

@WebMvcTest(DocumentController.class)
class DocumentControllerTest {

    @Autowired
    private MockMvc mockMvc;

    @MockitoBean
    private DocumentIngestionService ingestionService;

    @Test
    void uploadReturnsAcceptedDocument() throws Exception {
        when(ingestionService.ingest(any())).thenReturn(new DocumentResponse(
                "doc-1",
                "PENDING",
                "invoice.pdf",
                "application/pdf",
                12,
                "omnidoc-documents",
                "documents/doc-1/invoice.pdf",
                null,
                Instant.parse("2026-10-14T00:00:00Z"),
                null,
                null
        ));
        MockMultipartFile file = new MockMultipartFile(
                "file",
                "invoice.pdf",
                "application/pdf",
                "%PDF-1.4".getBytes(StandardCharsets.US_ASCII)
        );

        mockMvc.perform(multipart("/api/documents/upload").file(file))
                .andExpect(status().isAccepted())
                .andExpect(jsonPath("$.documentId").value("doc-1"))
                .andExpect(jsonPath("$.status").value("PENDING"));
    }

    @Test
    void uploadRejectsInvalidPdf() throws Exception {
        when(ingestionService.ingest(any())).thenThrow(new InvalidDocumentException("File is not a PDF"));
        MockMultipartFile file = new MockMultipartFile("file", "notes.txt", MediaType.TEXT_PLAIN_VALUE, "hello".getBytes(StandardCharsets.UTF_8));

        mockMvc.perform(multipart("/api/documents/upload").file(file))
                .andExpect(status().isBadRequest())
                .andExpect(jsonPath("$.detail").value("File is not a PDF"));
    }

    @Test
    void listReturnsRecentDocuments() throws Exception {
        when(ingestionService.listRecent()).thenReturn(List.of(new DocumentResponse(
                "doc-1",
                "COMPLETED",
                "invoice.pdf",
                "application/pdf",
                12,
                "omnidoc-documents",
                "documents/doc-1/invoice.pdf",
                null,
                Instant.parse("2026-10-14T00:00:00Z"),
                "ACME billed Jane Miller $250.",
                List.of("Amount: $250.00")
        )));

        mockMvc.perform(get("/api/documents"))
                .andExpect(status().isOk())
                .andExpect(jsonPath("$[0].documentId").value("doc-1"))
                .andExpect(jsonPath("$[0].summary").value("ACME billed Jane Miller $250."))
                .andExpect(jsonPath("$[0].keyInformation[0]").value("Amount: $250.00"));
    }

    @Test
    void getReturnsNotFound() throws Exception {
        when(ingestionService.get("missing")).thenThrow(new com.omnidoc.ingestion.error.DocumentNotFoundException("missing"));

        mockMvc.perform(get("/api/documents/missing"))
                .andExpect(status().isNotFound());
    }
}
