from __future__ import annotations
import hashlib, json
from pathlib import Path
from typing import Any
import yaml

VALID_ENTITY_TYPES = {"requirement", "knowledge", "reuse_decision", "task", "implementation", "test", "release", "skill"}
VALID_EVIDENCE_KINDS = {"command", "test", "build", "review", "artifact", "manual"}

def _load(path: Path) -> Any:
    if not path.is_file(): raise ValueError(f"Input file does not exist or is not a file: {path}")
    try:
        raw = path.read_text(encoding="utf-8-sig")
        return json.loads(raw) if path.suffix.lower() == ".json" else yaml.safe_load(raw)
    except (OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        raise ValueError(f"Cannot parse {path}: {exc}") from exc

def _report(kind: str, path: Path, findings: list[dict], **extra):
    errors=sum(x["level"]=="ERROR" for x in findings); warnings=sum(x["level"]=="WARNING" for x in findings)
    return {"schema_version":1,"validator":f"aimes-{kind}-validator","source":str(path),"ok":errors==0,"summary":{"errors":errors,"warnings":warnings,"findings":len(findings)},"findings":findings,**extra}

def _add(fs, level, code, message): fs.append({"level":level,"code":code,"message":message})

def validate_evidence(path: Path, root: Path | None = None) -> dict:
    data=_load(path); fs=[]
    if not isinstance(data, dict) or not isinstance(data.get("evidence"), list):
        _add(fs,"ERROR","ROOT_SHAPE","Evidence record must be an object with an evidence list")
        return _report("evidence",path,fs,checked_evidence=0)
    seen=set(); checked=0; root=(root or path.parent).resolve()
    for i,e in enumerate(data["evidence"]):
        loc=f"evidence[{i}]"
        if not isinstance(e,dict): _add(fs,"ERROR","ENTRY_TYPE",f"{loc} must be an object"); continue
        checked+=1; eid=e.get("id")
        if not isinstance(eid,str) or not eid.strip(): _add(fs,"ERROR","ID_REQUIRED",f"{loc}.id is required")
        elif eid in seen: _add(fs,"ERROR","DUPLICATE_ID",f"Duplicate evidence id: {eid}")
        else: seen.add(eid)
        if e.get("kind") not in VALID_EVIDENCE_KINDS: _add(fs,"ERROR","EVIDENCE_KIND",f"{loc}.kind must be one of {sorted(VALID_EVIDENCE_KINDS)}")
        if e.get("result") not in {"PASS","FAIL","INFO","UNKNOWN"}: _add(fs,"ERROR","EVIDENCE_RESULT",f"{loc}.result must be PASS, FAIL, INFO or UNKNOWN")
        if e.get("kind") in {"command","test","build"}:
            if not isinstance(e.get("command"),str) or not e["command"].strip(): _add(fs,"ERROR","COMMAND_REQUIRED",f"{loc} command/test/build evidence requires the exact command")
            if type(e.get("exit_code")) is not int: _add(fs,"ERROR","EXIT_CODE_REQUIRED",f"{loc} command/test/build evidence requires integer exit_code")
            elif e.get("result")=="PASS" and e["exit_code"]!=0: _add(fs,"ERROR","EXIT_CODE_CONTRADICTION",f"{loc} says PASS but exit_code is not 0")
        if not isinstance(e.get("observed_at"),str) or not e["observed_at"].strip(): _add(fs,"WARNING","OBSERVED_AT_MISSING",f"{loc}.observed_at should record when evidence was observed")
        artifact=e.get("artifact_path")
        if artifact:
            candidate=(root/artifact).resolve()
            try: candidate.relative_to(root)
            except ValueError: _add(fs,"ERROR","PATH_ESCAPE",f"{loc}.artifact_path escapes project root")
            else:
                if not candidate.is_file(): _add(fs,"ERROR","ARTIFACT_NOT_FOUND",f"{loc} artifact not found: {artifact}")
                elif e.get("sha256"):
                    digest=hashlib.sha256(candidate.read_bytes()).hexdigest()
                    if digest.lower()!=str(e["sha256"]).lower(): _add(fs,"ERROR","HASH_MISMATCH",f"{loc} artifact SHA-256 does not match")
        if e.get("result")=="PASS" and e.get("kind") in {"command","test","build"} and not artifact:
            _add(fs,"WARNING","ARTIFACT_NOT_RECORDED",f"{loc} passing command evidence should reference a captured artifact/log")
    return _report("evidence",path,fs,checked_evidence=checked,evidence_ids=sorted(seen))

def validate_trace(path: Path, root: Path | None = None) -> dict:
    data=_load(path); fs=[]; root=(root or path.parent).resolve()
    if not isinstance(data,dict) or not isinstance(data.get("entities"),list):
        _add(fs,"ERROR","ROOT_SHAPE","Trace manifest must be an object with an entities list")
        return _report("trace",path,fs,checked_entities=0)
    entities=data["entities"]; ids={}; checked=0
    for i,e in enumerate(entities):
        if not isinstance(e,dict): _add(fs,"ERROR","ENTRY_TYPE",f"entities[{i}] must be an object"); continue
        checked+=1; eid=e.get("id")
        if not isinstance(eid,str) or not eid.strip(): _add(fs,"ERROR","ID_REQUIRED",f"entities[{i}].id is required"); continue
        if eid in ids: _add(fs,"ERROR","DUPLICATE_ID",f"Duplicate entity id: {eid}")
        ids[eid]=e
        if e.get("type") not in VALID_ENTITY_TYPES: _add(fs,"ERROR","ENTITY_TYPE",f"{eid}: unsupported type {e.get('type')!r}")
        if not isinstance(e.get("links",[]),list): _add(fs,"ERROR","LINKS_TYPE",f"{eid}.links must be a list")
        if not isinstance(e.get("status","UNKNOWN"),str): _add(fs,"ERROR","STATUS_TYPE",f"{eid}.status must be a string")
    for e in entities:
        if not isinstance(e,dict) or not isinstance(e.get("id"),str): continue
        eid=e["id"]
        for link in e.get("links",[]) if isinstance(e.get("links",[]),list) else []:
            target=link.get("target") if isinstance(link,dict) else link
            if not isinstance(target,str) or target not in ids: _add(fs,"ERROR","BROKEN_TRACE_LINK",f"{eid} links to missing entity {target!r}")
        if e.get("status")=="VERIFIED":
            refs=e.get("evidence_refs",[])
            if not isinstance(refs,list) or not refs: _add(fs,"ERROR","VERIFIED_WITHOUT_EVIDENCE",f"{eid} is VERIFIED but has no evidence_refs")
            elif not data.get("evidence_file"):
                _add(fs,"ERROR","EVIDENCE_FILE_REQUIRED",f"{eid} is VERIFIED but manifest has no evidence_file")
    evidence_path=None
    if data.get("evidence_file"):
        rel=data["evidence_file"]; evidence_path=(root/rel).resolve()
        try: evidence_path.relative_to(root)
        except ValueError: _add(fs,"ERROR","PATH_ESCAPE","evidence_file escapes project root"); evidence_path=None
        if evidence_path and not evidence_path.is_file(): _add(fs,"ERROR","EVIDENCE_FILE_NOT_FOUND",f"Evidence file not found: {rel}"); evidence_path=None
    evidence_by_id={}
    if evidence_path:
        ev=validate_evidence(evidence_path,root)
        if not ev["ok"]: _add(fs,"ERROR","EVIDENCE_FILE_INVALID","Evidence file has validation errors")
        try:
            ed=_load(evidence_path); evidence_by_id={e.get("id"):e for e in ed.get("evidence",[]) if isinstance(e,dict)}
        except (ValueError,AttributeError): pass
        for e in entities:
            if not isinstance(e,dict) or e.get("status")!="VERIFIED": continue
            refs=e.get("evidence_refs",[])
            for ref in refs if isinstance(refs,list) else []:
                evitem=evidence_by_id.get(ref)
                if not evitem: _add(fs,"ERROR","EVIDENCE_REF_NOT_FOUND",f"{e.get('id')} references missing evidence {ref!r}")
                elif evitem.get("result")!="PASS": _add(fs,"ERROR","VERIFIED_EVIDENCE_NOT_PASS",f"{e.get('id')} references evidence {ref!r} whose result is not PASS")
    for item in data.get("context_files",[]) if isinstance(data.get("context_files",[]),list) else []:
        if not isinstance(item,str): _add(fs,"ERROR","CONTEXT_FILE_TYPE","context_files entries must be path strings"); continue
        p=(root/item).resolve()
        try: p.relative_to(root)
        except ValueError: _add(fs,"ERROR","PATH_ESCAPE",f"context file escapes project root: {item}")
        else:
            if not p.is_file(): _add(fs,"WARNING","CONTEXT_FILE_NOT_FOUND",f"Context file not found: {item}")
    return _report("trace",path,fs,checked_entities=checked,entity_ids=sorted(ids),evidence_count=len(evidence_by_id))

def build_context_pack(manifest_path: Path, output_dir: Path, root: Path | None = None) -> dict:
    data=_load(manifest_path)
    if not isinstance(data,dict): raise ValueError("Trace manifest must be an object")
    root=(root or manifest_path.parent).resolve(); output_dir=output_dir.resolve()
    try: output_dir.relative_to(root)
    except ValueError: raise ValueError("Context pack output directory must be inside project root")
    output_dir.mkdir(parents=True,exist_ok=True)
    included=[]
    for rel in data.get("context_files",[]) if isinstance(data.get("context_files",[]),list) else []:
        if not isinstance(rel,str): continue
        p=(root/rel).resolve()
        try: p.relative_to(root)
        except ValueError: continue
        if p.is_file():
            raw=p.read_bytes(); included.append({"path":rel,"sha256":hashlib.sha256(raw).hexdigest(),"size_bytes":len(raw)})
    pack={"schema_version":1,"pack_type":"AIMES_CONTEXT_PACK","project":data.get("project",{}),"generated_from":str(manifest_path.relative_to(root)) if manifest_path.is_relative_to(root) else manifest_path.name,"generated_note":"此包记录上下文文件清单与摘要，不复制源文件、不执行项目命令。","task":data.get("task",{}),"entities":data.get("entities",[]),"evidence_file":data.get("evidence_file"),"context_files":included,"open_questions":data.get("open_questions",[]),"risks":data.get("risks",[])}
    json_path=output_dir/"context-pack.json"; json_path.write_text(json.dumps(pack,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    task=data.get("task",{}) if isinstance(data.get("task",{}),dict) else {}
    lines=["# AIMES HANDOFF", "", f"- 项目：{(data.get('project') or {}).get('name','未填写') if isinstance(data.get('project'),dict) else '未填写'}",f"- 任务：{task.get('id','未填写')} — {task.get('title','未填写')}",f"- 当前状态：{task.get('status','UNKNOWN')}","", "## 任务目标", str(task.get("goal","未填写")),"", "## 追溯实体"]
    for e in data.get("entities",[]) if isinstance(data.get("entities",[]),list) else []:
        if isinstance(e,dict): lines.append(f"- {e.get('id','?')} [{e.get('type','?')}] {e.get('status','UNKNOWN')}")
    lines += ["", "## 已纳入上下文的文件"]
    lines += [f"- `{x['path']}` (SHA-256: `{x['sha256']}`)" for x in included] or ["- 无；请先在 manifest 的 context_files 中指定文件"]
    lines += ["", "## 未决问题"] + [f"- {x}" for x in data.get("open_questions",[]) if isinstance(x,str)]
    lines += ["", "## 风险与限制"] + [f"- {x}" for x in data.get("risks",[]) if isinstance(x,str)]
    lines += ["", "## 接续约束", "- 先读取本 HANDOFF 和 context-pack.json，再检查列出的源文件是否仍与哈希一致。", "- 不要把 UNKNOWN 或 IMPLEMENTED_UNVERIFIED 自动升级为 VERIFIED。", "- 任何新结论都应补充依据、追溯链接和必要的验证证据。", ""]
    handoff=output_dir/"HANDOFF.md"; handoff.write_text("\n".join(lines),encoding="utf-8")
    return {"schema_version":1,"ok":True,"output_dir":str(output_dir),"files":[str(json_path),str(handoff)],"context_files_included":len(included),"message":"Context Pack 与 HANDOFF 已生成；源文件未复制或修改。"}
