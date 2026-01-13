from __future__ import annotations

import importlib
import sqlite3

import pytest


@pytest.mark.unit
def test_import_package() -> None:
    importlib.import_module("dijon")


@pytest.mark.unit
def test_import_cli_main() -> None:
    importlib.import_module("dijon.cli.main")


@pytest.mark.integration
def test_sqlite_smoke(db_conn: sqlite3.Connection) -> None:
    db_conn.execute("CREATE TABLE IF NOT EXISTS smoke (id INTEGER PRIMARY KEY, x TEXT NOT NULL);")
    db_conn.execute("INSERT INTO smoke (x) VALUES ('ok');")
    rows = db_conn.execute("SELECT x FROM smoke;").fetchall()
    assert rows == [("ok",)]