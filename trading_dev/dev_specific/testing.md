

```sql

-- Log in to MySQL
mysql -u trading_dev_user -p Trading_dev

-- Enter password: devStrongPass2025!

-- Truncate channel_fetch_batches to clear all batch records
TRUNCATE TABLE channel_fetch_batches;

-- Reset fetch-related fields in channels to start fresh
UPDATE channels
SET FetchStatus = NULL,
    fetch_attempts = 0,
    earliest_raw_message_ID = NULL,
    earliest_raw_message_date = NULL,
    latest_raw_message_ID = NULL,
    latest_raw_message_date = NULL
WHERE Operating = 1 AND Disappeared = 0;

-- Verify the reset
SELECT ID, FetchStatus, fetch_attempts, earliest_raw_message_ID, latest_raw_message_ID
FROM channels
WHERE Operating = 1 AND Disappeared = 0;

SELECT COUNT(*) FROM channel_fetch_batches;

```


```
python scripts/telegram_fetch.py --max-batches 25
```
```
python scripts/channelTracker.py --config config/combined_config.yaml
``` 
```sh
pytest tests/test_config_manager.py --cov=helper --cov-report=html
```

```sh
pytest tests/ --cov=helper --cov-report=html
```



```sh
   clear;type .\helper\config_manager.py; type .\tests\test_config_manager.py;  
 pytest tests/test_config_manager::test_singleton_pattern
 ```

```sh
clear;pytest tests/test_config_manager::test_singleton_pattern
```



```sh
    clear;pytest tests/test_telegram_client.py -v
 ```


 ```sh
    clear ; pytest tests -v
 ```
