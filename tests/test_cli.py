import json
import io
from contextlib import redirect_stdout
import tempfile
import unittest
from unittest.mock import call, patch
from pathlib import Path
from aimes_cli.adapters import normalize_tools
from aimes_cli.core import init_project, inspect_project, validate_project
from aimes_cli.cli import emit

class AimesCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name).resolve()

    def tearDown(self):
        self.tmp.cleanup()

    def test_emit_handles_string_conflicts_from_init_report(self):
        report = {"ok": False, "conflicts": ["CLAUDE.md"], "actions": []}
        output = io.StringIO()
        with redirect_stdout(output):
            emit(report)
        self.assertIn("CLAUDE.md (preserved; review proposal)", output.getvalue())

    def test_normalize_aliases_and_deduplicate(self):
        self.assertEqual(normalize_tools('codex,codex-cli,claude'), ['codex-cli','claude-code'])

    def test_init_dry_run_does_not_write(self):
        result = init_project(self.root, ['codex-cli'], dry_run=True)
        self.assertTrue(result['dry_run'])
        self.assertFalse((self.root/'.aimes/config.yaml').exists())

    def test_init_and_validate(self):
        result = init_project(self.root, ['codex-cli','claude-code'], dry_run=False)
        self.assertTrue(result['ok'])
        self.assertTrue((self.root/'AGENTS.md').exists())
        self.assertTrue((self.root/'CLAUDE.md').exists())
        validation = validate_project(self.root)
        self.assertTrue(validation['ok'], validation)
        managed = {item['path'] for item in json.loads((self.root/'.aimes/manifest.json').read_text())['managed_files']}
        self.assertIn('.aimes/skills/registry.yaml', managed)
        import yaml
        registry = yaml.safe_load((self.root/'.aimes/skills/registry.yaml').read_text(encoding='utf-8'))
        for route in registry['skills']:
            self.assertIn(route['file'], managed)
            self.assertTrue((self.root/route['file']).is_file(), route['file'])

    def test_existing_file_is_never_overwritten(self):
        (self.root/'AGENTS.md').write_text('user content\n', encoding='utf-8')
        result = init_project(self.root, ['codex-cli'])
        self.assertFalse(result['ok'])
        self.assertEqual((self.root/'AGENTS.md').read_text(), 'user content\n')
        self.assertTrue((self.root/'.aimes/proposed/AGENTS.md.proposed').exists())

    def test_zcode_uses_manual_adapter_not_guessed_native_path(self):
        init_project(self.root, ['zcode'])
        self.assertTrue((self.root/'.aimes/adapters/zcode/README.md').exists())
        self.assertFalse((self.root/'.zcode').exists())
        result=validate_project(self.root)
        self.assertTrue(result['ok'])
        self.assertTrue(any(f['code']=='ADAPTER_MANUAL' for f in result['findings']))


    def test_configure_adds_tool_when_existing_config_is_unmodified(self):
        init_project(self.root, ['codex-cli'])
        result = init_project(self.root, ['claude-code'])
        self.assertTrue(result['ok'], result)
        import yaml
        config = yaml.safe_load((self.root/'.aimes/config.yaml').read_text(encoding='utf-8'))
        self.assertEqual([t['id'] for t in config['tools']], ['codex-cli', 'claude-code'])
        self.assertTrue(validate_project(self.root)['ok'])


    def test_user_modified_managed_file_is_preserved_on_configure(self):
        init_project(self.root, ['codex-cli'])
        (self.root/'AGENTS.md').write_text('my custom rule\n', encoding='utf-8')
        result = init_project(self.root, ['claude-code'])
        self.assertFalse(result['ok'])
        self.assertEqual((self.root/'AGENTS.md').read_text(encoding='utf-8'), 'my custom rule\n')
        self.assertTrue((self.root/'.aimes/proposed/AGENTS.md.proposed').exists())

    def test_unknown_tool_rejected(self):
        with self.assertRaises(ValueError): normalize_tools('unknown-tool')

    def test_interactive_init_previews_then_applies_after_confirmation(self):
        from aimes_cli.cli import interactive_wizard
        preview = {"ok": True, "root": str(self.root), "dry_run": True, "actions": []}
        applied = {"ok": True, "root": str(self.root), "dry_run": False, "actions": []}
        with patch("aimes_cli.cli.Path.cwd", return_value=self.root), \
             patch("builtins.input", side_effect=["1", "1", "y", "yes", "0"]), \
             patch("aimes_cli.cli.init_project", side_effect=[preview, applied]) as init_mock, \
             patch("aimes_cli.cli.emit") as emit_mock:
            self.assertEqual(interactive_wizard(), 0)
        self.assertEqual(init_mock.call_args_list, [
            call(self.root, ["trae-code"], "project", True),
            call(self.root, ["trae-code"], "project", False),
        ])
        self.assertEqual(emit_mock.call_count, 2)

    def test_interactive_init_preview_cancel_does_not_apply(self):
        from aimes_cli.cli import interactive_wizard
        preview = {"ok": True, "root": str(self.root), "dry_run": True, "actions": []}
        with patch("aimes_cli.cli.Path.cwd", return_value=self.root), \
             patch("builtins.input", side_effect=["1", "1", "y", "no", "0"]), \
             patch("aimes_cli.cli.init_project", return_value=preview) as init_mock, \
             patch("aimes_cli.cli.emit"):
            self.assertEqual(interactive_wizard(), 0)
        init_mock.assert_called_once_with(self.root, ["trae-code"], "project", True)


    def test_product_manager_skill_is_deployed_and_routed(self):
        result = init_project(self.root, ['trae-code', 'codex-cli'])
        self.assertTrue(result['ok'], result)
        skill_path = self.root/'.aimes/skills/product-manager/SKILL.md'
        self.assertTrue(skill_path.is_file())
        self.assertIn('项目知识基线', skill_path.read_text(encoding='utf-8'))
        import yaml
        registry = yaml.safe_load((self.root/'.aimes/skills/registry.yaml').read_text(encoding='utf-8'))
        route = next(item for item in registry['skills'] if item['name'] == 'product-manager')
        self.assertEqual(route['file'], 'skills/product-manager/SKILL.md')
        self.assertIn('generate_guidance_prompt', route['triggers'])
        self.assertIn('product-manager/SKILL.md', (self.root/'.trae/rules/00-aimes-governance.md').read_text(encoding='utf-8'))
        self.assertIn('product-manager/SKILL.md', (self.root/'AGENTS.md').read_text(encoding='utf-8'))
        self.assertTrue(validate_project(self.root)['ok'], validate_project(self.root))

    def test_chatgpt_work_adapter_deploys_entry_and_prompt_optimization_skill(self):
        result = init_project(self.root, ['chatgpt-work'])
        self.assertTrue(result['ok'], result)
        self.assertTrue((self.root/'docs/_governance/adapters/CHATGPT-WORK-ENTRY.md').is_file())
        self.assertTrue((self.root/'.aimes/adapters/chatgpt-work/PROJECT-INSTRUCTIONS.md').is_file())
        self.assertTrue((self.root/'.aimes/adapters/chatgpt-work/README.md').is_file())
        self.assertTrue((self.root/'.aimes/skills/prompt-optimization/SKILL.md').is_file())
        self.assertTrue(validate_project(self.root)['ok'], validate_project(self.root))
        import yaml
        registry = yaml.safe_load((self.root/'.aimes/skills/registry.yaml').read_text(encoding='utf-8'))
        prompt_route = next(item for item in registry['skills'] if item['name'] == 'prompt-optimization')
        self.assertTrue((self.root/prompt_route['file']).is_file())

if __name__ == '__main__': unittest.main()
