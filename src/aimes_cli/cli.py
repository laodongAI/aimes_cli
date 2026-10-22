from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from . import __version__
from .adapters import ADAPTERS, normalize_tools
from .core import find_root, init_project, inspect_project, validate_project, doctor, status, render_text
from .validators import validate_requirement, validate_knowledge, validate_reuse, validate_skill_registry
from .v03 import validate_trace, validate_evidence, build_context_pack
from .evaluation import validate_suite, validate_run, validate_run_against_suite, build_run_report, compare_runs
from .v05 import validate_adapter_evidence, adapter_report, validate_context_pack
from .skill_execution import validate_skill_execution
from .workflow import validate_workflow_definition
from .workflow_run import start_workflow_run, transition_workflow_run, validate_workflow_run
from .runtime_probe import create_runtime_probe, validate_runtime_probe
from .mock_runner import run_mock
from .audit import append_event, validate_audit
from .publish import publish_project
from .publish_profiles import load_profiles, save_profile
from .docs_check import check_docs
from .task_state import validate_task_state, claim_task_state, release_task_state
from .cleanup_audit import audit_temp_registry
from .metrics import build_metrics_report
from .release_check import validate_release
from .upgrade import plan_upgrade, apply_upgrade
from .repair import build_repair_plan, apply_safe_repairs
from .code_repair import diagnose_command, propose_patch, apply_patch, verify_patch, rollback_patch

