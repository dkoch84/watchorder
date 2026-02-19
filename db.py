"""Shared MySQL storage for watchorder collections config.

Reads MySQL connection details from Kodi's advancedsettings.xml (videodatabase
section).  Falls back silently when mysql.connector is unavailable, MySQL is not
configured, or the server is unreachable.
"""

import json
import xml.etree.ElementTree as ET

import xbmc
import xbmcvfs

_ADDON_ID = "plugin.video.watchorder"

# Module-level caches (reset each plugin invocation)
_mysql_settings = None
_mysql_settings_parsed = False
_connection = None
_warned = False


def get_mysql_settings():
    """Return dict with host/port/user/pass from advancedsettings.xml, or None."""
    global _mysql_settings, _mysql_settings_parsed
    if _mysql_settings_parsed:
        return _mysql_settings
    _mysql_settings_parsed = True

    path = xbmcvfs.translatePath("special://userdata/advancedsettings.xml")
    try:
        tree = ET.parse(path)
    except Exception:
        return None

    vdb = tree.getroot().find("videodatabase")
    if vdb is None:
        return None

    host = vdb.findtext("host")
    if not host:
        return None

    _mysql_settings = {
        "host": host,
        "port": int(vdb.findtext("port", "3306")),
        "user": vdb.findtext("user", "kodi"),
        "password": vdb.findtext("pass", ""),
    }
    return _mysql_settings


def _ensure_schema(conn):
    """Create the watchorder database and config table if missing."""
    cur = conn.cursor()
    cur.execute(
        "CREATE DATABASE IF NOT EXISTS `watchorder`"
        " CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cur.execute("USE `watchorder`")
    cur.execute(
        "CREATE TABLE IF NOT EXISTS `config` ("
        "  id INT NOT NULL DEFAULT 1,"
        "  config_json MEDIUMTEXT NOT NULL,"
        "  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
        "    ON UPDATE CURRENT_TIMESTAMP,"
        "  PRIMARY KEY (id),"
        "  CHECK (id = 1)"
        ") ENGINE=InnoDB"
    )
    conn.commit()
    cur.close()


def _shared_collections_enabled():
    """Check if shared collections setting is enabled."""
    import xbmcaddon
    try:
        return xbmcaddon.Addon(_ADDON_ID).getSetting("shared_collections") == "true"
    except Exception:
        return False


def _get_connection():
    """Return a MySQL connection, or None if unavailable."""
    global _connection, _warned

    if not _shared_collections_enabled():
        return None

    try:
        import mysql.connector  # noqa: F401 — from script.module.myconnpy
    except ImportError:
        return None

    settings = get_mysql_settings()
    if not settings:
        return None

    # Reuse cached connection if still alive
    if _connection is not None:
        try:
            _connection.ping(reconnect=True, attempts=1, delay=0)
            _connection.database = "watchorder"
            return _connection
        except Exception:
            _connection = None

    try:
        _connection = mysql.connector.connect(
            host=settings["host"],
            port=settings["port"],
            user=settings["user"],
            password=settings["password"],
            connection_timeout=3,
        )
        _ensure_schema(_connection)
        _connection.database = "watchorder"
        return _connection
    except Exception as e:
        if not _warned:
            _warned = True
            xbmc.log(
                "{}: MySQL unavailable, using local JSON: {}".format(_ADDON_ID, e),
                xbmc.LOGWARNING,
            )
        _connection = None
        return None


def db_load_config():
    """Load config dict from MySQL, or return None on any failure."""
    conn = _get_connection()
    if conn is None:
        return None
    try:
        cur = conn.cursor()
        cur.execute("SELECT config_json FROM config WHERE id = 1")
        row = cur.fetchone()
        cur.close()
        if row is None:
            return None
        return json.loads(row[0])
    except Exception as e:
        xbmc.log(
            "{}: MySQL read failed: {}".format(_ADDON_ID, e),
            xbmc.LOGWARNING,
        )
        return None


def get_linked_movie_ids(tvshowid):
    """Get movie IDs linked to a TV show from Kodi's video database."""
    # Try MySQL first
    settings = get_mysql_settings()
    if settings:
        try:
            import mysql.connector
            conn = mysql.connector.connect(
                host=settings["host"],
                port=settings["port"],
                user=settings["user"],
                password=settings["password"],
                connection_timeout=3,
            )
            cur = conn.cursor()
            cur.execute("SHOW DATABASES LIKE 'MyVideos%'")
            dbs = [row[0] for row in cur.fetchall()]
            if dbs:
                video_db = sorted(dbs)[-1]
                cur.execute(
                    ("SELECT idMovie FROM `{}`.movielinktvshow"
                     " WHERE idShow = %s").format(video_db),
                    (tvshowid,),
                )
                ids = [row[0] for row in cur.fetchall()]
                cur.close()
                conn.close()
                return ids
            cur.close()
            conn.close()
        except Exception as e:
            xbmc.log(
                "{}: get_linked_movie_ids MySQL error: {}".format(
                    _ADDON_ID, e),
                xbmc.LOGWARNING,
            )

    # Fall back to SQLite
    try:
        import sqlite3
        db_dir = xbmcvfs.translatePath("special://database/")
        _, files = xbmcvfs.listdir(db_dir)
        video_dbs = sorted(
            f for f in files
            if f.startswith("MyVideos") and f.endswith(".db")
        )
        if not video_dbs:
            return []
        db_path = db_dir + video_dbs[-1]
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT idMovie FROM movielinktvshow WHERE idShow = ?",
            (tvshowid,),
        )
        ids = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()
        return ids
    except Exception:
        return []


def db_save_config(config):
    """Save config dict to MySQL.  Best-effort — failures are logged, not raised."""
    conn = _get_connection()
    if conn is None:
        return
    try:
        blob = json.dumps(config, indent=4)
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO config (id, config_json) VALUES (1, %s)"
            " ON DUPLICATE KEY UPDATE config_json = VALUES(config_json)",
            (blob,),
        )
        conn.commit()
        cur.close()
    except Exception as e:
        xbmc.log(
            "{}: MySQL write failed: {}".format(_ADDON_ID, e),
            xbmc.LOGWARNING,
        )
