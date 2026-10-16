import json, tempfile, unittest
from pathlib import Path
from aimes_cli.evaluation import validate_suite, validate_run, build_run_report, compare_runs

class EvaluationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory(); self.root=Path(self.tmp.name)
    def tearDown(self): self.tmp.cleanup()
    def put(self,name,data):
        p=self.root/name; p.parent.mkdir(parents=True,exist_ok=True); p.write_text(data if isinstance(data,str) else json.dumps(data),encoding='utf-8'); return p
    def suite(self,cases=None):
        return {"schema_version":1,"suite_id":"suite","version":"1.0.0","cases":cases if cases is not None else [{"case_id":"C1","objective":"test","input":{},"expected":{},"scoring":{"hard_gates":["G1"],"diagnostic_dimensions":["quality"]}}]}
    def run_record(self, status="PASS", gate="PASS", score=.8, case="C1"):
        return {"schema_version":1,"metadata":{"run_id":"R","suite_id":"suite","suite_version":"1.0.0","model":"m","tool_version":"t","skill_version":"s","started_at":"2026-10-14T00:00:00Z"},"case_results":[{"case_id":case,"status":status,"hard_gates":{"G1":gate},"scores":{"quality":score},"evidence_refs":["E1"]}]}
    def test_valid_suite(self): self.assertTrue(validate_suite(self.put('suite.yaml',self.yaml(self.suite())) )['ok'])
    def yaml(self,obj):
        import yaml
        return yaml.safe_dump(obj,allow_unicode=True)
    def test_duplicate_case_id_rejected(self):
        s=self.suite(); s['cases'].append(dict(s['cases'][0])); r=validate_suite(self.put('suite.yaml',self.yaml(s)))
        self.assertIn('DUPLICATE_CASE_ID',{x['code'] for x in r['findings']})
    def test_run_rejects_score_out_of_range(self):
        r=self.run_record(); r['case_results'][0]['scores']['quality']=1.2
        out=validate_run(self.put('run.json',r)); self.assertFalse(out['ok'])
        self.assertIn('SCORE_RANGE',{x['code'] for x in out['findings']})
    def test_run_rejects_pass_with_failed_gate(self):
        r=self.run_record(gate='FAIL'); out=validate_run(self.put('run.json',r))
        self.assertIn('PASS_WITH_FAILED_GATE',{x['code'] for x in out['findings']})
    def test_report_keeps_hard_gate_and_scores_separate(self):
        p=self.put('run.json',self.run_record()); report=build_run_report(p)
        self.assertEqual(report['status_counts']['PASS'],1); self.assertEqual(report['hard_gate_counts']['G1']['PASS'],1)
        self.assertEqual(report['diagnostic_score_means']['quality'],.8)
    def test_compare_flags_hard_gate_regression(self):
        b=self.put('base.json',self.run_record()); c=self.put('candidate.json',self.run_record(status='FAIL',gate='FAIL',score=.99))
        result=compare_runs(b,c); self.assertFalse(result['ok']); self.assertIn('HARD_GATE_REGRESSION',{x['code'] for x in result['findings']})
    def test_compare_reports_added_removed_cases(self):
        b=self.put('base.json',self.run_record()); c=self.put('candidate.json',self.run_record(case='C2'))
        result=compare_runs(b,c); self.assertEqual(result['added_cases'],['C2']); self.assertEqual(result['removed_cases'],['C1'])

if __name__=='__main__': unittest.main()
