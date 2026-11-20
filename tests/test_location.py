import unittest
from unittest.mock import patch

from dayboard import app


class LocationTests(unittest.TestCase):
    def test_local_request_rounds_coordinates(self):
        with patch('dayboard.weather', return_value={'forecast': []}) as provider:
            result = app.test_client().post('/api/weather/location', headers={'Origin': 'http://localhost'},
                                            json={'latitude': 34.6937, 'longitude': 135.5023})
            self.assertEqual(result.status_code, 200)
            self.assertEqual(provider.call_args.args[1:], (34.69, 135.5))

    def test_invalid_requests_do_not_fetch(self):
        with patch('dayboard.weather') as provider:
            for origin, latitude, code in [('http://other.test', 35, 403), ('http://localhost', True, 400),
                                           ('http://localhost', 91, 400), ('http://localhost', '35', 400)]:
                result = app.test_client().post('/api/weather/location', headers={'Origin': origin},
                                                json={'latitude': latitude, 'longitude': 139})
                self.assertEqual(result.status_code, code)
            provider.assert_not_called()
