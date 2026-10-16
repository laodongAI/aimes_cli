from __future__ import annotations
import argparse, json, sys
from pathlib import Path
from . import __version__
from .adapters import ADAPTERS, normalize_tools
from .core import find_root, init_project, inspect_project, validate_project, doctor, status, render_text
from .validators import validate_requirement, validate_knowledge, validate_reuse, validate_skill_registry
from .v03 import validate_trace, validate_evidence, build_context_pack
from .evaluation import validate_suite, validate_run, build_run_report, compare_runs
from .v05 import validate_adapter_evidence, adapter_report, validate_context_pack
from .mock_runner import run_mock
from .audit import append_event, validate_audit
from .publish import publish_project
from .publish_profiles import load_profiles, save_profile

def parser() -> argparse.ArgumentParser:
    p=argparse.ArgumentParser(prog='aimes', description='AIMES local-first cross-tool governance CLI')
    p.add_argument('--version', action='version', version=f'aimes {__version__}')
    sub=p.add_subparsers(dest='command', required=True)
    def common(sp):
        sp.add_argument('--root', type=Path, help='Project root (defaults to current directory / upward detection)')
        sp.add_argument('--format', choices=['text','json'], default='text')
        sp.add_argument('--output', type=Path, help='Write report to a file')
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
            if 'ok' in data: lines.append(f"Result: {'PASS' if data['ok'] else 'NEEDS ATTENTION'}")
            if 'dry_run' in data: lines.append(f"Mode: {'dry-run (no files written)' if data['dry_run'] else 'apply'}")
            if data.get('tools') and all(isinstance(item, str) for item in data['tools']): lines.append('Tools: ' + ', '.join(data['tools']))
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
    ]
    while True:
        print("\n请选择要执行的操作：")
        for i, (label, _) in enumerate(actions, 1):
            print(f"  {i}. {label}")
        print("  0. 退出")
        choice = input("请输入序号 [0-8]：").strip()
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
            dry = input("先预览变更？[Y/n]：").strip().lower() not in ("n", "no")
            if dry:
                preview = init_project(root, selected, "project", True)
                emit(preview)
                confirm = input("预览完成。确认按上述计划执行初始化？请输入 YES：").strip()
                if confirm.upper() != "YES":
                    print("未确认，已取消；没有写入文件。")
                    continue
            else:
                confirm = input("将直接写入当前项目文件。确认执行？请输入 YES：").strip()
                if confirm.upper() != "YES":
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
        for i, name in enumerate(names, 1): print(f"  {i}. {name} — {profiles[name].get('repository', '')}")
        print(f"  {len(names)+1}. 新建配置")
        choice = _ask("选择配置序号", str(len(names)+1))
        if choice.isdigit() and 1 <= int(choice) <= len(names): selected = dict(profiles[names[int(choice)-1]])
    interactive = sys.stdin.isatty() and not args.apply
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
        save_name = _ask("保存配置名称（留空不保存）", args.save_profile or "")
        if save_name:
            save_profile(save_name, {"source": source_value, "repository": repo_value, "branch": branch_value, "message": message_value, "excludes": excludes})
            print(f"已保存配置：{save_name}")
    if not repo_value or not source_value: raise ValueError("请提供 --source/--repo，或在交互向导中填写。")
    source = Path(source_value).expanduser().resolve()
    branch = branch_value.strip() or None
    if args.save_profile and not interactive:
        save_profile(args.save_profile, {"source": source, "repository": repo_value, "branch": branch or "", "message": message_value, "excludes": excludes})
    if args.apply and args.confirm != "PUBLISH":
        raise ValueError("执行发布必须同时提供 --apply --confirm PUBLISH")
    preview = publish_project(source, repo_value, branch, False, None, message_value, excludes)
    emit(preview, args.format, args.output)
    if interactive:
        if not any(preview.get("change_counts", {}).get(k, 0) for k in ("added", "updated", "deleted")):
            print("无需推送：远端与本地镜像一致。")
            return 0
        print("\n注意：完整镜像会删除删除清单中列出的远端文件。")
        if input("确认推送？请输入 PUBLISH（其他输入均取消）：").strip() != "PUBLISH":
            print("已取消；没有向 GitHub 推送。")
            return 0
        result = publish_project(source, repo_value, branch, True, "PUBLISH", message_value, excludes)
        emit(result, args.format, args.output)
        return 0 if result.get("ok") else 2
    if args.apply:
        result = publish_project(source, repo_value, branch, True, args.confirm, message_value, excludes)
        emit(result, args.format, args.output)
    return 0

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
        if args.command == 'publish':
            return run_publish_wizard(args)
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
        if args.command == 'skill':
            target = (root / args.path).resolve() if not args.path.is_absolute() else args.path.resolve()
            result = validate_skill_registry(target, root, args.id)
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