def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='aimes', description='AIMES local-first cross-tool governance CLI')
    p.add_argument('--version', action='version', version=f'aimes {__version__}')
    sub=p.add_subparsers(dest='command', required=True)
    def common(sp):
        sp.add_argument('--root', type=Path, help='Project root (defaults to current directory / upward detection)')
        sp.add_argument('--format', choices=['text','json'], default='text')
        sp.add_argument('--output', type=Path, help='Write report to a file')
    upgrade = sub.add_parser('upgrade', help='Safely upgrade an existing AIMES project; preview and preserve user edits')
    common(upgrade)
    upgrade.add_argument('--apply', action='store_true', help='Apply safe changes after explicit confirmation')
    upgrade.add_argument('--dry-run', action='store_true', help='Only print the plan; do not prompt or write files')
    upgrade.add_argument('--confirm', help='Must be UPGRADE to apply non-interactively')
    publish=sub.add_parser('publish', help='Interactive configuration or preview/mirror a local project to GitHub')
    publish.add_argument('--source', type=Path, help='Local project directory to mirror')
    publish.add_argument('--repo', help='GitHub repository as owner/repo or GitHub URL')
    publish.add_argument('--branch', help='Target branch; defaults to the repository default branch')
    publish.add_argument('--profile', help='Use a saved publishing profile')
    publish.add_argument('--list-profiles', action='store_true', help='List saved publishing profiles')
    publish.add_argument('--save-profile', metavar='NAME', help='Save selected settings as a reusable profile')
    publish.add_argument('--exclude', action='append', default=[], metavar='GLOB', help='Additional exclusion glob; may be repeated')
    publish.add_argument('--apply', action='store_true', help='Execute the mirror and push (preview is the default)')
    publish.add_argument('--confirm', help='Must be exactly PUBLISH when used with --apply')
    publish.add_argument('--message', default=None, help='Git commit message')
    publish.add_argument('--format', choices=['text','json'], default='text')
    publish.add_argument('--output', type=Path, help='Write report to a file')
    init=sub.add_parser('init', help='Initialize AIMES governance in the current project')
    common(init); init.add_argument('--tools', help='Comma-separated tools: trae-code,vscode-codex,vscode-claude-code,vscode-copilot,zcode,qcode,claude-code,codex-cli')
    init.add_argument('--scope', choices=['project'], default='project'); init.add_argument('--dry-run', action='store_true', help='Preview without writing files')
    conf=sub.add_parser('configure', help='Add selected tool adapters using safe merge semantics')
    common(conf); conf.add_argument('--tools', required=True); conf.add_argument('--dry-run', action='store_true')
    for name, helptext in [('inspect','Inspect project and existing rule files'),('validate','Validate AIMES configuration and managed files'),('doctor','Check local tool executable availability'),('status','Show governance deployment status'),('diff','Show a deployment preview')]:
        sp=sub.add_parser(name,help=helptext); common(sp)
        if name=='diff': sp.add_argument('--tools', default='trae-code,vscode-codex,vscode-claude-code,vscode-copilot,zcode,qcode,claude-code,codex-cli')
    repair = sub.add_parser('repair', help='Diagnose findings, preview remediation options, or safely auto-repair known issues')
    common(repair)
    repair.add_argument('--apply', action='store_true', help='Apply safe repairs; default is plan-only')
    repair.add_argument('--confirm', help='Must be REPAIR (case-insensitive) with --apply')
    repair.add_argument('--tools', help='Required if AIMES is not configured; comma-separated tool adapter IDs')
    code_repair = sub.add_parser('repair-code', help='Review, apply, verify, or roll back a business-code patch proposal')
    code_repair_sub = code_repair.add_subparsers(dest='repair_code_command', required=True)
    code_repair_diagnose = code_repair_sub.add_parser('diagnose', help='Run a user-selected test command and return evidence-backed remediation guidance')
    common(code_repair_diagnose)
    code_repair_diagnose.add_argument('--id', required=True, dest='diagnostic_id')
    code_repair_diagnose.add_argument('--test-argv-json', required=True, help='JSON argv array; command runs without shell')
    code_repair_diagnose.add_argument('--timeout-seconds', type=int, default=300)
    code_repair_propose = code_repair_sub.add_parser('propose', help='Validate and save a unified diff proposal without modifying business files')
    common(code_repair_propose)
    code_repair_propose.add_argument('patch_file', type=Path)
    code_repair_propose.add_argument('--id', required=True, dest='repair_id')
    code_repair_propose.add_argument('--finding', required=True, help='Original diagnostic finding or issue ID')
    code_repair_propose.add_argument('--rationale', default='', help='Root-cause reasoning and proposed fix summary')
    code_repair_apply = code_repair_sub.add_parser('apply', help='Apply a reviewed patch after explicit confirmation and create backups')
    common(code_repair_apply)
    code_repair_apply.add_argument('repair_id')
    code_repair_apply.add_argument('--confirm', required=True, help='Must be APPLY-FIX (case-insensitive)')
    code_repair_verify = code_repair_sub.add_parser('verify', help='Run a test command as argv (no shell) and record the result')
    common(code_repair_verify)
    code_repair_verify.add_argument('repair_id')
    code_repair_verify.add_argument('--test-argv-json', required=True, help='JSON array, e.g. ["python","-m","unittest"]')
    code_repair_verify.add_argument('--timeout-seconds', type=int, default=300)
    code_repair_rollback = code_repair_sub.add_parser('rollback', help='Restore pre-apply backups if touched files have not changed since apply')
    common(code_repair_rollback)
    code_repair_rollback.add_argument('repair_id')
    code_repair_rollback.add_argument('--confirm', required=True, help='Must be ROLLBACK-FIX (case-insensitive)')
    task = sub.add_parser('task', help='Task ownership and change-scope governance')
    task_sub = task.add_subparsers(dest='task_command', required=True)
    task_validate = task_sub.add_parser('validate', help='Validate active-writer declaration, lease, branch and changed-file scope')
    common(task_validate)
    task_validate.add_argument('path', type=Path, nargs='?', default=Path('.aimes/project-control/active-writer.yaml'))
    task_validate.add_argument('--require-active', action='store_true', help='Fail unless an unexpired ACTIVE writer declaration exists')
    task_validate.add_argument('--no-check-scope', action='store_true', help='Skip changed-file scope check (not recommended)')
    task_claim = task_sub.add_parser('claim', help='Atomically claim the local active-writer declaration')
    common(task_claim)
    task_claim.add_argument('--task-id', required=True)
    task_claim.add_argument('--tool-id', required=True, choices=list(ADAPTERS))
    task_claim.add_argument('--branch', required=True)
    task_claim.add_argument('--base-commit', required=True)
    task_claim.add_argument('--allowed-path', action='append', dest='allowed_paths', required=True, help='Allowed relative file/directory; repeat as needed')
    task_claim.add_argument('--lease-hours', type=int, default=8)
    task_claim.add_argument('--confirm', required=True, help='Must be CLAIM (case-insensitive)')
    task_claim.add_argument('--takeover', action='store_true', help='Explicitly replace only an expired/invalid active lease')
    task_release = task_sub.add_parser('release', help='Release writer declaration after a handoff file exists')
    common(task_release)
    task_release.add_argument('--task-id', required=True)
    task_release.add_argument('--tool-id', required=True, choices=list(ADAPTERS))
    task_release.add_argument('--handoff-file', required=True, help='Project-relative handoff file that must already exist')
    task_release.add_argument('--confirm', required=True, help='Must be RELEASE (case-insensitive)')
    release = sub.add_parser('release', help='Release metadata and governance compatibility checks')
    release_sub = release.add_subparsers(dest='release_command', required=True)
    release_validate = release_sub.add_parser('validate', help='Validate package/runtime/README/core-template version compatibility')
    common(release_validate)
    metrics = sub.add_parser('metrics', help='Evidence-backed engineering metrics')
    metrics_sub = metrics.add_subparsers(dest='metrics_command', required=True)
    metrics_report = metrics_sub.add_parser('report', help='Calculate available metrics; missing sources remain UNKNOWN')
    common(metrics_report)
    metrics_report.add_argument('--trace-manifest', type=Path, help='Optional trace manifest for traceability/evidence metrics')
    metrics_report.add_argument('--temp-registry', type=Path, help='Optional temporary artifact registry')
    metrics_report.add_argument('--handoff-trials', type=Path, help='Optional handoff recoverability trial registry')
    metrics_report.add_argument('--audit-log', type=Path, help='Optional audit JSONL for gate bypass count')
    cleanup = sub.add_parser('cleanup', help='Temporary artifact audit (read-only)')
    cleanup_sub = cleanup.add_subparsers(dest='cleanup_command', required=True)
    cleanup_audit = cleanup_sub.add_parser('audit', help='Report registered/expired/unregistered temporary candidates; never deletes files')
    common(cleanup_audit)
    cleanup_audit.add_argument('path', type=Path, nargs='?', default=Path('.aimes/temp-registry.yaml'))
    cleanup_audit.add_argument('--max-scan-entries', type=int, default=10000)
    docs = sub.add_parser('docs', help='Documentation integrity and thin-entry checks')
    docs_sub = docs.add_subparsers(dest='docs_command', required=True)
    docs_check = docs_sub.add_parser('check', help='Check local Markdown links and configured thin tool entries; read-only')
    common(docs_check)
    docs_check.add_argument('--max-entry-lines', type=int, default=40, help='Maximum allowed lines in a thin entry (default: 40)')
    # V0.2 structured governance registries; all validators are read-only.
    req = sub.add_parser('requirement', help='Requirement cognition record operations')
    req_sub = req.add_subparsers(dest='requirement_command', required=True)
    req_validate = req_sub.add_parser('validate', help='Validate a requirement cognition YAML/JSON record')
    common(req_validate); req_validate.add_argument('path', type=Path)
    knowledge = sub.add_parser('knowledge', help='Project knowledge asset operations')
    knowledge_sub = knowledge.add_subparsers(dest='knowledge_command', required=True)
    knowledge_validate = knowledge_sub.add_parser('validate', help='Validate a knowledge asset YAML/JSON record')
    common(knowledge_validate); knowledge_validate.add_argument('path', type=Path)
    reuse = sub.add_parser('reuse', help='Reuse decision operations')
    reuse_sub = reuse.add_subparsers(dest='reuse_command', required=True)
    reuse_validate = reuse_sub.add_parser('validate', help='Validate a reuse decision YAML/JSON record')
    common(reuse_validate); reuse_validate.add_argument('path', type=Path)
    skill = sub.add_parser('skill', help='Skill registry operations')
    skill_sub = skill.add_subparsers(dest='skill_command', required=True)
    skill_validate = skill_sub.add_parser('validate', help='Validate a Skill registry and its referenced files')
    common(skill_validate); skill_validate.add_argument('path', type=Path, nargs='?', default=Path('.aimes/skills/registry.yaml'))
    skill_validate.add_argument('--id', help='Validate a single Skill ID; default validates all entries')
    skill_execution = skill_sub.add_parser('execution', help='Skill execution record operations')
    skill_execution_sub = skill_execution.add_subparsers(dest='skill_execution_command', required=True)
    skill_execution_validate = skill_execution_sub.add_parser('validate', help='Validate a structured Skill execution record; does not execute the Skill')
    common(skill_execution_validate); skill_execution_validate.add_argument('path', type=Path)
    workflow = sub.add_parser('workflow', help='Declarative workflow state machine operations')
    workflow_sub = workflow.add_subparsers(dest='workflow_command', required=True)
    workflow_validate = workflow_sub.add_parser('validate', help='Validate workflow states, transitions, failure paths, and retry policy; does not execute the workflow')
    common(workflow_validate); workflow_validate.add_argument('path', type=Path)
    workflow_run = workflow_sub.add_parser('run', help='Persistent local workflow run state')
    workflow_run_sub = workflow_run.add_subparsers(dest='workflow_run_command', required=True)
    workflow_run_start = workflow_run_sub.add_parser('start', help='Create a new run record without overwriting existing files')
    common(workflow_run_start); workflow_run_start.add_argument('definition', type=Path); workflow_run_start.add_argument('--record', type=Path, required=True)
    workflow_run_start.add_argument('--run-id', required=True); workflow_run_start.add_argument('--task-id', required=True); workflow_run_start.add_argument('--baseline-commit', required=True)
    workflow_run_start.add_argument('--actor', default='local-user'); workflow_run_start.add_argument('--approval-ref'); workflow_run_start.add_argument('--confirm', required=True, help='Must be START (case-insensitive)')
    workflow_run_validate = workflow_run_sub.add_parser('validate', help='Validate a run record against its exact workflow definition')
    common(workflow_run_validate); workflow_run_validate.add_argument('definition', type=Path); workflow_run_validate.add_argument('record', type=Path)
    workflow_run_transition = workflow_run_sub.add_parser('transition', help='Record an allowed state transition with backup and explicit confirmation')
    common(workflow_run_transition); workflow_run_transition.add_argument('definition', type=Path); workflow_run_transition.add_argument('record', type=Path)
    workflow_run_transition.add_argument('--event', required=True); workflow_run_transition.add_argument('--actor', default='local-user')
    workflow_run_transition.add_argument('--evidence-ref', action='append', dest='evidence_refs', default=[])
    workflow_run_transition.add_argument('--approval-ref'); workflow_run_transition.add_argument('--guard-evidence')
    workflow_run_transition.add_argument('--confirm', required=True, help='Must be TRANSITION (case-insensitive)')
    trace = sub.add_parser('trace', help='End-to-end engineering traceability operations')
    trace_sub = trace.add_subparsers(dest='trace_command', required=True)
    trace_validate = trace_sub.add_parser('validate', help='Validate trace links and VERIFIED evidence gates')
    common(trace_validate); trace_validate.add_argument('path', type=Path)
    evidence = sub.add_parser('evidence', help='Evidence registry operations')
    evidence_sub = evidence.add_subparsers(dest='evidence_command', required=True)
    evidence_validate = evidence_sub.add_parser('validate', help='Validate recorded command/test/build evidence without executing it')
    common(evidence_validate); evidence_validate.add_argument('path', type=Path)
    evaluation = sub.add_parser('evaluation', help='AI engineering evaluation suite and regression operations')
    evaluation_sub = evaluation.add_subparsers(dest='evaluation_command', required=True)
    evaluation_validate = evaluation_sub.add_parser('validate', help='Validate a versioned evaluation suite')
    common(evaluation_validate); evaluation_validate.add_argument('path', type=Path)
    evaluation_run_validate = evaluation_sub.add_parser('validate-run', help='Validate run completeness and hard-gate coverage against a fixed suite')
    common(evaluation_run_validate); evaluation_run_validate.add_argument('run', type=Path); evaluation_run_validate.add_argument('--suite', type=Path, required=True)
    evaluation_report = evaluation_sub.add_parser('report', help='Summarize a recorded evaluation run; does not execute tasks')
    common(evaluation_report); evaluation_report.add_argument('path', type=Path)
    evaluation_compare = evaluation_sub.add_parser('compare', help='Compare baseline and candidate run records')
    common(evaluation_compare); evaluation_compare.add_argument('baseline', type=Path); evaluation_compare.add_argument('candidate', type=Path)
    evaluation_mock = evaluation_sub.add_parser('run-mock', help='Run deterministic fixture checks; does not call a model')
    common(evaluation_mock); evaluation_mock.add_argument('path', type=Path, help='Evaluation suite YAML/JSON')
    evaluation_mock.add_argument('--responses', type=Path, required=True, help='Fixture response YAML/JSON')
    evaluation_mock.add_argument('--case-id', action='append', dest='case_ids', help='Limit to a case ID; may be repeated')
    adapter = sub.add_parser('adapter', help='Cross-tool runtime verification evidence')
    adapter_sub = adapter.add_subparsers(dest='adapter_command', required=True)
    adapter_validate = adapter_sub.add_parser('validate', help='Validate recorded tool rule-loading evidence; does not probe IDE internals')
    common(adapter_validate); adapter_validate.add_argument('path', type=Path)
    adapter_report_cmd = adapter_sub.add_parser('report', help='Summarize tool verification coverage')
    common(adapter_report_cmd); adapter_report_cmd.add_argument('path', type=Path)
    adapter_probe = adapter_sub.add_parser('probe', help='Create or validate an isolated native rule-loading probe')
    adapter_probe_sub = adapter_probe.add_subparsers(dest='adapter_probe_command', required=True)
    adapter_probe_create = adapter_probe_sub.add_parser('create', help='Create a disposable probe project; does not launch an AI tool')
    common(adapter_probe_create); adapter_probe_create.add_argument('--tool', choices=['codex-cli','claude-code'], required=True)
    adapter_probe_create.add_argument('--output-dir', type=Path, required=True); adapter_probe_create.add_argument('--product-version', required=True)
    adapter_probe_create.add_argument('--governance-version', default='1.2'); adapter_probe_create.add_argument('--observer', default='')
    adapter_probe_validate = adapter_probe_sub.add_parser('validate', help='Validate the raw response and write a V2 runtime evidence record')
    common(adapter_probe_validate); adapter_probe_validate.add_argument('probe_dir', type=Path); adapter_probe_validate.add_argument('--observer', default='')
    audit = sub.add_parser('audit', help='Local structured audit event operations')
    audit_sub = audit.add_subparsers(dest='audit_command', required=True)
    audit_validate = audit_sub.add_parser('validate', help='Validate JSONL audit event structure')
    common(audit_validate); audit_validate.add_argument('path', type=Path)
    audit_append = audit_sub.add_parser('append', help='Append a redacted JSONL audit event')
    common(audit_append); audit_append.add_argument('path', type=Path); audit_append.add_argument('--run-id', required=True)
    audit_append.add_argument('--event-type', required=True); audit_append.add_argument('--status', required=True)
    audit_append.add_argument('--actor', default='aimes-cli'); audit_append.add_argument('--details-json', default='{}')
    context = sub.add_parser('context', help='Persistent context and handoff operations')
    context_sub = context.add_subparsers(dest='context_command', required=True)
    context_pack = context_sub.add_parser('pack', help='Generate context-pack.json and HANDOFF.md from a trace manifest')
    common(context_pack); context_pack.add_argument('path', type=Path)
    context_pack.add_argument('--output-dir', type=Path, default=Path('.aimes/context-pack'))
    context_validate = context_sub.add_parser('validate', help='Verify Context Pack source-file hashes and optional HANDOFF file')
    common(context_validate); context_validate.add_argument('path', type=Path); context_validate.add_argument('--handoff', type=Path)
    return p

