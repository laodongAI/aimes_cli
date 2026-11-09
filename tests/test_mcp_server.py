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
        self.assertEqual(names, ["aimes_assess_project_lifecycle", "aimes_task_start", "aimes_task_list", "aimes_task_update", "aimes_session_show", "aimes_session_bind", "aimes_project_state", "aimes_detect_engineering_mode", "aimes_set_project_state", "aimes_skill_route", "aimes_read_skill", "aimes_validate_delivery"])

    def test_project_state_and_mode_detection_tools(self):
        state = call_tool(self.root, "aimes_project_state", {})
        self.assertFalse(state["isError"])
        state_payload = json.loads(state["content"][0]["text"])
        self.assertEqual(state_payload["state"]["project_lifecycle"], "unknown")

        detected = call_tool(self.root, "aimes_detect_engineering_mode",
                             {"task_text": "Vue组件化开发"})
        self.assertFalse(detected["isError"])
        detected_payload = json.loads(detected["content"][0]["text"])
        self.assertEqual(detected_payload["mode"], "frontend-development")
        self.assertEqual(detected_payload["confidence"], "medium")

    def test_set_project_state_tool_requires_source_and_blocks_low_confidence_ai(self):
        missing_source = call_tool(self.root, "aimes_set_project_state",
                                   {"mode": "frontend-optimization"})
        self.assertTrue(missing_source["isError"])
        low_confidence = call_tool(self.root, "aimes_set_project_state",
                                   {"mode": "frontend-optimization", "source": "ai", "confidence": "low"})
        self.assertTrue(low_confidence["isError"])
        approved = call_tool(self.root, "aimes_set_project_state",
                             {"mode": "frontend-optimization", "source": "ai", "confidence": "medium"})
        self.assertFalse(approved["isError"])
        payload = json.loads(approved["content"][0]["text"])
        self.assertEqual(payload["state"]["mode_source"], "ai")

    def test_lifecycle_assessment_and_session_scoped_tasks(self):
        assessed = call_tool(self.root, "aimes_assess_project_lifecycle", {})
        self.assertFalse(assessed["isError"])
        assessment = json.loads(assessed["content"][0]["text"])
        self.assertEqual(assessment["current_lifecycle"], "unknown")
        self.assertIn("evidence", assessment)

        first = call_tool(self.root, "aimes_task_start",
                          {"title": "前端优化", "session_id": "codex", "task_id": "ui-task"})
        second = call_tool(self.root, "aimes_task_start",
                           {"title": "接口修复", "session_id": "claude", "task_id": "api-task"})
        self.assertFalse(first["isError"])
        self.assertFalse(second["isError"])
        session = call_tool(self.root, "aimes_session_show", {"session_id": "codex"})
        session_payload = json.loads(session["content"][0]["text"])
        self.assertEqual(session_payload["current_task"]["task_id"], "ui-task")
        listed = call_tool(self.root, "aimes_task_list", {"session_id": "claude"})
        listed_payload = json.loads(listed["content"][0]["text"])
        self.assertEqual([item["task_id"] for item in listed_payload["tasks"]], ["api-task"])
        updated = call_tool(self.root, "aimes_task_update",
                            {"task_id": "ui-task", "phase": "testing", "status": "blocked"})
        self.assertFalse(updated["isError"])
        payload = json.loads(updated["content"][0]["text"])
        self.assertEqual(payload["task"]["phase"], "testing")
        self.assertEqual(payload["task"]["status"], "blocked")

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
        document_path = Path(document["file"]).resolve()
        document_path.relative_to(self.root.resolve())

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
