import logging
import os
from odoo import models, api, fields, exceptions
import psycopg2
from psycopg2.extras import RealDictCursor

_logger = logging.getLogger(__name__)

# Env var names (all optional except USER/PASS/HOST)
EV_REPLICA_HOST = "ODOO_REPLICA_HOST"
EV_REPLICA_PORT = "ODOO_REPLICA_PORT"
EV_REPLICA_DB = "ODOO_REPLICA_DB"
EV_REPLICA_USER = "ODOO_REPLICA_USER"
EV_REPLICA_PASS = "ODOO_REPLICA_PASS"
EV_REPLICA_SSLMODE = "ODOO_REPLICA_SSLMODE"        # e.g., require
EV_REPLICA_SSLROOTCERT = "ODOO_REPLICA_SSLROOTCERT"
EV_REPLICA_MAX_LAG = "ODOO_REPLICA_MAX_LAG"        # seconds


def _get_env(key, default=None):
    v = os.getenv(key, default)
    if v is not None and isinstance(v, str):
        v = v.strip()
    return v


def _build_dsn_from_env():
    host = _get_env(EV_REPLICA_HOST)
    port = _get_env(EV_REPLICA_PORT, "5432")
    db = _get_env(EV_REPLICA_DB, "odoo")
    user = _get_env(EV_REPLICA_USER)
    passwd = _get_env(EV_REPLICA_PASS)
    sslmode = _get_env(EV_REPLICA_SSLMODE, "require")
    sslroot = _get_env(EV_REPLICA_SSLROOTCERT)

    if not host or not user or passwd is None:
        # intentionally return None if required pieces missing
        return None

    dsn = f"host={host} port={port} dbname={db} user={user} password={passwd} sslmode={sslmode}"
    if sslroot:
        dsn += f" sslrootcert={sslroot}"
    return dsn


def _get_max_lag_from_env():
    v = _get_env(EV_REPLICA_MAX_LAG, "5")
    try:
        return int(v)
    except Exception:
        return 5


def _get_replica_lag_seconds(conn):
    # Returns integer seconds or None
    with conn.cursor() as cur:
        cur.execute("SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp()))::int AS lag_seconds;")
        row = cur.fetchone()
        if not row:
            return None
        return int(row[0]) if row[0] is not None else None


class ReplicaReportRunner(models.Model):
    _name = 'replica.report.runner'
    _description = 'Run heavy read-only reports on replica (env-config)'

    name = fields.Char(string="Name")

    @api.model
    def _connect_to_replica(self):
        dsn = _build_dsn_from_env()
        if not dsn:
            _logger.warning("Replica DSN environment variables are not fully configured.")
            return None
        try:
            conn = psycopg2.connect(dsn)
            return conn
        except Exception as e:
            _logger.warning("Could not connect to replica: %s", e)
            return None

    @api.model
    def run_heavy_partner_report(self, limit=200):
        """
        Example heavy report: aggregate posted invoice totals per partner, limit to `limit`.
        Attempts to run on replica; if unavailable or lag too high, falls back to primary via ORM.
        Returns list of dicts: [{id, name, total}, ...]
        """
        max_lag = _get_max_lag_from_env()
        conn = self._connect_to_replica()
        if not conn:
            _logger.info("Replica not available - running report on primary (ORM).")
            return self._run_on_primary(limit)

        try:
            lag = _get_replica_lag_seconds(conn)
            if lag is None:
                _logger.warning("Replica lag unknown - using primary.")
                return self._run_on_primary(limit)
            if lag > max_lag:
                _logger.info("Replica lag %s s > %s s - using primary.", lag, max_lag)
                return self._run_on_primary(limit)

            _logger.info("Running report on replica (lag %s s <= %s s).", lag, max_lag)
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT rp.id, rp.name, COALESCE(SUM(inv.amount_total),0) AS total
                    FROM res_partner rp
                    LEFT JOIN account_move inv ON inv.partner_id = rp.id AND inv.state = 'posted'
                    GROUP BY rp.id, rp.name
                    ORDER BY total DESC
                    LIMIT %s
                    """,
                    (limit,)
                )
                rows = cur.fetchall()
                return [dict(r) for r in rows]
        except Exception as e:
            _logger.exception("Error running report on replica, falling back to primary: %s", e)
            return self._run_on_primary(limit)
        finally:
            try:
                conn.close()
            except Exception:
                pass

    def _run_on_primary(self, limit):
        # ORM fallback (safe, slower)
        partners = self.env['res.partner'].search([], limit=limit)
        out = []
        for p in partners:
            total = sum(inv.amount_total for inv in p.invoice_ids.filtered(lambda i: i.state == 'posted'))
            out.append({'id': p.id, 'name': p.name, 'total': float(total)})
        return out
