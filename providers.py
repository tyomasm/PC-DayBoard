"""Read-only providers. Timestamps sent to the browser are Unix seconds."""
import json
import os
import re
import unicodedata
import tomllib
from datetime import date, datetime, time, timedelta
from email.utils import parsedate_to_datetime
from getpass import getpass
from pathlib import Path
from urllib.parse import urlsplit
from xml.etree import ElementTree
from zoneinfo import ZoneInfo

import caldav
import keyring
import requests
from caldav.lib.error import AuthorizationError, DAVError

JST = ZoneInfo("Asia/Tokyo")
DATA = Path(os.environ.get("DAYBOARD_DATA") or Path(os.environ.get("LOCALAPPDATA", Path.home())) / "PC-DayBoard")
SETTINGS = Path(__file__).with_name("settings.toml")


def preferences():
    return tomllib.loads(SETTINGS.read_text(encoding="utf-8-sig")) if SETTINGS.is_file() else {}



class CalendarFailure(Exception):
    """Safe stage and exception type only; never include the DAV URL or event text."""


class SetupNeeded(Exception):
    pass


def weather(now, latitude=None, longitude=None):
    if latitude is None:
        config = preferences()
        latitude, longitude = config.get("latitude"), config.get("longitude")
        if latitude is None or longitude is None:
            raise SetupNeeded()
        if not (-90 <= latitude <= 90 and -180 <= longitude <= 180):
            raise ValueError("予報地点の設定を確認してください")
    fields = "temperature_2m,weather_code"
    response = requests.get("https://api.open-meteo.com/v1/forecast", params={
        "latitude": latitude, "longitude": longitude, "timezone": "Asia/Tokyo",
        "wind_speed_unit": "ms", "forecast_days": 2, "hourly": fields,
        "current": fields + ",relative_humidity_2m,wind_speed_10m,wind_direction_10m",
        "daily": "temperature_2m_max,temperature_2m_min",
    }, timeout=10)
    response.raise_for_status()
    data = response.json()
    index = data["daily"]["time"].index(now.date().isoformat())
    hourly = data["hourly"]
    forecast = []
    for stamp, temp, code in zip(hourly["time"], hourly["temperature_2m"], hourly["weather_code"]):
        when = datetime.fromisoformat(stamp).replace(tzinfo=JST)
        if when >= now.replace(second=0, microsecond=0) and when.hour % 3 == 0:
            forecast.append([when.isoformat(), round(temp), code])
    return dict(current=data["current"], high=data["daily"]["temperature_2m_max"][index],
                low=data["daily"]["temperature_2m_min"][index], forecast=forecast[:6])


FX_TERMS = ("為替", "円相場", "ドル円", "ドル/円", "ドル・円", "円安", "円高", "NY円", "東京円",
            "ロンドン円", "ユーロ円", "ドル高", "ドル安", "ドル指数", "ユーロ高", "ユーロ安")
STOCK_TERMS = ("株式", "株価", "日経平均", "東証", "NY株", "米株", "米国株", "日本株",
               "欧州株", "東京株", "個別株", "株主優待", "自社株", "ダウ平均", "NYダウ",
               "ナスダック", "NASDAQ", "TOPIX", "S&P500")


def classify_headline(title):
    # Ignore the publisher suffix Yahoo appends, and unify full-width Latin text.
    headline = unicodedata.normalize("NFKC", title).upper()
    headline = re.sub(r"\([^()]*\)$", "", headline)
    if any(term in headline for term in FX_TERMS):
        return "為替"
    if any(term in headline for term in STOCK_TERMS):
        return "株式"
    return "経済"


def parse_news(xml, now):
    channel = ElementTree.fromstring(xml).find("channel")
    if channel is None:
        raise ValueError("Invalid RSS")
    articles = {}
    for item in channel.findall("item"):
        title = (item.findtext("title") or "").strip()
        url = item.findtext("link") or ""
        try:
            stamp = parsedate_to_datetime(item.findtext("pubDate")).timestamp()
        except (ValueError, TypeError, AttributeError):
            continue
        if not title or urlsplit(url).scheme != "https" or not 0 <= now.timestamp()-stamp < 172800:
            continue
        articles[url] = dict(title=title, url=url, stamp=stamp, tag=classify_headline(title))
    return sorted(articles.values(), key=lambda row: -row["stamp"])


