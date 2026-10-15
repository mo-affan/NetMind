"""M6 Network State Database (SQLite).

Every analysis is saved as a "run" (one capture, pcap file, demo or NS2 trace).
Tables hold the run's traffic summary, per-window metrics, anomaly results,
topology and flows, so the dashboard and the Copilot can compare runs and look
back in time.
"""
from __future__ import annotations

import json
import os
import sqlite3
import time
from pathlib import Path

import pandas as pd

# Paths are anchored to the repository, not the current folder, so commands behave the same
# from any directory. NETMIND_DB overrides the database location.
REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DEFAULT_DB = Path(os.environ.get("NETMIND_DB", DATA_DIR / "netmind.db"))

TABLES = ["metrics", "anomalies", "incidents", "nodes", "links", "flows", "protocols", "rtt"]


class NetMindDB:
    def __init__(self, path: str | Path = DEFAULT_DB):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, check_same_thread=False)
        self.conn.execute("""CREATE TABLE IF NOT EXISTS runs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT, source TEXT, created REAL, summary TEXT)""")
        self.conn.commit()

    # ---- runs ---------------------------------------------------------------
    def new_run(self, name: str, source: str, summary: dict | None = None) -> int:
        cur = self.conn.execute("INSERT INTO runs (name, source, created, summary) VALUES (?,?,?,?)",
                                (name, source, time.time(), json.dumps(summary or {})))
        self.conn.commit()
        return int(cur.lastrowid)

    def update_summary(self, run_id: int, summary: dict) -> None:
        self.conn.execute("UPDATE runs SET summary=? WHERE id=?", (json.dumps(summary), run_id))
        self.conn.commit()

    def runs(self) -> pd.DataFrame:
        return pd.read_sql("SELECT id, name, source, created FROM runs ORDER BY id DESC", self.conn)

    def run(self, run_id: int) -> dict:
        row = self.conn.execute("SELECT id, name, source, created, summary FROM runs WHERE id=?",
                                (run_id,)).fetchone()
        if row is None:
            raise KeyError(f"no run {run_id}")
        return {"id": row[0], "name": row[1], "source": row[2], "created": row[3],
                "summary": json.loads(row[4] or "{}")}

    def latest_run_id(self) -> int | None:
        row = self.conn.execute("SELECT MAX(id) FROM runs").fetchone()
        return row[0]

    # ---- tables ---------------------------------------------------------------
    def save(self, table: str, run_id: int, df: pd.DataFrame) -> None:
        if table not in TABLES:
            raise ValueError(f"unknown table {table}")
        if df is None or df.empty:
            return
        out = df.copy()
        for c in out.columns:  # lists/dicts -> JSON text
            if out[c].map(lambda v: isinstance(v, (list, dict))).any():
                out[c] = out[c].map(json.dumps)
        out.insert(0, "run_id", run_id)
        # different sources (packets vs NS2) produce different columns: add any missing ones
        existing = {r[1] for r in self.conn.execute(f"PRAGMA table_info({table})")}
        if existing:
            for c in out.columns:
                if c not in existing:
                    self.conn.execute(f'ALTER TABLE {table} ADD COLUMN "{c}"')
        out.to_sql(table, self.conn, if_exists="append", index=False)
        self.conn.commit()

    def load(self, table: str, run_id: int) -> pd.DataFrame:
        if table not in TABLES:
            raise ValueError(f"unknown table {table}")
        try:
            df = pd.read_sql(f"SELECT * FROM {table} WHERE run_id=?", self.conn, params=(run_id,))
        except (sqlite3.OperationalError, pd.errors.DatabaseError):
            return pd.DataFrame()
        return df.drop(columns=["run_id"]).dropna(axis=1, how="all")

    def delete_run(self, run_id: int) -> None:
        for t in TABLES:
            try:
                self.conn.execute(f"DELETE FROM {t} WHERE run_id=?", (run_id,))
            except sqlite3.OperationalError:
                pass
        self.conn.execute("DELETE FROM runs WHERE id=?", (run_id,))
        self.conn.commit()

    def close(self) -> None:
        self.conn.close()
