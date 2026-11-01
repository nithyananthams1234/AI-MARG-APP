-- One-time setup for the Mentor Intelligence Engine database role and schemas.
-- Run as the postgres superuser, CONNECTED TO marg_mentor_intelligence:
--   & "D:\postgre\bin\psql.exe" -U postgres -h localhost -p 5432 -d marg_mentor_intelligence -f scripts\setup_db_role.sql
-- Then set the role password interactively (not stored in any file or shell history):
--   & "D:\postgre\bin\psql.exe" -U postgres -h localhost -p 5432 -d marg_mentor_intelligence -c "\password marg_mie_app"
-- This script does not touch any other database.

\set ON_ERROR_STOP on

DO $$
BEGIN
  IF current_database() <> 'marg_mentor_intelligence' THEN
    RAISE EXCEPTION 'Wrong database: connected to %, expected marg_mentor_intelligence', current_database();
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'marg_mie_app') THEN
    CREATE ROLE marg_mie_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION;
  END IF;
END $$;

GRANT CONNECT, TEMPORARY ON DATABASE marg_mentor_intelligence TO marg_mie_app;
CREATE SCHEMA IF NOT EXISTS mie AUTHORIZATION marg_mie_app;
CREATE SCHEMA IF NOT EXISTS mie_test AUTHORIZATION marg_mie_app;
ALTER ROLE marg_mie_app IN DATABASE marg_mentor_intelligence SET search_path = mie;

SELECT current_database() AS database, 'marg_mie_app ready; now set its password with \password' AS next_step;
