from __future__ import annotations

import hashlib
import json
import sqlite3
from contextlib import contextmanager
from datetime import date, datetime, timezone
from pathlib import Path

from .models import Prediction, VerificationResult


def make_cache_key(*, provider: str, model: str, purpose: str, system_prompt: str, user_prompt: str, prompt_version: str) -> str:
    raw = json.dumps([provider, model, purpose, system_prompt, user_prompt, prompt_version], ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class RadarRepository:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema()

    @contextmanager
    def connect(self):
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        db.execute("PRAGMA busy_timeout=5000")
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    def _init_schema(self):
        with self.connect() as db:
            db.execute("PRAGMA journal_mode=WAL")
            db.executescript("""
            CREATE TABLE IF NOT EXISTS runs(
              id TEXT PRIMARY KEY, started_at TEXT NOT NULL, finished_at TEXT,
              model TEXT NOT NULL, prompt_version TEXT NOT NULL,
              status TEXT NOT NULL, metrics_json TEXT NOT NULL DEFAULT '{}');
            CREATE TABLE IF NOT EXISTS cache(
              key TEXT PRIMARY KEY, value_json TEXT NOT NULL,
              created_at TEXT NOT NULL, expires_at TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS predictions(
              id TEXT PRIMARY KEY, run_id TEXT NOT NULL REFERENCES runs(id),
              created_at TEXT NOT NULL, base_session TEXT NOT NULL, target_session TEXT NOT NULL,
              horizon_days INTEGER NOT NULL, target TEXT NOT NULL, direction TEXT NOT NULL,
              probability REAL NOT NULL, thesis TEXT NOT NULL, invalidation TEXT NOT NULL,
              sensors_json TEXT NOT NULL, evidence_json TEXT NOT NULL,
              base_asset REAL, base_benchmark REAL, model TEXT NOT NULL,
              prompt_version TEXT NOT NULL, frozen_hash TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS verification(
              prediction_id TEXT PRIMARY KEY REFERENCES predictions(id), verified_at TEXT NOT NULL,
              correct INTEGER NOT NULL, asset_return REAL NOT NULL, benchmark_return REAL,
              excess_return REAL, max_adverse REAL NOT NULL, brier REAL NOT NULL);
            """)

    def start_run(self, run_id: str, model: str, prompt_version: str):
        with self.connect() as db:
            db.execute("INSERT INTO runs(id,started_at,model,prompt_version,status) VALUES(?,?,?,?,?)",
                       (run_id, datetime.now(timezone.utc).isoformat(), model, prompt_version, "RUNNING"))

    def finish_run(self, run_id: str, status: str, metrics: dict):
        with self.connect() as db:
            db.execute("UPDATE runs SET finished_at=?,status=?,metrics_json=? WHERE id=?",
                       (datetime.now(timezone.utc).isoformat(), status, json.dumps(metrics), run_id))

    def get_run(self, run_id: str):
        with self.connect() as db:
            row = db.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
        return dict(row) if row else None

    def freeze_prediction(self, p: Prediction) -> bool:
        values = (
            p.id, p.run_id, p.created_at.isoformat(), p.base_session.isoformat(), p.target_session.isoformat(),
            p.horizon_days, p.target, p.direction, p.probability, p.thesis, p.invalidation,
            json.dumps(p.sensors), json.dumps(p.evidence_ids), p.base_asset, p.base_benchmark,
            p.model, p.prompt_version, p.frozen_hash,
        )
        with self.connect() as db:
            cur = db.execute("INSERT OR IGNORE INTO predictions VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)", values)
            return cur.rowcount == 1

    def get_prediction(self, prediction_id: str) -> Prediction | None:
        with self.connect() as db:
            row = db.execute("SELECT * FROM predictions WHERE id=?", (prediction_id,)).fetchone()
        if not row:
            return None
        return Prediction(
            id=row["id"], run_id=row["run_id"], created_at=datetime.fromisoformat(row["created_at"]),
            base_session=datetime.fromisoformat(row["base_session"]).date(), target_session=datetime.fromisoformat(row["target_session"]).date(),
            horizon_days=row["horizon_days"], target=row["target"], direction=row["direction"], probability=row["probability"],
            thesis=row["thesis"], invalidation=row["invalidation"], sensors=tuple(json.loads(row["sensors_json"])),
            evidence_ids=tuple(json.loads(row["evidence_json"])), base_asset=row["base_asset"], base_benchmark=row["base_benchmark"],
            model=row["model"], prompt_version=row["prompt_version"], frozen_hash=row["frozen_hash"],
        )

    def cache_set(self, key: str, value: object, *, expires_at: datetime):
        with self.connect() as db:
            db.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?)", (
                key, json.dumps(value, ensure_ascii=False), datetime.now(timezone.utc).isoformat(), expires_at.isoformat()))

    def cache_get(self, key: str, *, now: datetime):
        with self.connect() as db:
            row = db.execute("SELECT value_json,expires_at FROM cache WHERE key=?", (key,)).fetchone()
        if not row or datetime.fromisoformat(row["expires_at"]) <= now:
            return None
        return json.loads(row["value_json"])

    def due_predictions(self, today: date) -> list[Prediction]:
        with self.connect() as db:
            ids = [row[0] for row in db.execute(
                """SELECT p.id FROM predictions p
                   LEFT JOIN verification v ON v.prediction_id=p.id
                   WHERE v.prediction_id IS NULL AND p.target_session<=?
                   ORDER BY p.target_session,p.id""",
                (today.isoformat(),),
            )]
        return [p for pid in ids if (p := self.get_prediction(pid)) is not None]

    def save_verification(self, prediction_id: str, result: VerificationResult) -> bool:
        with self.connect() as db:
            cur = db.execute(
                "INSERT OR IGNORE INTO verification VALUES(?,?,?,?,?,?,?,?)",
                (prediction_id, datetime.now(timezone.utc).isoformat(), int(result.correct),
                 result.asset_return, result.benchmark_return, result.excess_return,
                 result.max_adverse, result.brier),
            )
            return cur.rowcount == 1