def choose_tools(raw: str | None) -> list[str]:
    if raw: return normalize_tools(raw)
    print('Select development tool entry points (comma-separated numbers):')
    keys=list(ADAPTERS)
    for i,k in enumerate(keys,1): print(f'  {i}. {ADAPTERS[k].label}'+(' [manual verification]' if ADAPTERS[k].status=='manual' else ''))
    answer=input('Selection (e.g. 1,5,7,8): ').strip()
    if not answer: raise ValueError('At least one tool must be selected.')
    selected=[]
    for part in answer.split(','):
        try: selected.append(keys[int(part.strip())-1])
        except (ValueError,IndexError): raise ValueError(f'Invalid selection: {part}')
    return list(dict.fromkeys(selected))

def emit(data, fmt='text', output: Path | None=None):
    if fmt == 'json':
        rendered = json.dumps(data, ensure_ascii=False, indent=2)
    else:
        lines = ['AIMES CLI report']
        if isinstance(data, dict):
            if data.get('root'): lines.append(f"Project: {data['root']}")
            if data.get('installed_cli_version') is not None: lines.append(f"Installed AIMES CLI version: {data['installed_cli_version']}")
            if data.get('project_cli_version') is not None: lines.append(f"Project manifest CLI version: {data['project_cli_version']}")
            if data.get('project_cli_version_before') is not None: lines.append(f"Project manifest CLI version before upgrade: {data['project_cli_version_before']}")
            if data.get('governance_target_version') is not None: lines.append(f"Target governance version: {data['governance_target_version']}")
            if 'ok' in data: lines.append(f"Result: {'PASS' if data['ok'] else 'NEEDS ATTENTION'}")
            if 'dry_run' in data: lines.append(f"Mode: {'dry-run (no files written)' if data['dry_run'] else 'apply'}")
            if data.get('tools') and all(isinstance(item, str) for item in data['tools']): lines.append('Tools: ' + ', '.join(data['tools']))
            if data.get('written'):
                lines.append('Files written:')
                for item in data['written']: lines.append(f"  - {item.get('action', 'write')}: {item['path']}")
            if data.get('preserved'):
                lines.append('Preserved files / proposals:')
                for item in data['preserved']:
                    if isinstance(item, dict): lines.append(f"  - {item.get('path', '?')}: {item.get('reason', '')}" + (f" -> {item['proposal_path']}" if item.get('proposal_path') else ''))
                    else: lines.append(f"  - {item}")
            if data.get('errors'):
                lines.append('Errors:')
                for item in data['errors']: lines.append(f"  - {item.get('path', '?')}: {item.get('error', '')}")
            if data.get('backup_dir'): lines.append(f"Backup directory: {data['backup_dir']}")
            if data.get('actions'):
                lines.append('Actions:')
                for action in data['actions']:
                    suffix = f" -> {action['proposed_path']}" if action.get('proposed_path') else ''
                    lines.append(f"  - {action['action']}: {action['path']}{suffix}")
            if data.get('conflicts'):
                lines.append('Conflicts:')
                for conflict in data['conflicts']: lines.append(f"  - {conflict['path']} (preserved; review proposal)")
            if data.get('findings'):
                lines.append('Findings:')
                for finding in data['findings']: lines.append(f"  - [{finding['level']}] {finding['code']}: {finding['message']}")
            if data.get('message'): lines.append(data['message'])
            if data.get('configured') is not None: lines.append(f"Configured: {data['configured']}")
            if data.get('selected_tools'): lines.append('Selected tools: ' + ', '.join(data['selected_tools']))
            if data.get('git'): lines.append('Git: ' + json.dumps(data['git'], ensure_ascii=False))
            if data.get('tools') and isinstance(data['tools'], list) and data['tools'] and isinstance(data['tools'][0], dict) and 'commands_found' in data['tools'][0]:
                lines.append('Tool detection:')
                for tool in data['tools']:
                    found = ', '.join(tool.get('commands_found', [])) or 'no matching CLI executable detected'
                    lines.append(f"  - {tool['name']}: {found} [{tool['adapter_status']}]")
                lines.append('Detection is advisory; it does not prove extension availability or rule loading.')
            if data.get('tools') and isinstance(data['tools'], dict):
                lines.append('Adapter verification by tool:')
                for tool_id, stats in data['tools'].items():
                    if isinstance(stats, dict) and stats.get('checks', 0):
                        lines.append(f"  - {tool_id}: PASS={stats.get('pass', 0)}, FAIL={stats.get('fail', 0)}, BLOCKED={stats.get('blocked', 0)}, NOT_RUN={stats.get('not_run', 0)}, UNKNOWN={stats.get('unknown', 0)}")
            if data.get('execution_modes') and isinstance(data['execution_modes'], dict):
                lines.append('Adapter verification by execution mode:')
                for mode, stats in data['execution_modes'].items():
                    lines.append(f"  - {mode}: PASS={stats.get('pass', 0)}, FAIL={stats.get('fail', 0)}, BLOCKED={stats.get('blocked', 0)}, NOT_RUN={stats.get('not_run', 0)}, UNKNOWN={stats.get('unknown', 0)}")
            if data.get('remote_empty'):
                lines.append('Remote repository: empty (no commits yet); first publish will create the initial commit.')
            if data.get('changes'):
                lines.append('Mirror changes (added/updated/deleted/unchanged):')
                for kind in ('added', 'updated', 'deleted', 'unchanged'):
                    paths = data['changes'].get(kind, [])
                    lines.append(f'  {kind}: {len(paths)}')
                    for path in paths[:30]: lines.append(f'    - {path}')
                    if len(paths) > 30: lines.append(f'    ... 另有 {len(paths) - 30} 项')
            if data.get('detected_stacks'):
                lines.append('Detected project stack: ' + ', '.join(data['detected_stacks']))
            if data.get('auto_excludes'):
                lines.append(f"Auto-selected exclusion rules: {len(data['auto_excludes'])} rule(s) (built-in + project markers + .gitignore)")
            if data.get('excluded_preview'):
                lines.append('Excluded environment/cache/runtime paths (preview up to 100):')
                for path in data['excluded_preview']: lines.append(f'  - {path}')
            if data.get('custom_excludes'):
                lines.append('Additional custom exclusion rules: ' + ', '.join(data['custom_excludes']))
            if data.get('secret_findings'):
                lines.append('Potential secret findings:')
                for item in data['secret_findings']: lines.append('  - ' + str(item.get('path')) + ': ' + str(item.get('reason')))
            if data.get('warning'): lines.append('WARNING: ' + data['warning'])
            if data.get('commit_url'): lines.append('Commit: ' + data['commit_url'])
            if data.get('repository_url'): lines.append('Repository: ' + data['repository_url'])
            if data.get('known_files'):
                lines.append('Known files:')
                for item in data['known_files']: lines.append(f"  - {item['path']} ({item['type']})")
            if data.get('validation', {}).get('summary'):
                summary=data['validation']['summary']
                lines.append(f"Validation: {summary['errors']} error(s), {summary['warnings']} warning(s)")
        rendered='\n'.join(lines)
    if output:
        output.parent.mkdir(parents=True,exist_ok=True); output.write_text(rendered+'\n',encoding='utf-8')
    print(rendered)

