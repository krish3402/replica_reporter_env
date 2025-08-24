# Replica Reporter (env-configured)

This module offloads heavy read-only reports to a Postgres replica using environment variables for config.

## Environment variables (set these for the Odoo process)

Required:
- ODOO_REPLICA_HOST        (e.g. pool-replica.example.internal or replica host)
- ODOO_REPLICA_USER        (read-only user)
- ODOO_REPLICA_PASS        (password for read-only user)

Optional (defaults provided):
- ODOO_REPLICA_PORT=5432
- ODOO_REPLICA_DB=odoo
- ODOO_REPLICA_SSLMODE=require
- ODOO_REPLICA_SSLROOTCERT=/path/to/ca.pem  (optional, for strict verification)
- ODOO_REPLICA_MAX_LAG=5    (seconds; fallback to primary if lag greater)

## Usage
1. Copy `replica_reporter_env` into your Odoo `addons` directory.
2. Restart Odoo.
3. Update Apps list and install "Replica Reporter (Env-configured)".
4. Configure environment variables in your system (systemd, docker-compose, kubernetes secrets, etc).
5. Test from Odoo shell:



6. Enable the cron (disabled by default) after verifying behavior.

## Security
- Keep read-only credentials out of Odoo DB; store them in env vars, secrets manager, or container secrets.
- Ensure `report_user` has only SELECT privileges.

## Notes
- This module only performs SELECTs on the replica connection.
- If the replica is unavailable or lag is too high, the module falls back to the ORM (primary).


