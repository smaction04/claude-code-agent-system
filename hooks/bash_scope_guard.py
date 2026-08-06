"""PreToolUse Hook (전역, matcher=Bash) — 과도하게 넓은 find 검색 사전 확인.

배경: 사용자 홈 디렉토리 전체를 -maxdepth 없이 find로 훑으려다
지연·불필요한 대기를 유발한 사고 재발 방지.
파일 검색은 원래 Glob 도구를 우선해야 하는데 건너뛴 게 근본 원인.

동작: command에 find가 있고, 대상 경로가 사용자 홈 루트/윈도우 드라이브 루트이며
-maxdepth 지정이 없으면 permissionDecision="ask"로 확인을 거치게 함(차단은 아님).

Fail-safe: 예외 → 통과(exit 0, 세션 차단 금지).
"""
import sys, json, os, re, io

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

def _wide_roots():
    """홈 디렉토리와 드라이브 루트를 런타임에 계산 (환경 무관)."""
    roots = {"c:/", "/c/", "c:\\", "/", "~"}
    home = os.path.expanduser("~").rstrip("/\\")
    if home and home != "~":
        h = home.lower()
        roots.add(h.replace("\\", "/"))
        roots.add(h.replace("/", "\\"))
        # Git Bash 스타일 (C:/Users/x -> /c/Users/x)
        m = re.match(r"^([a-z]):[/\\](.*)$", h)
        if m:
            roots.add(f"/{m.group(1)}/" + m.group(2).replace("\\", "/"))
    return roots


WIDE_ROOTS = _wide_roots()


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def main():
    try:
        raw = sys.stdin.read()
        raw = raw.lstrip("\ufeff").strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        emit({})
        return

    tool_input = data.get("tool_input", {}) or {}
    command = tool_input.get("command", "") or ""

    if "find " not in command:
        emit({})
        return

    if "-maxdepth" in command:
        emit({})
        return

    m = re.search(r'find\s+(["\']?)([^\s"\']+)\1', command)
    if not m:
        emit({})
        return

    path = m.group(2).rstrip("/\\").lower()
    if path not in WIDE_ROOTS:
        emit({})
        return

    reason = (
        "find 대상이 사용자 홈/드라이브 루트 전체이고 -maxdepth 제한이 없습니다. "
        "먼저 Glob 도구(파일 패턴 검색 전용, 더 빠름)를 쓰거나, "
        "정말 find가 필요하면 -maxdepth로 범위를 좁히세요. "
        "그래도 전체 검색이 필요하면 승인하세요."
    )
    emit({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "ask",
            "permissionDecisionReason": reason,
        }
    })


if __name__ == "__main__":
    try:
        main()
    except Exception:
        emit({})