def interactive_wizard():
    """交互式主菜单：让用户先选择任务，再逐步选择参数。"""
    print(f"\nAIMES 智能工程助手 v{__version__}")
    print("当前目录：" + str(Path.cwd()))
    actions = [
        ("初始化项目", "init"),
        ("配置 AI 工具", "configure"),
        ("检查项目文件", "inspect"),
        ("验证项目配置", "validate"),
        ("检查本机工具环境", "doctor"),
        ("查看部署状态", "status"),
        ("预览配置变更", "diff"),
        ("发布项目到 GitHub", "publish"),
        ("升级现有项目 AIMES", "upgrade"),
    ]
    while True:
        print("\n请选择要执行的操作：")
        for i, (label, _) in enumerate(actions, 1):
            print(f"  {i}. {label}")
        print("  0. 退出")
        choice = input("请输入序号 [0-9]：").strip()
        if choice in ("0", "q", "quit", "exit"):
            print("已退出 AIMES。")
            return 0
        if not choice.isdigit() or not (1 <= int(choice) <= len(actions)):
            print("输入无效，请输入菜单中的序号。")
            continue
        label, command = actions[int(choice)-1]
        if command == "publish":
            try: run_publish_wizard()
            except (ValueError, OSError) as exc: print(f"发布配置错误：{exc}")
            continue
        if command == "upgrade":
            try:
                run_upgrade_wizard(Path.cwd().resolve())
            except (ValueError, OSError, EOFError, KeyboardInterrupt) as exc:
                print(f"升级已取消或失败：{exc}")
            continue
        if command in ("init", "configure", "diff"):
            keys = list(ADAPTERS)
            print("\n请选择工具，可输入多个序号并用逗号分隔：")
            for i, key in enumerate(keys, 1):
                adapter = ADAPTERS[key]
                note = "（需人工核验入口）" if adapter.status == "manual" else ""
                print(f"  {i}. {adapter.label} [{key}]{note}")
            raw = input("工具序号，例如 7,8（回车取消）：").strip()
            if not raw:
                print("已取消本次操作。")
                continue
            try:
                selected = []
                for item in raw.replace("，", ",").split(","):
                    index = int(item.strip())
                    if index < 1 or index > len(keys):
                        raise ValueError(f"工具序号超出范围：{item}")
                    if keys[index-1] not in selected:
                        selected.append(keys[index-1])
            except ValueError as exc:
                print(f"选择无效：{exc}")
                continue
            if command == "configure":
                command = "configure"
            elif command == "diff":
                result = init_project(find_root().resolve(), selected, "project", True)
                emit(result)
                continue
            # 交互式向导承诺操作“当前项目目录”，因此不向上自动跳到父级 Git 仓库。
            root = Path.cwd().resolve()
            print(f"\n项目范围：{root}（仅修改此目录，不修改用户全局配置）")
            dry = _ask_yes_no("先预览变更？", default=True)
            if dry:
                preview = init_project(root, selected, "project", True)
                emit(preview)
                if not _confirm_word("预览完成。确认按上述计划执行初始化？请输入 YES（输入 N 取消）：", "YES"):
                    print("未确认，已取消；没有写入文件。")
                    continue
            else:
                if not _confirm_word("将直接写入当前项目文件。确认执行？请输入 YES（输入 N 取消）：", "YES"):
                    print("未确认，已取消；没有写入文件。")
                    continue
            result = init_project(root, selected, "project", False)
            emit(result)
            continue
        result = {
            "inspect": inspect_project,
            "validate": validate_project,
            "doctor": doctor,
            "status": status,
        }[command](find_root().resolve())
        emit(result)



