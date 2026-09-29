"""PostgreSQL backend that survives transient DNS/network blips.

The Supabase pooler is reached by hostname, so a momentary failure of the local
resolver (router DNS hiccup, Wi-Fi reconnect, VPN flap) makes psycopg2 raise
`could not translate host name ... to address`. Without this wrapper that single
`getaddrinfo` failure crashes `runserver` during its startup migration check and
kills every in-flight request with a 500, even though the credentials and the
database are perfectly healthy a second later.

Retrying with a short backoff inside `get_new_connection` keeps those blips
invisible. Auth and config errors (bad password, missing database) are still
raised immediately -- retrying those would only slow down a real misconfiguration.
"""

import socket
import time

import psycopg2
from django.db.backends.postgresql.base import DatabaseWrapper as PostgresWrapper

# Substrings that mark a failure as worth retrying: the host could not be
# resolved, the packet was refused/lost, or the server dropped the socket.
RETRYABLE_MARKERS = (
    'name or service not known',
    'nodename nor servname',
    'temporary failure in name resolution',
    'getaddrinfo',
    'could not translate host name',
    'connection refused',
    'connection reset',
    'connection timed out',
    'timeout expired',
    'no route to host',
    'network is unreachable',
    'server closed the connection',
    'ssl connection has been closed',
    'terminating connection',
)

# Defaults are intentionally short: a DNS answer usually lands within ~1s, and
# blocking a worker for longer than that is worse than surfacing the error.
DEFAULT_ATTEMPTS = 4
DEFAULT_BACKOFF = 0.5


def _is_retryable(exc):
    """True when `exc` is a transient DNS/socket problem rather than a config error."""
    if isinstance(exc, socket.gaierror):
        return True
    if not isinstance(exc, psycopg2.OperationalError):
        return False
    message = str(exc).lower()
    return any(marker in message for marker in RETRYABLE_MARKERS)


class DatabaseWrapper(PostgresWrapper):
    def get_new_connection(self, conn_params):
        attempts = int(self.settings_dict.get('CONNECT_ATTEMPTS') or DEFAULT_ATTEMPTS)
        backoff = float(self.settings_dict.get('CONNECT_BACKOFF', DEFAULT_BACKOFF))

        for attempt in range(1, max(attempts, 1) + 1):
            try:
                return super().get_new_connection(conn_params)
            except (psycopg2.OperationalError, socket.gaierror) as exc:
                if attempt >= attempts or not _is_retryable(exc):
                    raise
                time.sleep(backoff * attempt)

    def ensure_connection(self):
        """Reconnect when the server has dropped the socket.

        Django's base implementation only reconnects when ``self.connection is
        None``. That is not enough here: psycopg2 keeps the Python connection
        object alive after the *server* closes it, and a Supabase pooler does
        exactly that on its idle timeout. ``self.connection`` is therefore not
        None, so Django hands the dead object straight to the next query and
        every request fails with ``InterfaceError: connection already closed``
        until the process is restarted.

        Treating a closed connection as no connection fixes both that and the
        ``TransactionTestCase`` paths, which deliberately close connections
        mid-suite and used to leave the suite failing at random.
        """
        if self.connection is not None and self.connection.closed:
            if self.in_atomic_block:
                # Reopening inside an atomic block would silently abandon the
                # in-flight transaction, so fall through and let Django raise its
                # own ProgrammingError rather than corrupt the block.
                return super().ensure_connection()
            self.close()
        return super().ensure_connection()
