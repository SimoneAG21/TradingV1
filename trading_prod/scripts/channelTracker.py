#scripts/channelTracker.py
import argparse
import os
import sys
import time
import pandas as pd
from telethon import TelegramClient
import logging
import traceback
from sqlalchemy import create_engine
from sqlalchemy.sql import text
import asyncio
from datetime import datetime
from helper.config_manager import ConfigManager
from helper.Logger import Logging

def setup_logging(config, log_file):
    """Setup logging with file and console handlers using Logging class."""
    logger = Logging(config, instance_id="channelTracker")
    logger.set_log_file(os.path.splitext(os.path.basename(log_file))[0])
    return logger

def main():
    default_log_file = "/home/egirg/shared/trading_dev/logs/channel_tracker_default.log"
    config = ConfigManager('config/channel_sync_config.yaml', project_root="/home/egirg/shared/trading_dev")
    logger = setup_logging(config, default_log_file)

    try:
        parser = argparse.ArgumentParser(description="Channel Tracker Script")
        parser.add_argument('--project-root', type=str, help="Project root directory")
        args = parser.parse_args()

        project_root = ConfigManager.determine_project_root(
            env_var_name="CHTRKR_ROOT",
            cli_project_root=args.project_root,
            fallback_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
        )

        config = ConfigManager('config/channel_sync_config.yaml', project_root=project_root)

        db_config = {
            'user': config.get('database', 'mysql.user'),
            'password': config.get('database', 'mysql.password'),
            'host': config.get('database', 'mysql.host'),
            'port': config.get('database', 'mysql.port'),
            'database': config.get('database', 'mysql.database')
        }
        tele_config = {
            'session_path': config.get('telegram', 'session_path'),
            'api_id': config.get('telegram', 'api_id'),
            'api_hash': config.get('telegram', 'api_hash'),
            'phone_number': config.get('telegram', 'phone')
        }
        log_file = config.get_with_default('', 'log_file', 'channel_sync')
        if not os.path.isabs(log_file):
            log_file = os.path.join(project_root, 'logs', f"{log_file}.log")
        log_config = {'log_file': log_file}

        logger = setup_logging(config, log_config['log_file'])

        try:
            connection_string = f"mysql+mysqlconnector://{db_config['user']}:{db_config['password']}@{db_config['host']}:{db_config['port']}/{db_config['database']}"
            logger.info(f"Creating SQLAlchemy engine with connection string: {connection_string}")
            engine = create_engine(connection_string)
            logger.info(f"Engine created: {engine}")
            if engine is None:
                logger.error("SQLAlchemy engine is unexpectedly None")
                sys.exit(1)
        except Exception as e:
            logger.error(f"Failed to create SQLAlchemy engine: {e}")
            sys.exit(1)

        try:
            with engine.connect() as conn:
                logger.info(f"Connection to {db_config['database']} successful!")
        except Exception as e:
            logger.error(f"Error connecting to MySQL: {e}")
            sys.exit(1)

        async def fetch_telegram_channels():
            client = TelegramClient(tele_config["session_path"], tele_config["api_id"], tele_config["api_hash"])
            try:
                logger.info("Attempting to connect to Telegram...")
                await client.connect()
                if not await client.is_user_authorized():
                    logger.info("Session not authorized; starting login...")
                    await client.start(phone=tele_config["phone_number"])
                else:
                    logger.info("Using existing authorized session")
                
                logger.info("Successfully logged in to Telegram!")
                dialogs = await client.get_dialogs()
                channel_data = [(dialog.id, dialog.name) for dialog in dialogs if dialog.is_channel]
                df_tele = pd.DataFrame(channel_data, columns=['ID', 'Name'])
                with engine.connect() as conn:
                    conn.execute(text("TRUNCATE TABLE temp_channels"))
                    df_tele.to_sql('temp_channels', conn, if_exists='append', index=False)
                    conn.commit()
                    logger.info(f"Stored {len(df_tele)} channels in temp_channels")
                return df_tele
            except Exception as e:
                logger.error(f"Error fetching Telegram channels: {e}")
                return None
            finally:
                if client.is_connected():
                    await client.disconnect()
                logger.info("Disconnected from Telegram")

        def fetch_db_channels():
            try:
                with engine.connect() as conn:
                    query = "SELECT ID, Name, Operating, Disappeared, created_dt, update_dt FROM channels"
                    df_db = pd.read_sql(query, conn)
                    logger.info(f"Fetched {len(df_db)} channels from {db_config['database']}")
                    return df_db
            except Exception as e:
                logger.error(f"Error fetching channels from database: {e}")
                return None

        def update_channels_table(df_tele):
            df_db = fetch_db_channels()
            if df_db is None or df_tele is None or df_tele.empty:
                logger.warning("Cannot update channels: database or Telegram data missing.")
                return
            df_db.set_index('ID', inplace=True)
            df_tele.set_index('ID', inplace=True)
            try:
                with engine.connect() as conn:
                    new_channels = df_tele[~df_tele.index.isin(df_db.index)].copy()
                    if not new_channels.empty:
                        new_channels['Operating'] = 0
                        new_channels['Disappeared'] = 0
                        new_channels['created_dt'] = datetime.now()
                        new_channels['update_dt'] = None
                        new_channels.reset_index().to_sql('channels', conn, if_exists='append', index=False)
                        logger.info(f"Inserted {len(new_channels)} new channels")
                    for channel_id in df_db.index:
                        if channel_id in df_tele.index:
                            tele_name = df_tele.loc[channel_id, 'Name']
                            db_name = df_db.loc[channel_id, 'Name']
                            db_disappeared = df_db.loc[channel_id, 'Disappeared']
                            update_needed = (tele_name != db_name) or (db_disappeared != 0)
                            if update_needed:
                                conn.execute(
                                    text("UPDATE channels SET Name = :name, Disappeared = 0, update_dt = :update_dt WHERE ID = :id"),
                                    {"name": tele_name, "update_dt": datetime.now(), "id": channel_id}
                                )
                        else:
                            if df_db.loc[channel_id, 'Disappeared'] != 1:
                                conn.execute(
                                    text("UPDATE channels SET Disappeared = 1, update_dt = :update_dt WHERE ID = :id"),
                                    {"update_dt": datetime.now(), "id": channel_id}
                                )
                    conn.commit()
                    logger.info("Channels table updated successfully")
            except Exception as e:
                logger.error(f"Error updating channels table: {e}")

        interval = config.get_with_default('channel_sync', 'interval', 180) * 60  # Default 5 minutes
        while True:
            logger.info("Starting channel sync cycle")
            df_tele = asyncio.run(fetch_telegram_channels())
            update_channels_table(df_tele)
            logger.info(f"Sleeping for {interval} seconds")
            time.sleep(interval)

    except Exception as e:
        logger.error(f"Error: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        logger.close_log()

if __name__ == "__main__":
    main()
