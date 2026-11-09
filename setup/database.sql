-- ---------------------------------------------------------------------------
-- HRMS - MySQL schema bootstrap
-- Run once as root:  mysql -u root -p < setup\database.sql
--
-- Creates the database and a dedicated application user. Django creates the
-- tables itself (python manage.py migrate); this script only provisions the
-- schema and the credentials.
-- ---------------------------------------------------------------------------

CREATE DATABASE IF NOT EXISTS hrms_db
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

-- CHANGE THIS PASSWORD and put the same value in backend/.env
DROP USER IF EXISTS 'hrms_user'@'localhost';
CREATE USER 'hrms_user'@'localhost' IDENTIFIED BY 'ChangeThisPassword123!';
GRANT ALL PRIVILEGES ON hrms_db.* TO 'hrms_user'@'localhost';

-- Windows/MySQL 8 sometimes connects over 127.0.0.1 instead of the socket.
DROP USER IF EXISTS 'hrms_user'@'127.0.0.1';
CREATE USER 'hrms_user'@'127.0.0.1' IDENTIFIED BY 'ChangeThisPassword123!';
GRANT ALL PRIVILEGES ON hrms_db.* TO 'hrms_user'@'127.0.0.1';

-- Django's test runner creates and drops a test database.
GRANT ALL PRIVILEGES ON `test_hrms_db`.* TO 'hrms_user'@'localhost';
GRANT ALL PRIVILEGES ON `test_hrms_db`.* TO 'hrms_user'@'127.0.0.1';

FLUSH PRIVILEGES;

SHOW GRANTS FOR 'hrms_user'@'localhost';

-- ---------------------------------------------------------------------------
-- After `python manage.py migrate`, verify with:
--
--   USE hrms_db;
--   SHOW TABLES;
--   SELECT app, name FROM django_migrations ORDER BY id;
--   SHOW CREATE TABLE hrms_attendance;   -- look for the (employee_id, date) unique key
-- ---------------------------------------------------------------------------
