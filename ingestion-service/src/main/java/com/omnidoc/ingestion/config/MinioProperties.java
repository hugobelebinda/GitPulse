package com.omnidoc.ingestion.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "omnidoc.minio")
public record MinioProperties(String endpoint, String accessKey, String secretKey, String bucket) {
}
