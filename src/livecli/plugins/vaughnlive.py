import random
import re
import itertools
import ssl
import websocket

from livecli.plugin import Plugin
from livecli.plugin.api import useragents
from livecli.stream import RTMPStream

__livecli_docs__ = {
    "domains": [
        "breakers.tv",
        "instagib.tv",
        "pearltime.tv",
        "vapers.tv",
        "vaughnlive.tv",
    ],
    "geo_blocked": [],
    "notes": "",
    "live": True,
    "vod": False,
    "last_update": "2017-10-14",
}

_url_re = re.compile(r"""
    http(s)?://(\w+\.)?
    (?P<domain>vaughnlive|breakers|instagib|vapers|pearltime).tv
    (/embed/video)?
    /(?P<channel>[^/&?]+)
""", re.VERBOSE)


class VLWebSocket(websocket.WebSocket):
    def __init__(self, **_):
        self.session = _.pop("session")
        self.logger = self.session.logger.new_module("plugins.vaughnlive.websocket")
        sslopt = _.pop("sslopt", {})
        sslopt["cert_reqs"] = ssl.CERT_NONE
        super(VLWebSocket, self).__init__(sslopt=sslopt, **_)

    def send(self, payload, opcode=websocket.ABNF.OPCODE_TEXT):
        self.logger.debug("Sending message: {0}", payload)
        return super(VLWebSocket, self).send(payload + "\n\x00", opcode)

    def recv(self):
        d = super(VLWebSocket, self).recv().replace("\n", "").replace("\x00", "")
        return d.split(" ", 1)


class VaughnLive(Plugin):
    servers = ["wss://sapi-ws-{0}x{1:02}.vaughnlive.tv".format(x, y) for x, y in itertools.product(range(1, 3),
                                                                                                   range(1, 6))]
    origin = "https://vaughnlive.tv"
    rtmp_server_map = {
        "594140c69edad": "66.90.93.42",
        "585c4cab1bef1": "66.90.93.34",
        "5940d648b3929": "66.90.93.42",
        "5941854b39bc4": "198.255.0.10"
    }
    name_remap = {"#vl": "live", "#btv": "btv", "#pt": "pt", "#igb": "instagib", "#vtv": "vtv"}
    domain_map = {"vaughnlive": "#vl", "breakers": "#btv", "instagib": "#igb", "vapers": "#vtv", "pearltime": "#pt"}

    @classmethod
    def can_handle_url(cls, url):
        return _url_re.match(url)

    def api_url(self):
        return random.choice(self.servers)

    def parse_ack(self, action, message):
        if action.endswith("3"):
            channel, _, viewers, token, server, choked, is_live, chls, trns, ingest = message.split(";")
            is_live = is_live == "1"
            viewers = int(viewers)
            self.logger.debug("Viewers: {0}, isLive={1}", viewers, is_live)
            domain, channel = channel.split("-", 1)
            return is_live, server, domain, channel, token, ingest
        else:
            self.logger.error("Unhandled action format: {0}", action)

    def _get_info(self, stream_name):
        server = self.api_url()
        self.logger.debug("Connecting to API: {0}", server)
        ws = websocket.create_connection(server,
                                         header=["User-Agent: {0}".format(useragents.CHROME)],
                                         origin=self.origin,
                                         class_=VLWebSocket,
                                         session=self.session)
        ws.send("MVN LOAD3 {0}".format(stream_name))
        action, message = ws.recv()
        return self.parse_ack(action, message)

    def _get_rtmp_streams(self, server, domain, channel, token):
        # rtmp_server = self.rtmp_server_map.get(server, server)
        rtmp_server = "66.90.93.36:1935"

        url = "rtmp://{0}/live?{1}".format(rtmp_server, token)

        yield "live", RTMPStream(self.session, params={
            "rtmp": url,
            "pageUrl": self.url,
            "playpath": "{0}_{1}".format(self.name_remap.get(domain, "live"), channel),
            "live": True
        })

    def _get_streams(self):
        m = _url_re.match(self.url)
        if m:
            stream_name = "{0}-{1}".format(self.domain_map[(m.group("domain").lower())],
                                           m.group("channel"))

            is_live, server, domain, channel, token, ingest = self._get_info(stream_name)

            if not is_live:
                self.logger.info("Stream is currently off air")
            else:
                for s in self._get_rtmp_streams(server, domain, channel, token):
                    yield s


__plugin__ = VaughnLive
