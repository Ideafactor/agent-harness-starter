#!/usr/bin/env python3
"""jev_done.py - Stop 훅. GOAL.md의 완료 조건을 검사하고, 덜 끝났으면 종료를 막는다.

원문 저자의 구현이 아니다. 원문이 설명한 동작을 바탕으로 새로 작성했다.

동작 순서
  1. GOAL.md의 "## Done means" 구역에서 체크 항목을 읽는다.
  2. 백틱 명령으로 시작하는 항목은 그 명령을 직접 실행한다.
  3. 종료 코드가 0이 아니면 코드가 바로 실패로 판정한다.
  4. 출력의 뜻을 읽어야 하는 항목만 Jev에 묻는다(확률 0.9 이상이면 통과).
  5. 실패가 있으면 {"decision": "block"}을 출력해 작업을 계속시킨다.
  6. 같은 항목이 5번 실패하면 더 막지 않고 멈추게 둔다.

환경 변수
  TYPESAFE_API_KEY   Jev API 키. 없으면 Jev 단계를 건너뛴다. (변수 이름은 이 스크립트가 정했다)
  JEV_MODEL          기본값 jev-latest
  JEV_URL            기본값 https://api.typesafe.ai/v1/systemone
  JEV_DONE_STRICT    1이면 "판정 못 한 항목"도 실패로 본다. 기본값은 기록만 한다.
  JEV_DONE_MAX_FAILS 기본값 5
  JEV_DONE_CMD_TIMEOUT 명령 하나의 제한 시간(초). 기본값 300
"""
import json
import os
import re
import subprocess
import sys
import urllib.request
from pathlib import Path

THRESHOLD = 0.9
MAX_FAILS = int(os.environ.get("JEV_DONE_MAX_FAILS", "5"))
CMD_TIMEOUT = int(os.environ.get("JEV_DONE_CMD_TIMEOUT", "300"))
STRICT = os.environ.get("JEV_DONE_STRICT") == "1"
OUTPUT_TAIL = 4000

# 정확히 판정할 수 있는 금지 규칙은 모델이 아니라 코드가 맡는다.
FORBIDDEN = re.compile(
    r"(\brm\b|\brmdir\b|\bsudo\b|\bgit\s+(push|reset|clean)\b|\bdeploy\b|\bpublish\b"
    r"|\bdrop\s+(table|database)\b|\bterraform\s+(apply|destroy)\b|\bkubectl\s+(apply|delete)\b"
    r"|\bcurl\b|\bwget\b|\bmkfs\b|\bdd\b)",
    re.I,
)
EXIT_ONLY = re.compile(r"^(exits?|returns?)\s+(with\s+)?(code\s+)?0\.?$|^종료 코드\s*0", re.I)


def parse_goal(text):
    """'## Done means' 구역의 체크 항목을 [(조건문, 명령 또는 None)]으로 돌려준다."""
    items, inside = [], False
    for line in text.splitlines():
        if line.startswith("## "):
            inside = line.lower().startswith("## done means")
            continue
        m = re.match(r"\s*-\s*\[[ xX]\]\s*(.+)", line) if inside else None
        if not m:
            continue
        cond = m.group(1).strip()
        cmd = re.match(r"`([^`]+)`\s*(.*)", cond)
        # 백틱으로 "시작"하는 항목만 명령으로 본다. 문장 중간의 `--help` 등은 실행하지 않는다.
        items.append((cond, cmd.group(1) if cmd else None, cmd.group(2).strip() if cmd else ""))
    return items


def run(cmd, cwd):
    try:
        p = subprocess.run(cmd, shell=True, cwd=cwd, capture_output=True, text=True, timeout=CMD_TIMEOUT)
        return p.returncode, (p.stdout + p.stderr)[-OUTPUT_TAIL:]
    except subprocess.TimeoutExpired:
        return 124, f"제한 시간 {CMD_TIMEOUT}초를 넘겼다."


