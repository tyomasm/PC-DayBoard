import argparse
import json
import math
import sqlite3
import threading
import time
import webbrowser
from datetime import datetime
from email.utils import parsedate_to_datetime
from pathlib import Path

import requests
from caldav.lib.error import AuthorizationError
from flask import Flask, abort, jsonify, request, send_from_directory
from waitress import create_server

from providers import DATA, JST, SetupNeeded, CalendarFailure, agenda, news, setup, weather

ROOT = Path(__file__).resolve().parent
ADDRESS = "http://127.0.0.1:8766"
SOURCES = {"weather": (weather, 30, 0), "news": (news, 30, 5), "agenda": (agenda, 5, 0)}
app = Flask(__name__, static_folder="live", static_url_path="/assets")


def next_slot(stamp, minutes, offset):
    period = minutes * 60
    return ((int(stamp) - offset * 60) // period + 1) * period + offset * 60


def db():
    return sqlite3.connect(DATA / "cache.sqlite3", timeout=10)


def initialize():
    DATA.mkdir(parents=True, exist_ok=True)
    with db() as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS cache (name TEXT PRIMARY KEY, day TEXT, stamp REAL, payload TEXT, status TEXT)")


def snapshot():
    today = datetime.now(JST).date().isoformat()
    result = {name: dict(data=None, stamp=None, status="取得中") for name in SOURCES}
    with db() as conn:
        for name, day, stamp, payload, status in conn.execute("SELECT * FROM cache"):
            if name == "agenda" and day != today:
                continue
            result[name] = dict(data=json.loads(payload) if payload else None, stamp=stamp, status=status)
    return result


def retry_delay(header, stamp):
    try:
        return max(1, int(header))
    except (ValueError, TypeError):
        try:
            return max(1, parsedate_to_datetime(header).timestamp() - stamp)
        except (ValueError, TypeError, AttributeError):
            return 1800


def worker(name):
    fetch, minutes, offset = SOURCES[name]
    due = 0  # Revalidate even a recently cached result after restart or upgrade.
    failures = 0
    while True:
        stamp = time.time()
        if stamp < due:
            time.sleep(min(2, due - stamp))
            continue
        now = datetime.fromtimestamp(stamp, JST)
        day = now.date().isoformat()
        due = next_slot(stamp, minutes, offset)
        blocked = False
        try:
            payload = json.dumps(fetch(now), ensure_ascii=False, allow_nan=False)
            with db() as conn:
                previous = conn.execute("SELECT payload FROM cache WHERE name=?", (name,)).fetchone()
                status = "変更なし" if previous and previous[0] == payload else "内容更新"
                conn.execute("INSERT OR REPLACE INTO cache VALUES(?,?,?,?,?)",
                             (name, day, time.time(), payload, status))
            failures = 0
            continue
        except (SetupNeeded, AuthorizationError) as exc:
            status = "設定が必要" if isinstance(exc, SetupNeeded) else "認証エラー"
            blocked = name == "agenda"
        except Exception as exc:
            response = getattr(exc, "response", None)
            status = str(exc) if isinstance(exc, CalendarFailure) else "更新失敗"
            failures += 1
            if response is not None and response.status_code == 429:
                due = stamp + retry_delay(response.headers.get("Retry-After"), stamp)
            elif failures <= 2:
                due = min(due, stamp + (60 if failures == 1 else 300))
        with db() as conn:
            if name == "agenda":
                conn.execute("DELETE FROM cache WHERE name=? AND day<>?", (name, day))
            conn.execute("INSERT INTO cache VALUES(?,?,NULL,NULL,?) ON CONFLICT(name) DO UPDATE SET status=excluded.status",
                         (name, day, status))
        if blocked:
            # Do not retry authentication until configuration changes.
            config = DATA / "config.toml"
            modified = config.stat().st_mtime_ns if config.exists() else None
            while (config.stat().st_mtime_ns if config.exists() else None) == modified:
                if datetime.now(JST).date().isoformat() != day:
                    day = datetime.now(JST).date().isoformat()
                    with db() as conn:
                        conn.execute("INSERT OR REPLACE INTO cache VALUES(?,?,NULL,NULL,?)", (name, day, status))
                time.sleep(2)
            due = 0


@app.before_request
def local_only():
    if request.host.split(":")[0] not in {"localhost", "127.0.0.1"}:
        abort(403)


@app.after_request
def private(response):
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Frame-Options"] = "DENY"
    return response


@app.get("/")
def index():
    return send_from_directory(ROOT / "live", "index.html")


@app.get("/health")
def health():
    return "Dayboard/1"


@app.post("/api/weather/location")
def location_weather():
    if request.headers.get("Origin") != request.host_url.rstrip("/"):
        abort(403)
    point = request.get_json()
    coords = []
    for key, limit in (("latitude", 90), ("longitude", 180)):
        value = point.get(key) if isinstance(point, dict) else None
        if type(value) not in (int, float) or not -limit <= value <= limit or not math.isfinite(value):
            abort(400)
        coords.append(round(value, 2))
    try:
        forecast = weather(datetime.now(JST), *coords)
    except (requests.RequestException, ValueError, KeyError, TypeError, IndexError):
        return jsonify(error="現在地の予報を取得できません"), 502
    return jsonify(data=forecast, stamp=time.time(), status="取得成功")


@app.get("/api/dashboard")
def dashboard():
    return jsonify(snapshot())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--setup", action="store_true")
    args = parser.parse_args()
    if args.setup:
        try:
            setup()
        except (ValueError, AuthorizationError):
            parser.exit(1, "設定を保存できませんでした。認証情報とカレンダー番号を確認してください。\n")
        except Exception:
            parser.exit(1, "iCloud接続または資格情報の保存に失敗しました。接続・資格情報ストアを確認してください。\n")
        initialize()
        with db() as conn:
            conn.execute("DELETE FROM cache WHERE name='agenda'")
        print("保存しました。Dayboardを再起動してください。")
        return
    try:
        server = create_server(app, host="127.0.0.1", port=8766)
    except OSError:
        if requests.get(ADDRESS + "/health", timeout=3).text != "Dayboard/1":
            raise
        if not args.no_browser:
            webbrowser.open(ADDRESS)
        return
    initialize()
    for name in SOURCES:
        threading.Thread(target=worker, args=(name,), daemon=True).start()
    if not args.no_browser:
        webbrowser.open(ADDRESS)
    server.run()


if __name__ == "__main__":
    main()
