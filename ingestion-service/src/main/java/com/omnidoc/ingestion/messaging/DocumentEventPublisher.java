package com.omnidoc.ingestion.messaging;

import com.omnidoc.ingestion.config.MessagingProperties;
import com.omnidoc.ingestion.domain.DocumentUploadedEvent;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.amqp.rabbit.core.RabbitTemplate;
import org.springframework.stereotype.Component;

@Component
public class DocumentEventPublisher {

    private static final Logger log = LoggerFactory.getLogger(DocumentEventPublisher.class);

    private final RabbitTemplate rabbitTemplate;
    private final MessagingProperties messagingProperties;

    public DocumentEventPublisher(RabbitTemplate rabbitTemplate, MessagingProperties messagingProperties) {
        this.rabbitTemplate = rabbitTemplate;
        this.messagingProperties = messagingProperties;
    }

    public void publish(DocumentUploadedEvent event) {
        rabbitTemplate.convertAndSend(messagingProperties.queue(), event);
        log.info("Published DocumentUploadedEvent for document {} to {}", event.documentId(), messagingProperties.queue());
    }
}
