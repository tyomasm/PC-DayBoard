import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from icalendar import Event
import dayboard
from providers import JST, classify_headline, event_row, parse_news


class DashboardTests(unittest.TestCase):
    def test_feed(self):
        now = datetime(2026, 11, 20, tzinfo=JST)
        item = "<item><title>円相場</title><link>https://example.org/story</link><pubDate>{}</pubDate></item>"
        fresh = item.format("Thu, 19 Nov 2026 10:00:00 +0900")
        old = item.replace("/story", "/old").format("Tue, 17 Nov 2026 00:00:00 +0900")
        rows = parse_news("<rss><channel>"+fresh+fresh+old+"</channel></rss>", now)
        self.assertEqual([r["tag"] for r in rows], ["為替"])

    def test_market_headlines(self):
        for title, expected in [
            ("ＮＹ円の動向（架空通信）", "為替"),
            ("ＮＹ株の動向（架空通信）", "株式"),
            ("日本株の見通し", "株式"),
            ("株主優待の変更", "株式"),
            ("新商品の価格は158円台(株式会社テスト)", "経済"),
        ]:
            with self.subTest(title=title):
                self.assertEqual(classify_headline(title), expected)

    def test_calendar_boundaries(self):
        start = datetime(2026, 11, 20, tzinfo=JST)
        end = start + timedelta(days=1)
        e = Event()
        e.add("DTSTART", start.date())
        self.assertTrue(event_row(e, start, end)["allDay"])
        self.assertIsNone(event_row(e, end, end+timedelta(days=1)))
        e.add("DTEND", end.date()+timedelta(days=1))
        self.assertIsNotNone(event_row(e, end, end+timedelta(days=1)))
        e.add("STATUS", "CANCELLED")
        self.assertIsNone(event_row(e, start, end))

    def test_schedule(self):
        self.assertEqual(dayboard.next_slot(300, 30, 5), 2100)
        self.assertEqual(dayboard.next_slot(1799, 30, 0), 1800)
        self.assertEqual(dayboard.retry_delay("120", 0), 120)

    def test_failed_fetch_preserves_last_success(self):
        class StopWorker(Exception):
            pass
        def offline(now):
            raise ConnectionError()
        with tempfile.TemporaryDirectory() as tmp, patch.object(dayboard, "DATA", Path(tmp)):
            dayboard.initialize()
            with dayboard.db() as conn:
                conn.execute("INSERT INTO cache VALUES('news','old',1,'[]','更新済み')")
                conn.execute("INSERT INTO cache VALUES('agenda','old',1,'[]','更新済み')")
            with patch.dict(dayboard.SOURCES, news=(offline,30,5)), patch("dayboard.time.sleep", side_effect=StopWorker):
                with self.assertRaises(StopWorker):
                    dayboard.worker("news")
            state = dayboard.app.test_client().get("/api/dashboard").get_json()
            self.assertEqual(state["news"], dict(data=[], stamp=1, status="更新失敗"))
            self.assertIsNone(state["agenda"]["data"])
            self.assertEqual(dayboard.app.test_client().get("/",headers={"Host":"other.test"}).status_code,403)
