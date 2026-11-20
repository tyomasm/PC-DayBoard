import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import dayboard
import providers


class RefreshTests(unittest.TestCase):
    def test_news_new_unchanged_and_replaced(self):
        class Stop(Exception):
            pass
        with tempfile.TemporaryDirectory() as tmp, patch.object(dayboard, "DATA", Path(tmp)):
            dayboard.initialize()
            for title, status in [("記事A", "内容更新"), ("記事A", "変更なし"), ("記事B", "内容更新")]:
                def fetch(now):
                    return [{"title": title}]
                with patch.dict(dayboard.SOURCES, news=(fetch, 30, 5)), patch("dayboard.time.sleep", side_effect=Stop):
                    with self.assertRaises(Stop):
                        dayboard.worker("news")
                result = dayboard.snapshot()["news"]
                self.assertEqual((result["data"][0]["title"], result["status"]), (title, status))

    def test_calendar_rediscovery_and_expansion_fallback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.object(providers, "DATA", Path(tmp)):
            (Path(tmp)/"config.toml").write_text('account="test"\ncalendars=["https://old.example/cal/"]')
            with patch.object(providers.keyring, "get_password", return_value="test"), patch.object(providers, "connect") as connect:
                calendar = MagicMock()
                calendar.url = "https://new.example/cal/"
                connect.return_value.__enter__.return_value.principal.return_value.calendars.return_value = [calendar]
                calendar.search.side_effect = [ValueError("local expansion"), []]
                self.assertEqual(providers.agenda(datetime.now(providers.JST)), [])
                self.assertTrue(calendar.search.call_args.kwargs["server_expand"])
                calendar.search.side_effect = RuntimeError("private data")
                with self.assertRaisesRegex(providers.CalendarFailure, "^カレンダー1の期間検索失敗（RuntimeError）$"):
                    providers.agenda(datetime.now(providers.JST))
