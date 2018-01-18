import os
import unittest

from Crypto.Cipher import AES
from binascii import hexlify

from livecli.stream import hls
from livecli.session import Livecli
from functools import partial
import requests_mock


def pkcs7_encode(data, keySize):
    val = keySize - (len(data) % keySize)
    return b''.join([data, bytes(bytearray(val * [val]))])


def encrypt(data, key, iv):
    aesCipher = AES.new(key, AES.MODE_CBC, iv)
    encrypted_data = aesCipher.encrypt(pkcs7_encode(data, len(key)))
    return encrypted_data


class TestHLS(unittest.TestCase):
    """
    Test that when invoked for the command line arguments are parsed as expected
    """
    mediaSequence = 1651

    def getMasterPlaylist(self):
        masterPlaylist = """
#EXTM3U
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="720p30",NAME="720p",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=2299652,RESOLUTION=1280x720,CODECS="avc1.77.31,mp4a.40.2",VIDEO="720p30"
720p.m3u8
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="720p30",NAME="720p",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=2299652,RESOLUTION=1280x720,CODECS="avc1.77.31,mp4a.40.2",VIDEO="720p30"
720p_alt.m3u8
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="480p30",NAME="480p",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=1354652,RESOLUTION=852x480,CODECS="avc1.77.31,mp4a.40.2",VIDEO="480p30"
480p.m3u8
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="360p30",NAME="360p",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=630000,RESOLUTION=640x360,CODECS="avc1.77.31,mp4a.40.2",VIDEO="360p30"
360p.m3u8
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="160p30",NAME="160p",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=230000,RESOLUTION=284x160,CODECS="avc1.77.31,mp4a.40.2",VIDEO="160p30"
160p.m3u8
#EXT-X-MEDIA:TYPE=VIDEO,GROUP-ID="chunked",NAME="1080p (source)",AUTOSELECT=YES,DEFAULT=YES
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=3982010,RESOLUTION=1920x1080,CODECS="avc1.4D4029,mp4a.40.2",VIDEO="chunked"
playlist.m3u8
#EXT-X-MEDIA:TYPE=AUDIO,GROUP-ID="audio_only",NAME="audio_only",AUTOSELECT=YES,DEFAULT=NO,LANGUAGE="en"
#EXT-X-STREAM-INF:PROGRAM-ID=1,BANDWIDTH=90145,CODECS="mp4a.40.2",VIDEO="audio_only"
audio_only.m3u8
"""
        return masterPlaylist

    def getPlaylist(self, aesIv, streamNameTemplate):
        playlist = """
#EXTM3U
#EXT-X-VERSION:5
#EXT-X-TARGETDURATION:1
#ID3-EQUIV-TDTG:2018-01-01T18:20:05
#EXT-X-MEDIA-SEQUENCE:{0}
#EXT-X-TWITCH-ELAPSED-SECS:3367.800
#EXT-X-TWITCH-TOTAL-SECS:3379.943
""".format(self.mediaSequence)
        playlistEnd = ""
        if aesIv is not None:
            playlistEnd = playlistEnd + "#EXT-X-KEY:METHOD=AES-128,URI=\"encryption_key.key\",IV=0x{0},KEYFORMAT=identity,KEYFORMATVERSIONS=1\n".format(hexlify(aesIv).decode("UTF-8"))

        for i in range(4):
            playlistEnd = playlistEnd + "#EXTINF:1.000,\n{0}\n".format(streamNameTemplate.format(i))
            self.mediaSequence += 1

        return playlist + playlistEnd

    def start_livecli(self, masterPlaylist, kwargs={}):
        print("Executing livecli")
        livecli = Livecli()

        # Set to default value to avoid a test fail if the default change
        livecli.set_option("hls-live-edge", 3)

        livecli.logger.set_level("debug")
        masterStream = hls.HLSStream.parse_variant_playlist(livecli, masterPlaylist, **kwargs)
        stream = masterStream["1080p (source)"].open()
        data = b"".join(iter(partial(stream.read, 8192), b""))
        stream.close()
        print("End of livecli execution")
        return data

    def test_hls_non_encrypted(self):
        streams = [os.urandom(1024) for i in range(4)]
        masterPlaylist = self.getMasterPlaylist()
        # firstSequence = self.mediaSequence
        playlist = self.getPlaylist(None, "stream{0}.ts") + "#EXT-X-ENDLIST\n"
        with requests_mock.Mocker() as mock:
            mock.get("http://mocked/path/master.m3u8", text=masterPlaylist)
            mock.get("http://mocked/path/playlist.m3u8", text=playlist)
            for i, stream in enumerate(streams):
                mock.get("http://mocked/path/stream{0}.ts".format(i), content=stream)

            # Start livecli on the generated stream
            livecliResult = self.start_livecli("http://mocked/path/master.m3u8", {'start_offset': 1, 'duration': 1})

        # Check result
        expectedResult = b''.join(streams[1:3])
        self.assertEqual(livecliResult, expectedResult)

    def test_hls_encryted_aes128(self):
        # Encryption parameters
        aesKey = os.urandom(16)
        aesIv = os.urandom(16)
        # Generate stream data files
        clearStreams = [os.urandom(1024) for i in range(4)]
        encryptedStreams = [encrypt(clearStream, aesKey, aesIv) for clearStream in clearStreams]

        masterPlaylist = self.getMasterPlaylist()
        playlist1 = self.getPlaylist(aesIv, "stream{0}.ts.enc")
        playlist2 = self.getPlaylist(aesIv, "stream2_{0}.ts.enc") + "#EXT-X-ENDLIST\n"

        livecliResult = None
        with requests_mock.Mocker() as mock:
            mock.get("http://mocked/path/master.m3u8", text=masterPlaylist)
            mock.get("http://mocked/path/playlist.m3u8", [{'text': playlist1}, {'text': playlist2}])
            mock.get("http://mocked/path/encryption_key.key", content=aesKey)
            for i, encryptedStream in enumerate(encryptedStreams):
                mock.get("http://mocked/path/stream{0}.ts.enc".format(i), content=encryptedStream)
            for i, encryptedStream in enumerate(encryptedStreams):
                mock.get("http://mocked/path/stream2_{0}.ts.enc".format(i), content=encryptedStream)

            # Start livecli on the generated stream
            livecliResult = self.start_livecli("http://mocked/path/master.m3u8")

        # Check result
        # Live streams starts the last 3 segments from the playlist
        expectedResult = b''.join(clearStreams[1:] + clearStreams)
        self.assertEqual(livecliResult, expectedResult)


if __name__ == "__main__":
    unittest.main()
