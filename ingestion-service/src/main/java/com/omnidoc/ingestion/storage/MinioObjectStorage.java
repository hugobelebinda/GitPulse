package com.omnidoc.ingestion.storage;

import com.omnidoc.ingestion.error.StorageException;
import io.minio.BucketExistsArgs;
import io.minio.MinioClient;
import io.minio.PutObjectArgs;
import io.minio.RemoveObjectArgs;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.stereotype.Component;

import java.io.InputStream;

@Component
public class MinioObjectStorage implements ObjectStorage {

    private static final Logger log = LoggerFactory.getLogger(MinioObjectStorage.class);

    private final MinioClient minioClient;

    public MinioObjectStorage(MinioClient minioClient) {
        this.minioClient = minioClient;
    }

    @Override
    public void put(String bucket, String objectKey, InputStream body, long size, String contentType) {
        try (InputStream input = body) {
            minioClient.putObject(
                    PutObjectArgs.builder()
                            .bucket(bucket)
                            .object(objectKey)
                            .stream(input, size, -1L)
                            .contentType(contentType)
                            .build()
            );
            log.info("Stored object {} in bucket {}", objectKey, bucket);
        } catch (Exception ex) {
            throw new StorageException("Unable to store object " + objectKey, ex);
        }
    }

    @Override
    public void delete(String bucket, String objectKey) {
        try {
            minioClient.removeObject(
                    RemoveObjectArgs.builder()
                            .bucket(bucket)
                            .object(objectKey)
                            .build()
            );
            log.info("Removed object {} from bucket {}", objectKey, bucket);
        } catch (Exception ex) {
            throw new StorageException("Unable to delete object " + objectKey, ex);
        }
    }

    @Override
    public boolean bucketExists(String bucket) {
        try {
            return minioClient.bucketExists(BucketExistsArgs.builder().bucket(bucket).build());
        } catch (Exception ex) {
            throw new StorageException("Unable to check bucket " + bucket, ex);
        }
    }
}
