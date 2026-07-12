CREATE ROLE soc_ot_runtime LOGIN PASSWORD 'runtime_local';
CREATE ROLE soc_ot_outcome LOGIN PASSWORD 'outcome_local';

CREATE SCHEMA IF NOT EXISTS observable AUTHORIZATION soc_ot_admin;
CREATE SCHEMA IF NOT EXISTS hidden AUTHORIZATION soc_ot_admin;
CREATE SCHEMA IF NOT EXISTS audit AUTHORIZATION soc_ot_admin;

GRANT CONNECT ON DATABASE soc_ot TO soc_ot_runtime, soc_ot_outcome;
GRANT USAGE ON SCHEMA observable, audit TO soc_ot_runtime;
GRANT USAGE ON SCHEMA observable, hidden, audit TO soc_ot_outcome;

ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA observable
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO soc_ot_runtime, soc_ot_outcome;
ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA hidden
  GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO soc_ot_outcome;
ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA audit
  GRANT SELECT, INSERT ON TABLES TO soc_ot_runtime, soc_ot_outcome;
ALTER DEFAULT PRIVILEGES FOR ROLE soc_ot_admin IN SCHEMA observable, hidden, audit
  GRANT USAGE, SELECT ON SEQUENCES TO soc_ot_runtime, soc_ot_outcome;

