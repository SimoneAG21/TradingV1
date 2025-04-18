-- sqls/create_tables.sql
CREATE DATABASE IF NOT EXISTS Trading_dev;
USE Trading_dev;

CREATE TABLE IF NOT EXISTS channels (
    ID BIGINT NOT NULL PRIMARY KEY,
    Name VARCHAR(255),
    Operating TINYINT DEFAULT 1,
    Disappeared TINYINT DEFAULT 0,
    created_dt DATETIME DEFAULT CURRENT_TIMESTAMP,
    update_dt DATETIME,
    earliest_raw_message_ID BIGINT,
    earliest_raw_message_date DATETIME,
    latest_raw_message_ID BIGINT,
    latest_raw_message_date DATETIME,
    latest_batch_raw_run DATETIME,
    FetchStatus TINYINT DEFAULT 0,
    fetch_attempts INT DEFAULT 0,
    priority INT,
    pattern_profile TEXT,
    usefulness_score FLOAT
);

CREATE TABLE IF NOT EXISTS temp_channels (
    ID BIGINT NOT NULL,
    Name VARCHAR(255)
);
