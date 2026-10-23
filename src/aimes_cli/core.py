from __future__ import annotations
import hashlib, json, os, shutil, subprocess, sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
import yaml
from .adapters import ADAPTERS, adapter_payload, normalize_tools
from . import __version__, SCHEMA_VERSION, GOVERNANCE_VERSION

CONFIG_REL = Path('.aimes/config.yaml')
MANIFEST_REL = Path('.aimes/manifest.json')
CORE_REL = Path('docs/_governance/AIMES-CORE-V1.2.md')
ENTRY_TEMPLATES = {
    'AGENTS.md': """# AIMES project instructions (Codex-compatible entry)\n\nThis file is a thin tool entry point. The authoritative governance core is [`docs/_governance/AIMES-CORE-V1.2.md`](docs/_governance/AIMES-CORE-V1.2.md).\n\nBefore making changes:\n1. Read the governance core and relevant project instructions.\n2. Inspect `git status` and preserve all pre-existing user changes.\n3. Identify task scope, acceptance criteria, risks, and verification commands.\n4. Do not claim `VERIFIED` without reproducible evidence.\n5. Record task status and cross-tool handoff in the project's canonical records.\n6. If instructions conflict or tool capability is unknown, stop and report the conflict rather than guessing.\n\nThis entry does not replace tool-native safety controls or project-specific instructions.\n""",
    'CLAUDE.md': """# AIMES project instructions (Claude Code entry)\n\nThe authoritative governance core is [`docs/_governance/AIMES-CORE-V1.2.md`](docs/_governance/AIMES-CORE-V1.2.md). Read it before project-changing work.\n\n- Inspect `git status` first and preserve pre-existing user changes.\n- State scope, acceptance criteria, risk, and verification plan before significant changes.\n- Do not claim `VERIFIED` without reproducible evidence.\n- Update canonical task/handoff records when handing work to another tool.\n- Do not assume a tool integration, hook, or command exists unless verified in this environment.\n- Resolve project-specific details from the project context; do not duplicate them here.\n""",
    '.github/copilot-instructions.md': """# AIMES instructions for GitHub Copilot\n\nAuthoritative governance core: [`../docs/_governance/AIMES-CORE-V1.2.md`](../docs/_governance/AIMES-CORE-V1.2.md) (repository-relative: `docs/_governance/AIMES-CORE-V1.2.md`).\n\nFor project-changing work, inspect existing changes first, respect project instructions, define acceptance criteria, use configured verification commands, and record evidence. Never report a task as verified unless the relevant checks actually ran and passed. When uncertain about a tool capability or conflicting rule, report the limitation rather than inventing behavior.\n""",
    '.trae/rules/00-aimes-governance.md': """# AIMES governance rule for Trae Code\n\nAuthoritative governance core: `docs/_governance/AIMES-CORE-V1.2.md`. Confirm this rule is loaded by the installed Trae Code version before relying on it.\n\n- Inspect repository state before edits; preserve user changes.\n- Establish scope, acceptance criteria, risk and verification plan.\n- Use project-defined commands; do not invent commands.\n- Record evidence for verification; do not infer success from intent.\n- Keep task/handoff state in canonical repository records.\n- If this rule is not loaded or conflicts with another instruction, report it.\n""",
}

MANUAL_ADAPTER = """# AIMES adapter review required: {name}\n\nThis project has selected **{name}**, but AIMES does not assume a native rules path for this tool.\n\n1. Record the exact product name and version.\n2. Confirm its documented project-rule entry point and loading behavior.\n3. Map that entry to `docs/_governance/AIMES-CORE-V1.2.md` without duplicating the core.\n4. Run the rule-loading and handoff acceptance tests.\n5. Update `.aimes/config.yaml` and `.aimes/manifest.json` only after evidence is captured.\n\nUntil then, adapter status is `manual-unverified`; do not claim automatic enforcement.\n"""

def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()

def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()

def find_root(start: Path | None = None) -> Path:
    p = (start or Path.cwd()).resolve()
    if p.is_file(): p = p.parent
    for candidate in [p, *p.parents]:
        if (candidate / CONFIG_REL).is_file() or (candidate / '.git').exists():
            return candidate
    return p

def load_config(root: Path) -> dict[str, Any] | None:
    p = root / CONFIG_REL
    if not p.exists(): return None
    with p.open('r', encoding='utf-8') as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict): raise ValueError(f'{p} must contain a YAML mapping')
    return data

def _content_for_entry(path: str) -> str:
    return ENTRY_TEMPLATES[path]

