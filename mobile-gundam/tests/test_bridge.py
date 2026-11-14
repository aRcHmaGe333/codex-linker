import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from urllib.error import HTTPError
from urllib.request import Request,urlopen

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import bridge

class RelayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp=tempfile.TemporaryDirectory()
        bridge.DATA=Path(cls.tmp.name);bridge.DB=bridge.DATA/'relay.sqlite3'
        os.environ['GUNDAM_ADMIN_TOKEN']='test-admin'
        bridge.initialize()
        cls.http=bridge.ThreadingHTTPServer(('127.0.0.1',0),bridge.Handler)
        cls.url=f'http://127.0.0.1:{cls.http.server_port}'
        cls.thread=threading.Thread(target=cls.http.serve_forever,daemon=True);cls.thread.start()
    @classmethod
    def tearDownClass(cls):
        cls.http.shutdown();cls.http.server_close();cls.tmp.cleanup()
    def test_file_and_feedback_roundtrip(self):
        pair=bridge.request(self.url,'test-admin','POST','/v1/pair',b'')
        root='/v1/s/'+pair['session']
        phone,agent=pair['phone_token'],pair['agent_token']
        payload=b'APK data \0\1\2'
        uploaded=bridge.request(self.url,phone,'POST',root+'/files',payload,{'X-File-Name':'app.apk'})
        self.assertEqual(uploaded['sha256'],hashlib.sha256(payload).hexdigest())
        self.assertEqual(bridge.request(self.url,agent,'GET',root+'/files/'+uploaded['id']),payload)
        bridge.request(self.url,phone,'POST',root+'/events',b'{"kind":"crash","stack":"here"}')
        events=bridge.request(self.url,agent,'GET',root+'/events')['items']
        self.assertEqual([x['kind'] for x in events],['file','crash'])
        cmd=bridge.request(self.url,agent,'POST',root+'/commands',b'{"kind":"ping"}')
        self.assertEqual(bridge.request(self.url,phone,'GET',root+'/commands')['items'][0]['id'],cmd['id'])
        with self.assertRaises(RuntimeError):
            bridge.request(self.url,phone,'POST',root+'/commands',b'{"kind":"unsafe"}')
        with self.assertRaises(RuntimeError):
            bridge.request(self.url,'wrong','GET',root+'/events')
        with self.assertRaises(RuntimeError):
            bridge.request(self.url,agent,'GET',root+'/files/'+'0'*32)
if __name__=='__main__':unittest.main()