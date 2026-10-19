package com.omnidoc.ingestion.repository;

import com.omnidoc.ingestion.domain.DocumentRecord;
import org.springframework.data.mongodb.repository.MongoRepository;

import java.util.List;

public interface DocumentRepository extends MongoRepository<DocumentRecord, String> {

    List<DocumentRecord> findTop20ByOrderByCreatedAtDesc();
}