def _ask(label: str, default: str = "") -> str:
    suffix = f" [{default}]" if default else ""
    return input(f"{label}{suffix}：").strip() or default


def _confirm_word(prompt: str, expected: str, cancel_words=("n", "no", "cancel", "c", "q", "quit", "exit")) -> bool:
    """要求用户输入确认词；大小写不敏感，输错时重试，明确取消词才退出。"""
    while True:
        answer = input(prompt).strip()
        normalized = answer.casefold()
        if normalized == expected.casefold():
            return True
        if normalized in cancel_words:
            return False
        print(f"输入无效，请输入 {expected} 确认，或输入 N 取消。")


def _ask_yes_no(prompt: str, default: bool = True) -> bool:
    """大小写不敏感的 Y/N 确认；无效输入会重试。"""
    suffix = "[Y/n]" if default else "[y/N]"
    while True:
        answer = input(f"{prompt} {suffix}：").strip().casefold()
        if not answer:
            return default
        if answer in ("y", "yes"):
            return True
        if answer in ("n", "no"):
            return False
        print("输入无效，请输入 Y/YES 或 N/NO。")


def run_publish_wizard(args=None) -> int:
    """发布向导：配置选择、差异预览、显式确认推送。"""
    args = args or argparse.Namespace(source=None, repo=None, branch=None, profile=None, list_profiles=False, save_profile=None, exclude=[], apply=False, confirm=None, message=None, format="text", output=None)
    profiles = load_profiles()
    if args.list_profiles:
        for name, item in profiles.items():
            print(f"  {name}: {item.get('source', '')} -> {item.get('repository', '')} [{item.get('branch') or '默认分支'}]")
        if not profiles: print("暂无已保存的发布配置。")
        return 0
    selected = {}
    if args.profile:
        if args.profile not in profiles: raise ValueError(f"未找到发布配置：{args.profile}。请先运行 aimes publish --list-profiles。")
        selected = dict(profiles[args.profile])
    elif not args.source and not args.repo and sys.stdin.isatty() and profiles:
        names = list(profiles)
        print("\n已保存的发布配置：")
        for i, name in enumerate(names, 1):
            marker = " [上次使用]" if name == "上次使用" else ""
            print(f"  {i}. {name}{marker} — {profiles[name].get('repository', '')}")
        print(f"  {len(names)+1}. 新建配置")
        default_choice = str(names.index("上次使用") + 1) if "上次使用" in names else "1"
        choice = _ask("选择配置序号", default_choice)
        if choice.isdigit() and 1 <= int(choice) <= len(names):
            selected = dict(profiles[names[int(choice)-1]])
    interactive = sys.stdin.isatty() and not args.apply and not getattr(args, "dry_run", False)
    source_value = str(args.source or selected.get("source") or Path.cwd())
    repo_value = args.repo or selected.get("repository") or ""
    branch_value = args.branch if args.branch is not None else selected.get("branch", "")
    message_value = args.message or selected.get("message") or "chore: mirror local project with AIMES"
    excludes = list(selected.get("excludes") or []) + list(args.exclude or [])
    if interactive:
        source_value = _ask("本地项目目录", source_value)
        repo_value = _ask("GitHub 仓库（owner/repo）", repo_value)
        branch_value = _ask("目标分支（留空使用默认分支）", branch_value)
        message_value = _ask("提交说明", message_value)
        if excludes: print("已加载配置中的自定义排除规则：" + ", ".join(excludes))
        if not repo_value: raise ValueError("必须提供 GitHub 仓库，例如 laodongAI/my-project")
        current_profile = {"source": source_value, "repository": repo_value, "branch": branch_value, "message": message_value, "excludes": excludes}
        # Always remember the last interactive configuration; named profiles remain separately reusable.
        save_profile("上次使用", current_profile)
        print("已自动记住本次发布配置；下次进入向导将默认使用。")
        save_name = _ask("另存为配置名称（留空跳过）", args.save_profile or "")
        if save_name and save_name != "上次使用":
            save_profile(save_name, current_profile)
            print(f"已保存配置：{save_name}")
    if not repo_value or not source_value: raise ValueError("请提供 --source/--repo，或在交互向导中填写。")
    source = Path(source_value).expanduser().resolve()
    branch = branch_value.strip() or None
    if args.save_profile and not interactive:
        save_profile(args.save_profile, {"source": source, "repository": repo_value, "branch": branch or "", "message": message_value, "excludes": excludes})
    if args.apply and (args.confirm or "").strip().casefold() != "publish":
        raise ValueError("执行发布必须同时提供 --apply --confirm PUBLISH")
    preview = publish_project(source, repo_value, branch, False, None, message_value, excludes)
    emit(preview, args.format, args.output)
    if interactive:
        if not any(preview.get("change_counts", {}).get(k, 0) for k in ("added", "updated", "deleted")):
            print("无需推送：远端与本地镜像一致。")
            return 0
        print("\n注意：完整镜像会删除删除清单中列出的远端文件。")
        if not _confirm_word("确认推送？请输入 PUBLISH（大小写不限，输入 N 取消）：", "PUBLISH"):
            print("已取消；没有向 GitHub 推送。")
            return 0
        result = publish_project(source, repo_value, branch, True, "PUBLISH", message_value, excludes)
        emit(result, args.format, args.output)
        return 0 if result.get("ok") else 2
    if args.apply:
        result = publish_project(source, repo_value, branch, True, "PUBLISH", message_value, excludes)
        emit(result, args.format, args.output)
    return 0

