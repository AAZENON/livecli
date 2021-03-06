import unittest

from livecli.plugins.perviykanal import PerviyKanal


class TestPluginPerviyKanal(unittest.TestCase):
    def test_can_handle_url(self):
        regex_test_list = [
            "https://media.1tv.ru/embed/ctcmedia/ctc-che.html?start=auto",
            "https://media.1tv.ru/embed/ctcmedia/ctc-dom.html?start=auto",
            "https://media.1tv.ru/embed/ctcmedia/ctc-love.html?start=auto",
            "https://stream.1tv.ru/live",
            "https://www.1tv.ru/embedlive?start=auto",
            "https://www.1tv.ru/live",
            "https://www.chetv.ru/online/",
            "https://www.ctc.ru/online/",
            "https://www.ctclove.ru/online/",
            "https://www.domashny.ru/online/",
        ]

        for url in regex_test_list:
            self.assertTrue(PerviyKanal.can_handle_url(url))
