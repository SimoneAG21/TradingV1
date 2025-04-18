CREATE DATABASE IF NOT EXISTS Trading_dev;
CREATE USER IF NOT EXISTS 'trading_dev_user'@'localhost' IDENTIFIED BY 'devStrongPass2025!';
GRANT ALL PRIVILEGES ON Trading_dev.* TO 'trading_dev_user'@'localhost';