def build_config(root: Path, tools: list[str], scope: str) -> dict[str, Any]:
    return {
        'schema_version': SCHEMA_VERSION,
        'governance': {'name': 'AIMES', 'version': GOVERNANCE_VERSION, 'core': CORE_REL.as_posix()},
        'project': {'root': '.', 'name': root.name, 'scope': scope},
        'tools': [{'id': t, 'name': ADAPTERS[t].label, 'adapter_status': ADAPTERS[t].status, 'entry_paths': list(ADAPTERS[t].paths)} for t in tools],
        'policy': {'preserve_existing_files': True, 'auto_overwrite': False, 'unknown_capability': 'report-and-stop', 'verified_requires_evidence': True},
        'records': {'tasks': 'project-control/TASKS.md', 'handoff': 'project-control/HANDOFF.md'},
    }

def previous_manifest(root: Path) -> dict[str, str]:
    path = root / MANIFEST_REL
    if not path.is_file(): return {}
    try:
        data = json.loads(path.read_text(encoding='utf-8'))
        return {item['path']: item['sha256'] for item in data.get('managed_files', []) if isinstance(item, dict) and item.get('path') and item.get('sha256')}
    except Exception:
        return {}

def is_unchanged_managed(root: Path, rel: str, old_hashes: dict[str, str]) -> bool:
    path = root / rel
    return path.is_file() and rel in old_hashes and sha256_text(path.read_text(encoding='utf-8', errors='replace')) == old_hashes[rel]

def proposed_files(root: Path, tools: list[str], scope: str) -> dict[str, str]:
    files: dict[str, str] = {}
    effective_tools = list(tools)
    files[CORE_REL.as_posix()] = (Path(__file__).resolve().parent / 'templates/core/AIMES-CORE-V1.2.md').read_text(encoding='utf-8')
    # Deploy callable UI Skills with the project rules; references must never point to assets that init did not install.
    template_root = Path(__file__).resolve().parent / 'templates/skills'
    for skill_file in sorted(template_root.glob('*/SKILL.md')):
        rel = (Path('.aimes/skills') / skill_file.parent.name / 'SKILL.md').as_posix()
        files[rel] = skill_file.read_text(encoding='utf-8')
    ui_registry = template_root / 'registry.yaml'
    if ui_registry.is_file():
        files['.aimes/skills/registry.yaml'] = ui_registry.read_text(encoding='utf-8')
    ui_suite = template_root / 'ui-quality-governance-suite.yaml'
    if ui_suite.is_file():
        files['.aimes/skills/ui-quality-governance-suite.yaml'] = ui_suite.read_text(encoding='utf-8')
    old_hashes = previous_manifest(root)
    config = build_config(root, tools, scope)
    existing_config_path = root / CONFIG_REL
    if is_unchanged_managed(root, CONFIG_REL.as_posix(), old_hashes):
        try:
            old_config = yaml.safe_load(existing_config_path.read_text(encoding='utf-8')) or {}
            existing_tools = [t.get('id') for t in old_config.get('tools', []) if isinstance(t, dict)]
            merged_tools = list(dict.fromkeys(existing_tools + tools))
            effective_tools = merged_tools
            config = build_config(root, merged_tools, scope)
        except Exception:
            pass
    files[CONFIG_REL.as_posix()] = yaml.safe_dump(config, allow_unicode=True, sort_keys=False)
    capabilities = {'schema_version': 1, 'tools': [{'id': t, 'product_version': 'unknown', 'rule_loading': 'unknown', 'runtime_validation': 'not-run', 'evidence': []} for t in effective_tools]}
    caps_path = root / '.aimes/tool-capabilities.yaml'
    if is_unchanged_managed(root, '.aimes/tool-capabilities.yaml', old_hashes):
        try:
            old_caps = yaml.safe_load(caps_path.read_text(encoding='utf-8')) or {}
            old_items = {item.get('id'): item for item in old_caps.get('tools', []) if isinstance(item, dict) and item.get('id')}
            for item in capabilities['tools']:
                old_items.setdefault(item['id'], item)
            capabilities = {'schema_version': 1, 'tools': list(old_items.values())}
        except Exception:
            pass
    files['.aimes/tool-capabilities.yaml'] = yaml.safe_dump(capabilities, allow_unicode=True, sort_keys=False)
    files['.aimes/manifest.json'] = ''  # filled after target decision
    files['.aimes/adapters/README.md'] = "# AIMES tool adapters\n\nNative entry points are generated only when their loading contract is sufficiently known. ZCode and QCode use review notes until their exact rule-loading mechanism is verified.\n"
    for tool in effective_tools:
        adapter = ADAPTERS[tool]
        if adapter.status == 'manual':
            files[adapter.paths[0]] = MANUAL_ADAPTER.format(name=adapter.label)
        else:
            for path in adapter.paths:
                files[path] = _content_for_entry(path)
    return files

