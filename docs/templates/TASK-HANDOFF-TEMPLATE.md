# Task Handoff: TASK-ID — Short title

- **Task ID:** TASK-ID
- **Handoff date/time:** YYYY-MM-DDThh:mm:ss±hh:mm
- **Outgoing tool/version:** tool-id / version
- **Incoming tool (if known):** tool-id / version
- **Branch:** task/TASK-ID-tool-id
- **Baseline commit:** `<full commit SHA>`
- **Handoff commit:** `<full commit SHA or NOT_COMMITTED with reason>`
- **Task status:** IN_PROGRESS / IMPLEMENTED_UNVERIFIED / VERIFIED / BLOCKED
- **Writer declaration:** `.aimes/project-control/active-writer.yaml`
- **Evidence status:** PASS / PARTIAL / NOT_RUN

## 1. Goal and acceptance criteria

- Goal:
- Acceptance criteria:
- Explicitly out of scope:

## 2. Repository state at handoff

- `git status --short`:
- Existing user changes preserved:
- Current branch and HEAD:
- Changed files:
- Untracked files:
- Known conflicts:

## 3. Changes made

| Path | Change | Reason | Evidence |
|---|---|---|---|
| `path/to/file` | summary | requirement/task ID | test/log/commit |

## 4. Verification evidence

| Command/check | Actual result | Exit code | Evidence path |
|---|---|---:|---|
| `exact command` | PASS / FAIL / NOT_RUN | 0 / n/a | `path/to/log` |

Do not mark `VERIFIED` based on intended commands or another tool's summary. Record only checks that actually ran.

## 5. Open issues, risks and decisions

- Open issues:
- Risks and limitations:
- Decisions requiring owner approval:
- Related Issue/ADR:

## 6. Next steps

1. 
2. 

## 7. Incoming tool checklist

- [ ] Read this handoff and the authoritative governance core.
- [ ] Re-run `git status --short` and verify the branch/HEAD.
- [ ] Confirm the baseline and changed-file list.
- [ ] Verify listed evidence files and commands before relying on results.
- [ ] Confirm writer ownership before editing; do not assume this document grants an atomic lock.
