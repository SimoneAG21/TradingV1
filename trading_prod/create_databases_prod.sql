CREATE DATABASE IF NOT EXISTS Trading_prod;
CREATE USER IF NOT EXISTS 'trading_prod_user'@'localhost' IDENTIFIED BY 'ProdSafePass2025$';
GRANT ALL PRIVILEGES ON Trading_prod.* TO 'trading_prod_user'@'localhost';