# -*- coding: utf-8 -*-
"""
verify.py — clone 직후 "정말 작동하나?"를 한 번에 확인하는 스모크 테스트.

외부 의존성 0(파이썬 표준 라이브러리만). 네트워크도 쓰지 않습니다.
각 도구를 안전한 dry-run/읽기전용 모드로만 호출하고, 결과를 PASS/FAIL로 보고합니다.

사용법:
    python verify.py

종료코드: 0=전부 PASS, 1=하나라도 FAIL
"""
import sys, subprocess, tempfile, os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY = sys.executable


def run(label, args, env=None, expect_code=None, expect_in=None):
    """도구를 서브프로세스로 실행하고 PASS/FAIL 판정."""
    try:
        p = subprocess.run([PY, *args], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=60)
    except Exception as e:
        print(f"  [FAIL] {label}: 실행 예외 {e}")
        return False
    out = (p.stdout or "") + (p.stderr or "")
    ok = True
    if expect_code is not None and p.returncode != expect_code:
        ok = False
    if expect_in is not None and expect_in not in out:
        ok = False
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"        (code={p.returncode}, 기대코드={expect_code}, 기대문구={expect_in!r})")
        print("        " + out.strip().replace("\n", "\n        ")[:400])
    return ok


def run_hook(label, script, payload, expect_ask):
    """훅을 stdin JSON으로 호출하고 ask 여부를 판정."""
    import json
    try:
        p = subprocess.run([PY, script], cwd=ROOT, input=json.dumps(payload),
                           capture_output=True, text=True, timeout=30)
    except Exception as e:
        print(f"  [FAIL] {label}: 실행 예외 {e}")
        return False
    out = (p.stdout or "").strip()
    asked = '"ask"' in out
    ok = (asked == expect_ask)
    print(f"  [{'PASS' if ok else 'FAIL'}] {label}")
    if not ok:
        print(f"        (기대 ask={expect_ask}, 실제 출력={out[:200]!r})")
    return ok


def main():
    print("claude-code-agent-system — 스모크 테스트")
    print(f"파이썬: {sys.version.split()[0]}  (3.8+ 권장)\n")
    results = []

    # 1) fix_nfc: 인자 없이 호출 → 사용법 출력(읽기전용)
    results.append(run("tools/fix_nfc.py (사용법)",
                       ["tools/fix_nfc.py"], expect_in="resolve"))

    # 2) resume_slim: 임시 _RESUME.md로 무동작(정상) 확인 — 파일 미접촉
    with tempfile.TemporaryDirectory() as td:
        Path(td, "_RESUME.md").write_text(
            "# RESUME\n**최종 갱신**: 짧은 내용\n\n## 활성\n", encoding="utf-8")
        env = dict(os.environ, RESUME_PROJECT_ROOT=td)
        results.append(run("pipelines/resume_slim.py (dry-run)",
                           ["pipelines/resume_slim.py"], env=env, expect_code=0))

    # 3) news_brief: 토큰 미설정 → dry-run 미리보기(전송 안 함).
    #    네트워크가 없거나 RSS가 막혀도 스크립트 자체는 죽지 않아야 정상.
    env = dict(os.environ)
    env.pop("TELEGRAM_TOKEN", None)
    env.pop("CHAT_ID", None)
    results.append(run("pipelines/news_brief.py (dry-run)",
                       ["pipelines/news_brief.py"], env=env, expect_in="dry-run"))

    # 4) bash_scope_guard: 홈 루트 find → ask / 좁은 경로 → 통과
    home = os.path.expanduser("~")
    results.append(run_hook("hooks/bash_scope_guard.py (홈 전체 find → 확인 요청)",
                            "hooks/bash_scope_guard.py",
                            {"tool_input": {"command": f'find {home} -name "*.md"'}}, True))
    results.append(run_hook("hooks/bash_scope_guard.py (좁은 경로 → 통과)",
                            "hooks/bash_scope_guard.py",
                            {"tool_input": {"command": 'find ./src -name "*.py"'}}, False))

    # 5) large_file_guard: 큰 파일 → ask / 작은 파일 → 통과
    with tempfile.TemporaryDirectory() as td:
        big = Path(td, "big.txt")
        big.write_bytes(b"x" * (600 * 1024))
        results.append(run_hook("hooks/large_file_guard.py (600KB → 확인 요청)",
                                "hooks/large_file_guard.py",
                                {"tool_input": {"file_path": str(big)}}, True))
    results.append(run_hook("hooks/large_file_guard.py (작은 파일 → 통과)",
                            "hooks/large_file_guard.py",
                            {"tool_input": {"file_path": str(ROOT / "verify.py")}}, False))

    ok = all(results)
    print(f"\n결과: {sum(results)}/{len(results)} PASS — "
          + ("전부 정상 ✅" if ok else "실패 항목 확인 필요 ❌"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
