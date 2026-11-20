import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

import providers


class SourceTests(unittest.TestCase):
    def test_sample_and_configured_source(self):
        now = datetime.now(providers.JST)
        with tempfile.TemporaryDirectory() as tmp, patch.object(providers, "SETTINGS", Path(tmp)/"settings.toml"), patch("providers.requests.get") as get:
            self.assertTrue(all(a["stamp"] is None and a["url"] is None for a in providers.news(now)))
            get.assert_not_called()
            providers.SETTINGS.write_text('rss_url = "https://example.org/feed"', encoding="utf-8")
            get.return_value.content = b"<rss><channel/></rss>"
            self.assertEqual(providers.news(now), [])
            self.assertEqual(get.call_args.args, ("https://example.org/feed",))
