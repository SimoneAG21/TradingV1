CREATE DATABASE IF NOT EXISTS Trading_dev;
CREATE USER IF NOT EXISTS 'trading_dev_user'@'localhost' IDENTIFIED BY 'devStrongPass2025!';
GRANT ALL PRIVILEGES ON Trading_dev.* TO 'trading_dev_user'@'localhost';

CREATE DATABASE IF NOT EXISTS Trading_test;
CREATE USER IF NOT EXISTS 'trading_test_user'@'localhost' IDENTIFIED BY 'TestStrongPass2025#';
GRANT ALL PRIVILEGES ON Trading_test.* TO 'trading_test_user'@'localhost';

CREATE DATABASE IF NOT EXISTS Trading_prod;
CREATE USER IF NOT EXISTS 'trading_prod_user'@'localhost' IDENTIFIED BY 'ProdSafePass2025$';
GRANT ALL PRIVILEGES ON Trading_prod.* TO 'trading_prod_user'@'localhost';