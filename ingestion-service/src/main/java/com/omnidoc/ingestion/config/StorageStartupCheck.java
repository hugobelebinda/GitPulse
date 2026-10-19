package com.omnidoc.ingestion.config;

import com.omnidoc.ingestion.storage.ObjectStorage;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

@Component
public class StorageStartupCheck implements ApplicationRunner {

    private static final Logger log = LoggerFactory.getLogger(StorageStartupCheck.class);

    private final ObjectStorage objectStorage;
    private final MinioProperties minioProperties;

    public StorageStartupCheck(ObjectStorage objectStorage, MinioProperties minioProperties) {
        this.objectStorage = objectStorage;
        this.minioProperties = minioProperties;
    }

    @Override
    public void run(ApplicationArguments args) {
        if (!objectStorage.bucketExists(minioProperties.bucket())) {
            throw new IllegalStateException("MinIO bucket does not exist: " + minioProperties.bucket());
        }
        log.info("MinIO bucket {} is reachable at {}", minioProperties.bucket(), minioProperties.endpoint());
    }
}