def _manifest_for(files: dict[str, str], tools: list[str]) -> dict[str, Any]:
    return {'manifest_version': 1, 'aimes_cli_version': __version__, 'governance_version': GOVERNANCE_VERSION, 'created_at': utc_now(), 'managed_files': [{'path': p, 'sha256': sha256_text(c), 'status': 'managed' } for p, c in sorted(files.items()) if p != '.aimes/manifest.json'], 'selected_tools': tools}

def init_project(root: Path, tools: list[str], scope: str = 'project', dry_run: bool = False) -> dict[str, Any]:
    old_hashes = previous_manifest(root)
    files = proposed_files(root, tools, scope)
    actions=[]; conflicts=[]; preserved=[]; updateable=[]
    # Existing files are updated only when the previous manifest proves they are unchanged AIMES-managed files.
    for rel, content in files.items():
        if rel == '.aimes/manifest.json':
            continue
        target = root / rel
        if target.exists():
            existing = target.read_text(encoding='utf-8', errors='replace') if target.is_file() else '<directory>'
            if existing == content:
                actions.append({'path': rel, 'action': 'unchanged'})
            elif is_unchanged_managed(root, rel, old_hashes):
                updateable.append(rel)
                actions.append({'path': rel, 'action': 'update-managed'})
            else:
                conflicts.append({'path': rel, 'action': 'preserved-existing', 'proposed_path': f'.aimes/proposed/{rel}.proposed'})
                preserved.append(rel)
                actions.append({'path': rel, 'action': 'conflict-preserved', 'proposed_path': f'.aimes/proposed/{rel}.proposed'})
        else:
            actions.append({'path': rel, 'action': 'create'})
    managed_candidates = {p:c for p,c in files.items() if p not in preserved and p != '.aimes/manifest.json'}
    try:
        manifest_tools = [item.get('id') for item in (yaml.safe_load(files[CONFIG_REL.as_posix()]) or {}).get('tools', []) if isinstance(item, dict) and item.get('id')]
    except Exception:
        manifest_tools = tools
    manifest_content = json.dumps(_manifest_for(managed_candidates, manifest_tools), ensure_ascii=False, indent=2) + '\n'
    files['.aimes/manifest.json'] = manifest_content
    manifest_target = root / '.aimes/manifest.json'
    if manifest_target.exists():
        old_manifest_text = manifest_target.read_text(encoding='utf-8', errors='replace')
        # Update manifest only if it parses and every currently managed file still matches its recorded hash.
        try:
            old_manifest_obj = json.loads(old_manifest_text)
            manifest_safe = isinstance(old_manifest_obj, dict) and old_manifest_obj.get('manifest_version') == 1 and isinstance(old_manifest_obj.get('managed_files'), list)
        except Exception:
            manifest_safe = False
        if old_manifest_text == manifest_content:
            actions.append({'path': '.aimes/manifest.json', 'action': 'unchanged'})
        elif manifest_safe:
            actions.append({'path': '.aimes/manifest.json', 'action': 'update-managed'})
        else:
            conflicts.append({'path': '.aimes/manifest.json', 'action': 'preserved-existing', 'proposed_path': '.aimes/proposed/.aimes/manifest.json.proposed'})
            preserved.append('.aimes/manifest.json')
            actions.append({'path': '.aimes/manifest.json', 'action': 'conflict-preserved', 'proposed_path': '.aimes/proposed/.aimes/manifest.json.proposed'})
    else:
        actions.append({'path': '.aimes/manifest.json', 'action': 'create'})
    if not dry_run:
        for rel, content in files.items():
            target = root / rel
            if target.exists():
                existing = target.read_text(encoding='utf-8', errors='replace') if target.is_file() else '<directory>'
                safe_update = rel in updateable or (rel == '.aimes/manifest.json' and any(a['path']==rel and a['action']=='update-managed' for a in actions))
                if existing != content and safe_update:
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_text(content, encoding='utf-8')
                elif existing != content:
                    proposal = root / '.aimes/proposed' / f'{rel}.proposed'
                    proposal.parent.mkdir(parents=True, exist_ok=True)
                    if not proposal.exists(): proposal.write_text(content, encoding='utf-8')
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding='utf-8')
    return {'ok': not conflicts, 'root': str(root), 'dry_run': dry_run, 'tools': tools, 'actions': actions, 'conflicts': conflicts, 'message': 'No conflicts.' if not conflicts else 'Existing files were preserved; proposed replacements were staged under .aimes/proposed/.'}

