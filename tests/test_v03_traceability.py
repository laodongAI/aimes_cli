import tempfile, unittest
from pathlib import Path
import yaml
from aimes_cli.v03 import validate_evidence, validate_trace, build_context_pack

class V03Tests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def put(self, rel, text):
        p=self.root/rel; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(text,encoding='utf-8'); return p
    def test_trace_rejects_missing_link_and_verified_without_evidence(self):
        p=self.put('trace.yaml','''schema_version: 1\nentities:\n  - id: T-1\n    type: test\n    status: VERIFIED\n    links: [{target: MISSING}]\n''')
        r=validate_trace(p,self.root); codes={x['code'] for x in r['findings']}
        self.assertFalse(r['ok']); self.assertIn('BROKEN_TRACE_LINK',codes); self.assertIn('VERIFIED_WITHOUT_EVIDENCE',codes)
    def test_verified_requires_passing_real_evidence_reference(self):
        self.put('logs/test.log','pass')
        self.put('evidence.yaml','''schema_version: 1\nevidence:\n  - id: E-1\n    kind: test\n    command: pytest\n    exit_code: 0\n    result: PASS\n    observed_at: now\n    artifact_path: logs/test.log\n''')
        p=self.put('trace.yaml','''schema_version: 1\nevidence_file: evidence.yaml\nentities:\n  - id: T-1\n    type: test\n    status: VERIFIED\n    links: []\n    evidence_refs: [E-1]\n''')
        self.assertTrue(validate_trace(p,self.root)['ok'])
    def test_verified_cannot_reference_failed_evidence(self):
        self.put('evidence.yaml','''schema_version: 1\nevidence:\n  - id: E-1\n    kind: test\n    command: pytest\n    exit_code: 1\n    result: FAIL\n    observed_at: now\n''')
        p=self.put('trace.yaml','''schema_version: 1\nevidence_file: evidence.yaml\nentities:\n  - id: T-1\n    type: test\n    status: VERIFIED\n    links: []\n    evidence_refs: [E-1]\n''')
        self.assertIn('VERIFIED_EVIDENCE_NOT_PASS',{x['code'] for x in validate_trace(p,self.root)['findings']})
    def test_evidence_rejects_path_escape(self):
        p=self.put('evidence.yaml','''schema_version: 1\nevidence:\n  - id: E-1\n    kind: artifact\n    result: PASS\n    artifact_path: ../secret.txt\n''')
        self.assertIn('PATH_ESCAPE',{x['code'] for x in validate_evidence(p,self.root)['findings']})
    def test_context_pack_generates_handoff_without_modifying_sources(self):
        self.put('docs/context.md','keep')
        p=self.put('trace.yaml','''schema_version: 1\nproject: {name: Demo}\ntask: {id: T-1, title: Handoff, goal: Continue, status: IN_PROGRESS}\nentities: []\ncontext_files: [docs/context.md]\nopen_questions: [Need owner answer]\nrisks: []\n''')
        out=self.root/'.aimes/context-pack'; r=build_context_pack(p,out,self.root)
        self.assertTrue(r['ok']); self.assertTrue((out/'HANDOFF.md').is_file()); self.assertTrue((out/'context-pack.json').is_file())
        self.assertEqual((self.root/'docs/context.md').read_text(), 'keep')

if __name__=='__main__': unittest.main()
