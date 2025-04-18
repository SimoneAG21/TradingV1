USE Trading_dev;

DROP TABLE IF EXISTS channel_fetch_batches;

CREATE TABLE channel_fetch_batches (
    channel_id BIGINT NOT NULL,
    batch_timestamp DATETIME NOT NULL,
    message_file_path VARCHAR(512),
    first_message_id BIGINT,
    first_timestamp DATETIME,
    last_message_id BIGINT,
    last_timestamp DATETIME,
    message_count INT,
    processed TINYINT DEFAULT 0,
    created_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (channel_id, batch_timestamp)
);