def run_upgrade_wizard(root: Path, args=None) -> int:
    """Preview and guide an existing project through a non-destructive AIMES upgrade."""
    args = args or argparse.Namespace(apply=False, dry_run=False, confirm=None, format="text", output=None)
    plan = plan_upgrade(root)
    emit(plan, args.format, args.output)
    if not plan.get("ok"):
        return 2

    actions = [item for item in plan.get("actions", []) if item.get("action") != "unchanged"]
    if not actions:
        print("当前项目文件与已安装 AIMES 模板一致，无需升级。")
        return 0

    interactive = sys.stdin.isatty() and not args.apply
    if interactive:
        selected = []
        print("\n逐项确认升级操作：")
        for item in actions:
            kind = item["action"]
            path = item["path"]
            if kind in ("add", "update-managed"):
                prompt = f"{kind}: {path}。该文件是新增文件或已证明未被修改的 AIMES 管理文件，是否应用？"
            else:
                prompt = f"{kind}: {path}。检测到可能的项目自定义内容，是否仅生成候选文件供人工合并（原文件绝不覆盖）？"
            if _ask_yes_no(prompt, default=True):
                selected.append(path)
        if not selected:
            print("没有选择任何升级项；未修改项目文件。")
            return 0
        if not _confirm_word("确认执行已选择的升级步骤？请输入 UPGRADE（输入 N 取消）：", "UPGRADE"):
            print("已取消；未应用升级。")
            return 0
        result = apply_upgrade(root, selected)
    elif args.apply:
        if (args.confirm or "").strip().casefold() != "upgrade":
            raise ValueError("非交互升级必须同时提供 --apply --confirm UPGRADE")
        result = apply_upgrade(root)
    else:
        print("\n当前为只读预览。交互式终端可直接运行 aimes upgrade 并逐项确认；脚本执行请使用 --apply --confirm UPGRADE。")
        return 0

    emit(result, args.format, args.output)
    if result.get("backup_dir"):
        print("升级备份目录：" + result["backup_dir"])
    print("建议升级后执行：aimes validate --root \"" + str(root) + "\"")
    return 0 if result.get("ok") else 2


