package com.omnidoc.ingestion.storage;

import java.io.InputStream;

public interface ObjectStorage {

    void put(String bucket, String objectKey, InputStream body, long size, String contentType);

    void delete(String bucket, String objectKey);

    boolean bucketExists(String bucket);
}
