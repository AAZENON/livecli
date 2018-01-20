from __future__ import print_function
import re
from functools import partial

from livecli.plugin import Plugin
from livecli.plugin.api import http
from livecli.plugin.api import validate
from livecli.stream import HLSStream
from livecli.utils import parse_json

__livecli_docs__ = {
    "domains": [
        "tv360.com.tr",
    ],
    "geo_blocked": [],
    "notes": "",
    "live": True,
    "vod": False,
    "last_update": "2016-12-16",
}


class TV360(Plugin):
    url_re = re.compile(r"https?://(?:www.)?tv360.com.tr/CanliYayin")
    data_re = re.compile(r'''div.*?data-tp=(?P<q>["'])(?P<data>.*?)(?P=q)''', re.DOTALL)
    _js_to_json = partial(re.compile(r"""(\w+):(["']|\d+,|true|false)""").sub, r'"\1":\2')
    data_schema = validate.Schema(
        validate.transform(data_re.search),
        validate.any(
            None,
            validate.all(
                validate.get("data"),
                validate.transform(_js_to_json),
                validate.transform(lambda x: x.replace("'", '"')),
                validate.transform(parse_json),
                {
                    "tp_type": "hls4",
                    "tp_file": validate.url(),
                }
            )
        )
    )

    @classmethod
    def can_handle_url(cls, url):
        return cls.url_re.match(url) is not None

    def _get_streams(self):
        res = http.get(self.url)
        data = self.data_schema.validate(res.text)

        if data:
            return HLSStream.parse_variant_playlist(self.session, data["tp_file"])


__plugin__ = TV360