def ask_jev(questions_state):
    """{이름: 확률} 을 돌려준다. 호출이 실패하면 None."""
    key = os.environ.get("TYPESAFE_API_KEY")
    if not key or not questions_state:
        return None
    body = {
        "model": os.environ.get("JEV_MODEL", "jev-latest"),
        "state": questions_state,
        "questions": {
            name: {
                "type": "noul",
                "instructions": f"Look at `{name}` in the state. Does the evidence there prove "
                                "that its `condition` is fully met? Missing evidence means no.",
            }
            for name in questions_state
        },
    }
    req = urllib.request.Request(
        os.environ.get("JEV_URL", "https://api.typesafe.ai/v1/systemone"),
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            answers = json.load(r)["answers"]
        return {n: float(a["noul"]) for n, a in answers.items()}
    except Exception as e:  # 네트워크·인증·형식 오류는 "판정 못 함"으로 처리한다.
        print(f"jev_done: Jev 호출 실패 ({e})", file=sys.stderr)
        return None


def main():
    try:
        event = json.load(sys.stdin)
    except Exception:
        event = {}
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
    goal = root / "GOAL.md"
    if not goal.exists():
        return  # 목표가 없으면 관여하지 않는다.

    session = str(event.get("session_id", "default"))
    store = root / ".claude" / "hooks" / ".jev_done_state.json"
    try:
        counts_all = json.loads(store.read_text())
    except Exception:
        counts_all = {}
    counts = counts_all.get(session, {})

    failed, unknown, to_judge = [], [], {}
    for i, (cond, cmd, rest) in enumerate(parse_goal(goal.read_text(encoding="utf-8"))):
        name = f"check_{i}"
        if cmd is None:
            # 명령이 없는 항목은 STATE.md와 receipts/ 목록을 증거로 Jev에 묻는다.
            state_md = root / "STATE.md"
            receipts = root / "receipts"
            to_judge[name] = {
                "condition": cond,
                "state_md": state_md.read_text(encoding="utf-8")[-OUTPUT_TAIL:] if state_md.exists() else "",
                "receipt_files": sorted(p.name for p in receipts.iterdir()) if receipts.is_dir() else [],
            }
            continue
        if FORBIDDEN.search(cmd):
            unknown.append((name, cond, "금지된 명령이라 실행하지 않았다. 사람이 확인해야 한다."))
            continue
        code, out = run(cmd, root)
        if code != 0:
            failed.append((name, cond, f"`{cmd}` 종료 코드 {code}\n{out[-800:]}"))
        elif not EXIT_ONLY.match(rest):
            to_judge[name] = {"condition": cond, "command": cmd, "exit_code": code, "output": out}

    probs = ask_jev(to_judge)
    for name, st in to_judge.items():
        if probs is None or name not in probs:
            unknown.append((name, st["condition"], "Jev 판정 없음. 사람이 확인해야 한다."))
        elif probs[name] < THRESHOLD:
            failed.append((name, st["condition"], f"Jev 확률 {probs[name]:.2f} < {THRESHOLD}. 증거가 부족하다."))

    if STRICT:
        failed, unknown = failed + unknown, []
    for name, cond, why in unknown:
        print(f"jev_done: 판정 못 함 - {cond} ({why})", file=sys.stderr)

    if not failed:
        counts_all.pop(session, None)
        save(store, counts_all)
        return  # 아무것도 출력하지 않으면 정상 종료를 허용한다.

    for name, _, _ in failed:
        counts[name] = counts.get(name, 0) + 1
    counts_all[session] = counts
    save(store, counts_all)

    exhausted = [c for n, c, _ in failed if counts[n] >= MAX_FAILS]
    if exhausted:
        # GOAL.md의 "5번 실패하면 멈춘다" 규칙. 더 막지 않고 사람에게 돌려보낸다.
        print(f"jev_done: {MAX_FAILS}번 실패해 중단을 허용한다 - " + "; ".join(exhausted), file=sys.stderr)
        return

    lines = [f"- {cond} (실패 {counts[name]}/{MAX_FAILS})\n  {why}" for name, cond, why in failed]
    reason = ("GOAL.md의 완료 조건이 아직 충족되지 않았다. 아래 항목을 고친 뒤 다시 멈춰라. "
              "삭제·푸시·배포·과금이 필요하면 진행하지 말고 사용자에게 물어라.\n" + "\n".join(lines))
    print(json.dumps({"decision": "block", "reason": reason}, ensure_ascii=False))


def save(path, data):
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    except Exception as e:
        print(f"jev_done: 상태 저장 실패 ({e})", file=sys.stderr)


if __name__ == "__main__":
    main()
