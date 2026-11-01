#!/bin/bash
# Runs once on first start of an empty data volume. Creates separate
# databases and least-privilege roles for the backend and Mentor Intelligence
# (the two AI systems never share a database).
set -euo pipefail

psql -v ON_ERROR_STOP=1 --username postgres <<-SQL
	CREATE ROLE marg_app LOGIN PASSWORD '${MARG_DB_PASSWORD}';
	CREATE DATABASE marg_db OWNER marg_app;
	CREATE ROLE marg_mie_app LOGIN PASSWORD '${MIE_DB_PASSWORD}' NOSUPERUSER NOCREATEDB NOCREATEROLE;
	CREATE DATABASE marg_mentor_intelligence;
	REVOKE ALL ON DATABASE marg_db FROM PUBLIC;
	REVOKE ALL ON DATABASE marg_mentor_intelligence FROM PUBLIC;
SQL

psql -v ON_ERROR_STOP=1 --username postgres --dbname marg_mentor_intelligence <<-SQL
	GRANT CONNECT, TEMPORARY ON DATABASE marg_mentor_intelligence TO marg_mie_app;
	CREATE SCHEMA IF NOT EXISTS mie AUTHORIZATION marg_mie_app;
	ALTER ROLE marg_mie_app IN DATABASE marg_mentor_intelligence SET search_path = mie;
SQL