def inspect_project(root: Path) -> dict[str, Any]:
    found=[]
    candidates=['.aimes/config.yaml','docs/_governance/AIMES-CORE-V1.2.md','AGENTS.md','CLAUDE.md','.github/copilot-instructions.md','.trae/rules/00-aimes-governance.md','.zcode','.qcode']
    for rel in candidates:
        p=root/rel
        if p.exists(): found.append({'path':rel,'type':'directory' if p.is_dir() else 'file','size':None if p.is_dir() else p.stat().st_size})
    git_dir=root/'.git'
    branch=None; commit=None; dirty=None
    if git_dir.exists():
        try:
            branch=subprocess.run(['git','-C',str(root),'branch','--show-current'],capture_output=True,text=True,timeout=5).stdout.strip()
            commit=subprocess.run(['git','-C',str(root),'rev-parse','--short','HEAD'],capture_output=True,text=True,timeout=5).stdout.strip()
            dirty=bool(subprocess.run(['git','-C',str(root),'status','--porcelain'],capture_output=True,text=True,timeout=5).stdout.strip())
        except Exception: pass
    return {'root':str(root),'git':{'present':git_dir.exists(),'branch':branch,'commit':commit,'dirty':dirty},'known_files':found,'configured':(root/CONFIG_REL).exists()}

def validate_project(root: Path) -> dict[str, Any]:
    findings=[]
    config_path=root/CONFIG_REL
    if not config_path.exists():
        return {'ok':False,'root':str(root),'findings':[{'level':'error','code':'CONFIG_MISSING','message':'Run `aimes init` to create .aimes/config.yaml.'}]}
    try: config=load_config(root)
    except Exception as e:
        return {'ok':False,'root':str(root),'findings':[{'level':'error','code':'CONFIG_INVALID','message':str(e)}]}
    if config.get('schema_version') != SCHEMA_VERSION: findings.append({'level':'error','code':'SCHEMA_UNSUPPORTED','message':f"schema_version must be {SCHEMA_VERSION}"})
    core = config.get('governance',{}).get('core')
    if not core: findings.append({'level':'error','code':'CORE_PATH_MISSING','message':'governance.core is not configured'})
    elif not (root/core).is_file(): findings.append({'level':'error','code':'CORE_NOT_FOUND','message':f'Governance core not found: {core}'})
    tools=config.get('tools',[])
    if not isinstance(tools,list): findings.append({'level':'error','code':'TOOLS_INVALID','message':'tools must be a list'})
    else:
        for tool in tools:
            tid=tool.get('id') if isinstance(tool,dict) else None
            if tid not in ADAPTERS: findings.append({'level':'error','code':'TOOL_UNKNOWN','message':f'Unknown adapter id: {tid}'})
            elif ADAPTERS[tid].status=='manual': findings.append({'level':'warning','code':'ADAPTER_MANUAL','message':f'{ADAPTERS[tid].label} adapter remains manual/unverified.'})
            for entry in (tool.get('entry_paths',[]) if isinstance(tool,dict) else []):
                if not (root/entry).exists(): findings.append({'level':'warning','code':'ENTRY_MISSING','message':f'Configured entry file not found: {entry}'})
    manifest_path=root/MANIFEST_REL
    if not manifest_path.exists(): findings.append({'level':'warning','code':'MANIFEST_MISSING','message':'Managed-file manifest is missing.'})
    else:
        try:
            manifest=json.loads(manifest_path.read_text(encoding='utf-8'))
            for item in manifest.get('managed_files',[]):
                p=root/item['path']
                if not p.is_file(): findings.append({'level':'warning','code':'MANAGED_FILE_MISSING','message':f"Managed file missing: {item['path']}"})
                elif sha256_text(p.read_text(encoding='utf-8',errors='replace')) != item.get('sha256'):
                    findings.append({'level':'warning','code':'MANAGED_FILE_CHANGED','message':f"Managed file differs from manifest (may be a user edit): {item['path']}"})
        except Exception as e: findings.append({'level':'error','code':'MANIFEST_INVALID','message':f'Invalid manifest: {e}'})
    errors=sum(f['level']=='error' for f in findings)
    return {'ok':errors==0,'root':str(root),'findings':findings,'summary':{'errors':errors,'warnings':sum(f['level']=='warning' for f in findings)}}

def doctor(root: Path) -> dict[str, Any]:
    tools=[]
    for key, adapter in ADAPTERS.items():
        found=[]
        for command in adapter.detection_commands:
            if shutil.which(command): found.append(command)
        tools.append({'id':key,'name':adapter.label,'commands_found':found,'adapter_status':adapter.status,'note':'Executable detection is advisory; GUI extension availability and rule loading are not proven.'})
    return {'root':str(root),'python':sys.version.split()[0],'git_available':bool(shutil.which('git')),'tools':tools}

def status(root: Path) -> dict[str, Any]:
    info=inspect_project(root); validation=validate_project(root) if info['configured'] else {'ok':False,'findings':[]}
    config=load_config(root) if info['configured'] else None
    return {'root':str(root),'configured':info['configured'],'governance_version':config.get('governance',{}).get('version') if config else None,'selected_tools':[t.get('id') for t in config.get('tools',[])] if config else [],'git':info['git'],'validation':validation}

def render_text(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, indent=2)
