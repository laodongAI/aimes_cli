from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any
import yaml
from .v03 import _load, _report, _add
from .adapters import ADAPTERS

VALID_VERIFICATION = {"NOT_RUN", "PASS", "FAIL", "BLOCKED", "UNKNOWN"}
VALID_METHODS = {"manual_prompt", "file_inspection", "runtime_observation", "automated_check", "user_confirmed"}

def validate_adapter_evidence(path: Path, root: Path | None = None) -> dict:
    data = _load(path); fs=[]; root=(root or path.parent).resolve()
    if not isinstance(data, dict) or not isinstance(data.get("checks"), list):
        _add(fs,"ERROR","ROOT_SHAPE","Adapter evidence must be an object with a checks list")
        return _report("adapter-evidence",path,fs,checked_checks=0)
    seen=set(); checked=0
    for i,item in enumerate(data["checks"]):
        loc=f"checks[{i}]"
        if not isinstance(item,dict): _add(fs,"ERROR","ENTRY_TYPE",f"{loc} must be an object"); continue
        checked+=1; cid=item.get("id")
        if not isinstance(cid,str) or not cid.strip(): _add(fs,"ERROR","ID_REQUIRED",f"{loc}.id is required")
        elif cid in seen: _add(fs,"ERROR","DUPLICATE_ID",f"Duplicate check id: {cid}")
        else: seen.add(cid)
        tool=item.get("tool")
        if tool not in ADAPTERS: _add(fs,"ERROR","UNKNOWN_TOOL",f"{loc}.tool must be one of {sorted(ADAPTERS)}")
        if item.get("verification") not in VALID_VERIFICATION: _add(fs,"ERROR","VERIFICATION_STATUS",f"{loc}.verification must be one of {sorted(VALID_VERIFICATION)}")
        if item.get("method") not in VALID_METHODS: _add(fs,"ERROR","VERIFICATION_METHOD",f"{loc}.method must be one of {sorted(VALID_METHODS)}")
        if item.get("verification")=="PASS" and item.get("method") not in {"runtime_observation","automated_check","user_confirmed"}:
            _add(fs,"ERROR","INSUFFICIENT_PASS_METHOD",f"{loc}: PASS requires runtime_observation, automated_check, or user_confirmed")
        for field in ("product_version","rule_entry","observed_at","observer"):
            if not isinstance(item.get(field),str) or not item[field].strip(): _add(fs,"WARNING","FIELD_RECOMMENDED_MISSING",f"{loc}.{field} should be recorded")
        artifact=item.get("artifact_path")
        if artifact:
            candidate=(root/artifact).resolve()
            try: candidate.relative_to(root)
            except ValueError: _add(fs,"ERROR","PATH_ESCAPE",f"{loc}.artifact_path escapes project root")
            else:
                if not candidate.is_file(): _add(fs,"ERROR","ARTIFACT_NOT_FOUND",f"{loc} artifact not found: {artifact}")
                elif item.get("sha256"):
                    digest=hashlib.sha256(candidate.read_bytes()).hexdigest()
                    if digest.lower()!=str(item["sha256"]).lower(): _add(fs,"ERROR","HASH_MISMATCH",f"{loc} artifact SHA-256 does not match")
        elif item.get("verification")=="PASS" and not (isinstance(item.get("evidence_note"),str) and item["evidence_note"].strip()):
            _add(fs,"WARNING","PASS_WITHOUT_ARTIFACT","PASS check should include an artifact_path or an explicit evidence_note")
        if item.get("verification")=="PASS" and not (isinstance(item.get("evidence_note"),str) and item["evidence_note"].strip()) and not artifact:
            _add(fs,"ERROR","PASS_WITHOUT_EVIDENCE","PASS requires artifact_path or evidence_note")
    return _report("adapter-evidence",path,fs,checked_checks=checked,check_ids=sorted(seen))

def adapter_report(path: Path, root: Path | None = None) -> dict:
    validation=validate_adapter_evidence(path,root); data=_load(path)
    summary={key:{"checks":0,"pass":0,"fail":0,"blocked":0,"not_run":0,"unknown":0} for key in ADAPTERS}
    for item in data.get("checks",[]) if isinstance(data,dict) and isinstance(data.get("checks"),list) else []:
        if not isinstance(item,dict) or item.get("tool") not in summary: continue
        bucket=summary[item["tool"]]; bucket["checks"]+=1
        status=item.get("verification","UNKNOWN")
        key={"PASS":"pass","FAIL":"fail","BLOCKED":"blocked","NOT_RUN":"not_run","UNKNOWN":"unknown"}.get(status,"unknown")
        bucket[key]+=1
    return {"ok":validation["ok"],"validation":validation,"tools":summary,"interpretation":"PASS 仅表示记录的验证已通过结构校验；是否真实加载仍取决于所记录的运行证据。未记录不等于失败，也不等于通过。"}

def validate_context_pack(path: Path, root: Path | None = None, handoff: Path | None = None) -> dict:
    fs=[]; root=(root or path.parent).resolve()
    try:
        data=json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError,json.JSONDecodeError) as exc:
        _add(fs,"ERROR","PACK_UNREADABLE",f"Cannot read context pack: {exc}")
        return _report("context-pack",path,fs,checked_files=0)
    if not isinstance(data,dict) or data.get("pack_type")!="AIMES_CONTEXT_PACK":
        _add(fs,"ERROR","PACK_TYPE","Expected pack_type AIMES_CONTEXT_PACK")
        return _report("context-pack",path,fs,checked_files=0)
    files=data.get("context_files",[])
    if not isinstance(files,list):
        _add(fs,"ERROR","CONTEXT_FILES_TYPE","context_files must be a list"); files=[]
    checked=0
    for i,item in enumerate(files):
        if not isinstance(item,dict) or not isinstance(item.get("path"),str):
            _add(fs,"ERROR","CONTEXT_ENTRY_TYPE",f"context_files[{i}] must contain a path"); continue
        checked+=1; p=(root/item["path"]).resolve()
        try: p.relative_to(root)
        except ValueError: _add(fs,"ERROR","PATH_ESCAPE",f"Context path escapes project root: {item['path']}"); continue
        if not p.is_file(): _add(fs,"ERROR","CONTEXT_FILE_MISSING",f"Context file missing: {item['path']}"); continue
        digest=hashlib.sha256(p.read_bytes()).hexdigest()
        if digest != item.get("sha256"):
            _add(fs,"ERROR","CONTEXT_HASH_CHANGED",f"Context file changed since pack creation: {item['path']}")
    if handoff:
        hp=handoff if handoff.is_absolute() else root/handoff
        if not hp.is_file(): _add(fs,"ERROR","HANDOFF_MISSING",f"HANDOFF file not found: {hp}")
        else:
            try: content=hp.read_text(encoding="utf-8")
            except OSError as exc: _add(fs,"ERROR","HANDOFF_UNREADABLE",str(exc))
            else:
                if "# AIMES HANDOFF" not in content: _add(fs,"WARNING","HANDOFF_MARKER_MISSING","Handoff file does not contain the expected AIMES heading")
    return _report("context-pack",path,fs,checked_files=checked,project=data.get("project"),task=data.get("task"),handoff_checked=handoff is not None)
