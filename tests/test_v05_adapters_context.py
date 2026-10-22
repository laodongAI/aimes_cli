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

    def test_v2_pass_requires_reproducible_context(self):
        p = self.write_yaml('adapter.yaml', {
            'schema_version': 2,
            'checks': [{
                'id': 'C1', 'tool': 'codex-cli', 'verification': 'PASS',
                'method': 'runtime_observation', 'evidence_note': 'Probe marker observed'
            }]
        })
        result = validate_adapter_evidence(p, self.root)
        self.assertFalse(result['ok'])
        missing = [f for f in result['findings'] if f['code'] == 'PASS_CONTEXT_FIELD_REQUIRED']
        self.assertEqual(len(missing), 9)

    def test_v2_pass_with_complete_context_is_valid(self):
        p = self.write_yaml('adapter.yaml', {
            'schema_version': 2,
            'checks': [{
                'id': 'C1', 'tool': 'codex-cli', 'product_version': '1.2.3',
                'execution_mode': 'cli', 'platform': 'windows-11', 'rule_entry': 'AGENTS.md',
                'verification': 'PASS', 'method': 'runtime_observation',
                'observed_at': '2026-10-22T00:00:00Z', 'observer': 'test-runner',
                'case_id': 'ADAPTER-PROBE-001', 'aimes_cli_version': '0.8.0',
                'governance_version': '1.2', 'evidence_note': 'Unique rule probe observed in a new session.'
            }]
        })
        result = validate_adapter_evidence(p, self.root)
        self.assertTrue(result['ok'], result['findings'])

    def test_v2_rejects_unknown_execution_mode(self):
        p = self.write_yaml('adapter.yaml', {
            'schema_version': 2,
            'checks': [{
                'id': 'C1', 'tool': 'codex-cli', 'verification': 'UNKNOWN',
                'method': 'file_inspection', 'execution_mode': 'guess'
            }]
        })
        result = validate_adapter_evidence(p, self.root)
        self.assertFalse(result['ok'])
        self.assertTrue(any(f['code'] == 'EXECUTION_MODE' for f in result['findings']))

    def test_v1_legacy_record_remains_compatible(self):
        p = self.write_yaml('adapter.yaml', {
            'schema_version': 1,
            'checks': [{
                'id': 'C1', 'tool': 'codex-cli', 'verification': 'PASS',
                'method': 'runtime_observation', 'evidence_note': 'Legacy evidence note'
            }]
        })
        result = validate_adapter_evidence(p, self.root)
        self.assertTrue(result['ok'], result['findings'])
        self.assertTrue(any(f['code'] == 'FIELD_RECOMMENDED_MISSING' for f in result['findings']))

    def test_adapter_report_counts_execution_modes(self):
        p = self.write_yaml('adapter.yaml', {
            'schema_version': 2,
            'checks': [{
                'id': 'C1', 'tool': 'codex-cli', 'verification': 'UNKNOWN',
                'method': 'file_inspection', 'execution_mode': 'cli'
            }, {
                'id': 'C2', 'tool': 'vscode-codex', 'verification': 'NOT_RUN',
                'method': 'manual_prompt', 'execution_mode': 'ide_extension'
            }]
        })
        result = adapter_report(p, self.root)
        self.assertEqual(result['execution_modes']['cli']['unknown'], 1)
        self.assertEqual(result['execution_modes']['ide_extension']['not_run'], 1)

    def test_adapter_schema_copies_match_and_declare_v2(self):
        repo_root = Path(__file__).resolve().parents[1]
        root_schema = json.loads((repo_root / 'schemas' / 'adapter-verification-evidence.schema.json').read_text(encoding='utf-8'))
        package_schema = json.loads((repo_root / 'src' / 'aimes_cli' / 'schemas' / 'adapter-verification-evidence.schema.json').read_text(encoding='utf-8'))
        self.assertEqual(root_schema, package_schema)
        self.assertEqual(root_schema['properties']['schema_version']['enum'], [1, 2])

    def test_malformed_evidence_types_return_findings_not_tracebacks(self):
        p = self.write_yaml('adapter.yaml', {
            'schema_version': [],
            'checks': [{
                'id': 'C1', 'tool': ['codex-cli'], 'verification': ['PASS'],
                'method': ['runtime_observation'], 'artifact_path': ['../escape']
            }]
        })
        result = validate_adapter_evidence(p, self.root)
        self.assertFalse(result['ok'])
        codes = {finding['code'] for finding in result['findings']}
        self.assertIn('SCHEMA_VERSION', codes)
        self.assertIn('UNKNOWN_TOOL', codes)
        self.assertIn('VERIFICATION_STATUS', codes)
        self.assertIn('VERIFICATION_METHOD', codes)
        self.assertIn('ARTIFACT_PATH_TYPE', codes)

if __name__=='__main__': unittest.main()
