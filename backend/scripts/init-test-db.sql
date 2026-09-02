-- Runs automatically on first container start (mounted into
-- /docker-entrypoint-initdb.d/) so the isolated test database exists
-- without any manual createdb step.
CREATE DATABASE ai_executive_assistant_test;