def news(now):
    url = preferences().get("rss_url", "")
    if not url:
        return [dict(title=title, tag=tag, url=None, stamp=None) for tag, title in [
            ("株式", "株式市場の見出し例"), ("為替", "外国為替市場の見出し例"), ("経済", "経済指標の見出し例")
        ]]
    if not isinstance(url, str) or urlsplit(url).scheme != "https" or not urlsplit(url).hostname:
        raise ValueError("rss_url にはHTTPSのRSSアドレスを指定してください")
    response = requests.get(url, timeout=10, headers={"Cache-Control": "no-cache"})
    response.raise_for_status()
    return parse_news(response.content, now)


def connect(account, password):
    return caldav.DAVClient(url="https://caldav.icloud.com/", username=account,
                            password=password, timeout=10)


def setup():
    account = input("Apple Account: ").strip()
    password = getpass("Apple アプリ用パスワード: ")
    with connect(account, password) as client:
        calendars = client.principal().calendars()
        for i, calendar in enumerate(calendars, 1):
            print(i, calendar.name)
        numbers = {int(n.strip()) for n in input("カレンダー番号（複数はカンマ区切り）: ").split(",")}
        if not numbers or not all(1 <= n <= len(calendars) for n in numbers):
            raise ValueError("番号を確認してください")
        urls = [str(calendars[n-1].url) for n in sorted(numbers)]
    keyring.set_password("PC-DayBoard/iCloud", account, password)
    DATA.mkdir(parents=True, exist_ok=True)
    config = DATA / "config.toml"
    tmp = config.with_suffix(".tmp")
    tmp.write_text(f"account = {json.dumps(account)}\ncalendars = {json.dumps(urls)}\n", encoding="utf-8")
    tmp.replace(config)


def local_time(value):
    if not isinstance(value, datetime):
        return datetime.combine(value, time.min, JST)
    return value.astimezone(JST) if value.tzinfo else value.replace(tzinfo=JST)


def event_row(event, start, end):
    if str(event.get("STATUS", "")).upper() == "CANCELLED":
        return None
    raw = event.decoded("DTSTART")
    begin = local_time(raw)
    all_day = type(raw) is date
    if "DTEND" in event:
        finish = local_time(event.decoded("DTEND"))
    else:
        finish = begin + event.get("DURATION").dt if "DURATION" in event else begin + timedelta(days=int(all_day))
    if begin >= end or (finish <= start and begin < start):
        return None
    return dict(start=begin.timestamp(), end=finish.timestamp(), allDay=all_day,
                title=str(event.get("SUMMARY") or "予定"), place=str(event.get("LOCATION") or ""))


def calendar_rows(calendar, start, end, *, server_expand=False):
    rows = {}
    resources = calendar.search(start=start, end=end, event=True, expand=not server_expand,
                                server_expand=server_expand, split_expanded=False)
    for resource in resources:
        for event in resource.icalendar_instance.walk("VEVENT"):
            row = event_row(event, start, end)
            if row:
                key = (str(event["UID"]), str(event.decoded("RECURRENCE-ID", row["start"])))
                rows[key] = row
    return list(rows.values())


def agenda(now):
    config = DATA / "config.toml"
    if not config.exists():
        raise SetupNeeded()
    stage = "設定ファイル"
    try:
        settings = tomllib.loads(config.read_text(encoding="utf-8-sig"))
        account = settings["account"]
        selected = settings["calendars"]
        stage = "Windows資格情報"
        password = keyring.get_password("PC-DayBoard/iCloud", account)
        if not password:
            raise SetupNeeded()
        start = local_time(now.date())
        end = start + timedelta(days=1)
        stage = "カレンダー一覧取得"
        with connect(account, password) as client:
            calendars = client.principal().calendars()
            # iCloud may change the shard hostname while keeping the collection path.
            by_path = {urlsplit(str(c.url)).path.rstrip("/"): c for c in calendars}
            rows = []
            for index, url in enumerate(selected, 1):
                calendar = by_path.get(urlsplit(url).path.rstrip("/"))
                if calendar is None:
                    raise CalendarFailure(f"カレンダー{index}が見つかりません（再設定してください）")
                stage = f"カレンダー{index}の期間検索"
                try:
                    rows.extend(calendar_rows(calendar, start, end))
                except AuthorizationError:
                    raise
                except (ValueError, TypeError, KeyError, OverflowError, DAVError):
                    stage = f"カレンダー{index}の予定展開"
                    rows.extend(calendar_rows(calendar, start, end, server_expand=True))
            return sorted(rows, key=lambda r: (r["start"], r["end"], r["title"], r["place"], r["allDay"]))
    except (SetupNeeded, AuthorizationError, CalendarFailure):
        raise
    except Exception as exc:
        raise CalendarFailure(f"{stage}失敗（{type(exc).__name__}）") from exc