def main(argv=None):
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        if sys.stdin.isatty():
            try:
                return interactive_wizard()
            except (EOFError, KeyboardInterrupt):
                print("\n已取消。")
                return 130
        parser().print_help()
        return 0
    args=parser().parse_args(argv)
    root=(getattr(args, 'root', None) or find_root()).resolve()
    try:
        if args.command == 'repair':
            if args.apply:
                result = apply_safe_repairs(root, confirm=args.confirm, tools=args.tools)
            else:
                result = build_repair_plan(root)
                result['apply_hint'] = 'Review the options above, then rerun with --apply --confirm REPAIR; add --tools when .aimes/config.yaml is missing.'
            emit(result, args.format, args.output)
            return 0 if result.get('ok', False) else (1 if not args.apply else 2)
        if args.command == 'repair-code':
            if args.repair_code_command == 'diagnose':
                result = diagnose_command(root, diagnostic_id=args.diagnostic_id, test_argv_json=args.test_argv_json, timeout_seconds=args.timeout_seconds)
            elif args.repair_code_command == 'propose':
                patch_file = (root / args.patch_file).resolve() if not args.patch_file.is_absolute() else args.patch_file.resolve()
                result = propose_patch(root, patch_file, repair_id=args.repair_id, finding=args.finding, rationale=args.rationale)
            elif args.repair_code_command == 'apply':
                result = apply_patch(root, args.repair_id, confirm=args.confirm)
            elif args.repair_code_command == 'verify':
                result = verify_patch(root, args.repair_id, test_argv_json=args.test_argv_json, timeout_seconds=args.timeout_seconds)
            else:
                result = rollback_patch(root, args.repair_id, confirm=args.confirm)
            emit(result, args.format, args.output)
            return 0 if result.get('ok', False) else 1
        if args.command == 'publish':
            return run_publish_wizard(args)
        if args.command == 'upgrade':
            return run_upgrade_wizard(root, args)
        if args.command in ('init','configure'):
            tools=choose_tools(args.tools)
            result=init_project(root,tools,getattr(args,'scope','project'),args.dry_run)
            emit(result,args.format,args.output)
            return 0 if result['ok'] else 2
        if args.command == 'requirement':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_requirement(target)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'knowledge':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_knowledge(target, root)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'reuse':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_reuse(target)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'workflow' and args.workflow_command == 'validate':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_workflow_definition(target)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'workflow' and args.workflow_command == 'run':
            definition = (root / args.definition).resolve() if not args.definition.is_absolute() else args.definition.resolve()
            if args.workflow_run_command == 'start':
                record = (root / args.record).resolve() if not args.record.is_absolute() else args.record.resolve()
                result = start_workflow_run(definition, record, root, run_id=args.run_id, task_id=args.task_id, baseline_commit=args.baseline_commit, actor=args.actor, approval_ref=args.approval_ref, confirm=args.confirm)
            else:
                record = (root / args.record).resolve() if not args.record.is_absolute() else args.record.resolve()
                if args.workflow_run_command == 'validate':
                    result = validate_workflow_run(definition, record, root)
                elif args.workflow_run_command == 'transition':
                    result = transition_workflow_run(definition, record, root, event=args.event, actor=args.actor, evidence_refs=args.evidence_refs, approval_ref=args.approval_ref, guard_evidence=args.guard_evidence, confirm=args.confirm)
                else:
                    raise ValueError(f"Unsupported workflow run command: {args.workflow_run_command}")
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'skill':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            if args.skill_command == 'validate':
                result = validate_skill_registry(target, root, args.id)
            elif args.skill_command == 'execution' and args.skill_execution_command == 'validate':
                result = validate_skill_execution(target)
            else:
                raise ValueError(f"Unsupported Skill command: {args.skill_command}")
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'release' and args.release_command == 'validate':
            result = validate_release(root)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'metrics' and args.metrics_command == 'report':
            result = build_metrics_report(root, trace_manifest=args.trace_manifest,
                temp_registry=args.temp_registry, handoff_trials=args.handoff_trials, audit_log=args.audit_log)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'cleanup' and args.cleanup_command == 'audit':
            if args.max_scan_entries < 1:
                raise ValueError('--max-scan-entries must be greater than zero')
            registry = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = audit_temp_registry(root, registry, max_scan_entries=args.max_scan_entries)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'task' and args.task_command == 'claim':
            result = claim_task_state(root, task_id=args.task_id, tool_id=args.tool_id, branch=args.branch,
                base_commit=args.base_commit, allowed_paths=args.allowed_paths, lease_hours=args.lease_hours,
                confirm=args.confirm, takeover=args.takeover)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'task' and args.task_command == 'release':
            result = release_task_state(root, task_id=args.task_id, tool_id=args.tool_id,
                handoff_file=args.handoff_file, confirm=args.confirm)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'task' and args.task_command == 'validate':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_task_state(target, root, require_active=args.require_active, check_scope=not args.no_check_scope)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'docs' and args.docs_command == 'check':
            if args.max_entry_lines < 1:
                raise ValueError('--max-entry-lines must be greater than zero')
            result = check_docs(root, max_entry_lines=args.max_entry_lines)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'trace':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_trace(target, root)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'evidence':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_evidence(target, root)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'evaluation':
            if args.evaluation_command == 'validate':
                target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
                result = validate_suite(target)
                emit(result, args.format, args.output)
                return 0 if result['ok'] else 1
            if args.evaluation_command == 'validate-run':
                run_path = (root / args.run).resolve() if not args.run.is_absolute() else args.run.resolve()
                suite_path = (root / args.suite).resolve() if not args.suite.is_absolute() else args.suite.resolve()
                result = validate_run_against_suite(suite_path, run_path)
                emit(result, args.format, args.output)
                return 0 if result['ok'] else 1
            if args.evaluation_command == 'report':
                target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
                validation = validate_run(target)
                report = build_run_report(target)
                result = {'ok': validation['ok'], 'validation': validation, 'report': report}
                emit(result, args.format, args.output)
                return 0 if validation['ok'] else 1
            if args.evaluation_command == 'compare':
                baseline = (root / args.baseline).resolve() if not args.baseline.is_absolute() else args.baseline.resolve()
                candidate = (root / args.candidate).resolve() if not args.candidate.is_absolute() else args.candidate.resolve()
                result = compare_runs(baseline, candidate)
                emit(result, args.format, args.output)
                return 0 if result['ok'] else 1
            if args.evaluation_command == 'run-mock':
                target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
                responses = (root / args.responses).resolve() if not args.responses.is_absolute() else args.responses.resolve()
                result = run_mock(target, responses, args.case_ids)
                emit(result, args.format, args.output)
                return 0 if all(x.get('status') == 'PASS' for x in result['case_results']) and result['case_results'] else 1
        if args.command == 'audit':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            if args.audit_command == 'validate':
                result = validate_audit(target)
            else:
                try:
                    details = json.loads(args.details_json)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"--details-json JSON 格式错误（第 {exc.lineno} 行，第 {exc.colno} 列）：{exc.msg}") from exc
                if not isinstance(details, dict):
                    raise ValueError('--details-json 必须是 JSON 对象')
                event = append_event(target, run_id=args.run_id, event_type=args.event_type, status=args.status, actor=args.actor, details=details)
                result = {'ok': True, 'event': event, 'note': '本地 JSONL 事件已追加；日志不具备自动防篡改保证。'}
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'adapter':
            if args.adapter_command == 'probe':
                if args.adapter_probe_command == 'create':
                    output_dir = (root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()
                    result = create_runtime_probe(root, output_dir, tool=args.tool, product_version=args.product_version, governance_version=args.governance_version, observer=args.observer)
                else:
                    probe_dir = (root / args.probe_dir).resolve() if not args.probe_dir.is_absolute() else args.probe_dir.resolve()
                    result = validate_runtime_probe(root, probe_dir, observer=args.observer)
            else:
                target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
                result = validate_adapter_evidence(target, root) if args.adapter_command == 'validate' else adapter_report(target, root)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'context' and args.context_command == 'validate':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            handoff = args.handoff
            result = validate_context_pack(target, root, handoff)
            emit(result, args.format, args.output)
            return 0 if result['ok'] else 1
        if args.command == 'context':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            outdir = (root / args.output_dir).resolve() if not args.output_dir.is_absolute() else args.output_dir.resolve()
            result = build_context_pack(target, outdir, root)
            emit(result, args.format, args.output)
            return 0
        if args.command=='inspect': result=inspect_project(root)
        elif args.command=='validate': result=validate_project(root)
        elif args.command=='doctor': result=doctor(root)
        elif args.command=='status': result=status(root)
        elif args.command=='diff':
            tools=normalize_tools(args.tools)
            result=init_project(root,tools,'project',True)
        else: raise ValueError(args.command)
        emit(result,args.format,args.output)
        if args.command=='validate' and not result['ok']: return 2
        return 0
    except (ValueError, OSError) as e:
        print(f'aimes: error: {e}',file=sys.stderr); return 2

if __name__=='__main__':
    raise SystemExit(main())
