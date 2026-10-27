import io
import json
import tempfile
import unittest
from pathlib import Path

from aimes_cli.core import init_project
from aimes_cli.mcp_server import call_tool, handle_request, serve_stdio


class McpServerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        init_project(self.root, ["codex-cli"], dry_run=False)

    def tearDown(self):
        self.directory.cleanup()

    def test_initialize_and_tools_list(self):
        response = handle_request(self.root, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        self.assertEqual(response["result"]["serverInfo"]["name"], "aimes-governance")
        self.assertIn("instructions", response["result"])
        listed = handle_request(self.root, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        names = [tool["name"] for tool in listed["result"]["tools"]]
        self.assertEqual(names, ["aimes_skill_route", "aimes_read_skill", "aimes_validate_delivery"])

    def test_notification_has_no_response(self):
        self.assertIsNone(handle_request(self.root, {"jsonrpc": "2.0", "method": "notifications/initialized"}))

    def test_skill_route_and_read_skill_roundtrip(self):
        result = call_tool(self.root, "aimes_skill_route", {"task_text": "实现新功能前先做需求分析", "top": 2})
        self.assertFalse(result["isError"])
        payload = json.loads(result["content"][0]["text"])
        self.assertTrue(payload["matches"])
        name = payload["matches"][0]["name"]
        read = call_tool(self.root, "aimes_read_skill", {"skill_name": name})
        self.assertFalse(read["isError"])
        document = json.loads(read["content"][0]["text"])
        self.assertIn("name: " + name, document["content"])
        self.assertTrue(Path(document["file"]).is_file())
        self.assertTrue(str(document["file"]).startswith(str(self.root)))

    def test_read_skill_rejects_unknown_name_and_missing_project(self):
        error = call_tool(self.root, "aimes_read_skill", {"skill_name": "does-not-exist"})
        self.assertTrue(error["isError"])
        with tempfile.TemporaryDirectory() as empty:
            missing = call_tool(Path(empty), "aimes_skill_route", {"task_text": "任意任务"})
            self.assertTrue(missing["isError"])
            self.assertIn("aimes init", missing["content"][0]["text"])

    def test_validate_delivery_tool(self):
        bad = "## DELIVERY\n- task_id: T-1\n- result: VERIFIED\n\n## FILES\n- none\n"
        result = call_tool(self.root, "aimes_validate_delivery", {"report_text": bad})
        payload = json.loads(result["content"][0]["text"])
        self.assertFalse(payload["ok"])
        codes = [item["code"] for item in payload["findings"]]
        self.assertIn("VERIFIED_WITHOUT_EVIDENCE", codes)

    def test_serve_stdio_processes_batch(self):
        stdin = io.StringIO(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}}) + "\n"
                            + "not-json\n"
                            + json.dumps({"jsonrpc": "2.0", "id": 2, "method": "unknown/method"}) + "\n")
        stdout = io.StringIO()
        serve_stdio(self.root, stdin=stdin, stdout=stdout)
        lines = [json.loads(line) for line in stdout.getvalue().splitlines() if line.strip()]
        self.assertEqual([line["id"] for line in lines], [1, None, 2])
        self.assertEqual(lines[1]["error"]["code"], -32700)
        self.assertEqual(lines[2]["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
