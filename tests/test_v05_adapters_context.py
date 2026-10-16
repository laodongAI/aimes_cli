import hashlib, json, tempfile, unittest
from pathlib import Path
import yaml
from aimes_cli.v05 import validate_adapter_evidence, adapter_report, validate_context_pack

class V05Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def write_yaml(self,name,data):
        p=self.root/name; p.write_text(yaml.safe_dump(data,sort_keys=False),encoding='utf-8'); return p
    def test_unknown_adapter_evidence_is_valid_but_not_verified(self):
        p=self.write_yaml('adapter.yaml',{'checks':[{'id':'C1','tool':'codex-cli','verification':'UNKNOWN','method':'file_inspection'}]})
        result=validate_adapter_evidence(p,self.root)
        self.assertTrue(result['ok'],result)
        self.assertTrue(any(f['code']=='FIELD_RECOMMENDED_MISSING' for f in result['findings']))
    def test_pass_requires_runtime_evidence_method_and_note_or_artifact(self):
        p=self.write_yaml('adapter.yaml',{'checks':[{'id':'C1','tool':'codex-cli','verification':'PASS','method':'file_inspection','evidence_note':'looked at file'}]})
        result=validate_adapter_evidence(p,self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(any(f['code']=='INSUFFICIENT_PASS_METHOD' for f in result['findings']))
    def test_adapter_report_counts_status(self):
        p=self.write_yaml('adapter.yaml',{'checks':[{'id':'C1','tool':'codex-cli','verification':'UNKNOWN','method':'file_inspection'}]})
        result=adapter_report(p,self.root)
        self.assertEqual(result['tools']['codex-cli']['unknown'],1)
    def test_context_pack_detects_hash_change(self):
        f=self.root/'README.md'; f.write_text('before',encoding='utf-8')
        pack=self.root/'context-pack.json'
        pack.write_text(json.dumps({'pack_type':'AIMES_CONTEXT_PACK','context_files':[{'path':'README.md','sha256':hashlib.sha256(b'before').hexdigest()}]}),encoding='utf-8')
        self.assertTrue(validate_context_pack(pack,self.root)['ok'])
        f.write_text('after',encoding='utf-8')
        result=validate_context_pack(pack,self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(any(f['code']=='CONTEXT_HASH_CHANGED' for f in result['findings']))
    def test_context_pack_rejects_path_escape(self):
        pack=self.root/'context-pack.json'
        pack.write_text(json.dumps({'pack_type':'AIMES_CONTEXT_PACK','context_files':[{'path':'../outside','sha256':'x'}]}),encoding='utf-8')
        result=validate_context_pack(pack,self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(any(f['code']=='PATH_ESCAPE' for f in result['findings']))

if __name__=='__main__': unittest.main()
