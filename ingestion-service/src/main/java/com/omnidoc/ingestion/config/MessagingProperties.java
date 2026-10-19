package com.omnidoc.ingestion.config;

import org.springframework.boot.context.properties.ConfigurationProperties;

@ConfigurationProperties(prefix = "omnidoc.messaging")
public record MessagingProperties(String queue) {
}
