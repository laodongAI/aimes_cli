import json
import tempfile
import unittest
from pathlib import Path
from aimes_cli.adapters import normalize_tools
from aimes_cli.core import init_project, inspect_project, validate_project

class AimesCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

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
        self.assertEqual(len(json.loads((self.root/'.aimes/manifest.json').read_text())['managed_files']), 6)

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

if __name__ == '__main__': unittest.main()
