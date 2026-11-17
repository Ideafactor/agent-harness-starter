# agent-harness-starter

Claude Code 에이전트 작업을 계획·구현·검증·완료 판정으로 나누는 시작 템플릿이다.

> **아직 실제 Claude Code에서 돌려 보지 않은 초안이다.** 설치 스크립트와 완료 훅은 가짜 입력으로만 시험했다. 먼저 작은 저장소에서 시험해 보고 쓴다.

## 설치

```bash
bash install.sh <대상 프로젝트 폴더>
```

```bash
bash install.sh <대상 프로젝트 폴더> --hook
```

- 이미 있는 파일은 덮어쓰지 않는다.
- 완료 훅은 꺼진 채로 설치된다. 바로 켜려면 `--hook`을 붙인다.
- `.claude/settings.json`이 이미 있으면 `--hook`은 그 파일을 건드리지 않는다. `settings.stop-hook.example.json`을 직접 병합한다.
- 대상 폴더의 `.gitignore`에 훅 상태 파일(`.claude/hooks/.jev_done_state.json`)을 더한다.
- 묶음 안의 `template/dot-claude/`는 설치할 때 대상 프로젝트의 `.claude/`가 된다.

## 들어 있는 것

| 설치 위치 | 하는 일 |
|---|---|
| `.claude/CLAUDE.md` | 역할 나누기, advisor를 부르는 때, 기록 규칙 |
| `.claude/agents/builder.md` | 지시서 하나를 구현하고 receipt를 남긴다 |
| `.claude/agents/verifier.md` | 구현과 다른 맥락에서 조각 하나를 다시 검증한다 |
| `.claude/agents/scout.md` | 찾고 요약한다. 파일을 고치지 않는다 |
| `.claude/agents/advisor.md` | 실행 전에 계획의 약점을 짚는다. 파일을 고치지 않는다 |
| `.claude/hooks/jev_done.py` | Stop 훅. `GOAL.md`의 완료 조건이 안 맞으면 종료를 막는다 |
| `GOAL.md`, `STATE.md`, `receipts/` | 목표와 완료 조건, 진행 상황, 조각별 증빙 |
| `prompts/01`~`05` | 막혔을 때, 작업 나누기, 스킬 만들기, 규칙 더하기, 설정 점검 |

## 설치 뒤에 할 일

1. `GOAL.md`에 목표를 한 문장으로 적는다.
2. `GOAL.md`에 완료 조건을 `` - [ ] `명령` exits 0 `` 형태로 적는다.
3. 작은 작업 하나를 구현 담당(`builder`)과 검증 담당(`verifier`)으로 끝까지 돌린다.
4. 완료 훅을 켠다.
5. 테스트를 일부러 깨뜨리고 훅이 종료를 막는지 확인한다.

## 보안과 한계

| 항목 | 내용 |
|---|---|
| 명령 실행 | `jev_done.py`는 `GOAL.md`에 적힌 명령을 셸로 그대로 실행한다. 믿을 수 있는 저장소에서만 쓴다. |
| 금지 명령 목록 | `rm`, `git push` 같은 명령을 정규식으로 걸러 실행하지 않는다. **보안 장치가 아니다.** 쉽게 우회된다. |
| 외부 전송 | `TYPESAFE_API_KEY`를 설정하면 `STATE.md` 일부, `receipts/` 파일 이름, 명령 출력을 Jev API로 보낸다. 키가 없으면 아무것도 보내지 않고 종료 코드만으로 판정한다. |
| Jev API | 주소, 요청 형식, 응답 형식을 확인하지 않았다. 호출이 실패하면 해당 항목을 "판정 못 함"으로 기록하고 막지 않는다. |
| 사람 승인 | 삭제, 푸시, 배포, 과금은 에이전트가 하지 않고 사람이 직접 승인한다. |

## 출처

에이전트 역할 분리, advisor를 부르는 조건, 완료 훅으로 종료를 막는 구조는 Annatar.md의 X 아티클에서 아이디어를 얻었다. 이 저장소의 파일은 모두 새로 쓴 것이며 원문을 옮겨 싣지 않았다. 원문의 `jev_route.py`에 해당하는 기능은 넣지 않았다.

## 라이선스

[MIT](LICENSE)
