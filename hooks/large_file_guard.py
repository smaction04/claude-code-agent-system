"""PreToolUse Hook (전역, matcher=Read) — 큰 파일 통째 Read 사전 차단.

배경: base64/바이너리 인코딩 등 크기 불명 파일을 통째로 Read해서
컨텍스트 토큰을 대량 낭비한 사고(2026-08-03) 재발 방지.
Claude Code 자체엔 이 안전장치가 없음(anthropics/claude-code#22699, not planned)
→ 로컬 훅으로 자체 보완.

동작: file_path 크기가 임계값(THRESHOLD_BYTES) 초과 + offset/limit 미지정이면
permissionDecision="ask"로 사용자 확인을 거치게 함(차단이 아니라 확인 — 정말 필요하면 진행 가능).
offset/limit이 이미 지정돼 있으면(의도적 부분 읽기) 그대로 통과.

Fail-safe: 예외/파일없음 → 통과(exit 0, 세션 차단 금지).
"""
import sys, json, os, io

try:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True)
except Exception:
    pass

THRESHOLD_BYTES = 500 * 1024  # 500KB


def emit(obj):
    sys.stdout.write(json.dumps(obj, ensure_ascii=False))
    sys.stdout.flush()


def main():
    try:
        raw = sys.stdin.read()
        raw = raw.lstrip("﻿").strip()
        data = json.loads(raw) if raw else {}
    except Exception:
        emit({})
        return

    tool_input = data.get("tool_input", {}) or {}
    file_path = tool_input.get("file_path")
    if not file_path:
        emit({})
        return

    # 의도적 부분 읽기(offset/limit 지정)는 이미 스스로 크기를 의식한 것 → 통과
    if tool_input.get("offset") or tool_input.get("limit"):
        emit({})
        return

    try:
        size = os.path.getsize(file_path)
    except Exception:
        emit({})
        return

    if size <= THRESHOLD_BYTES:
        emit({})
        return

    mb = size / (1024 * 1024)
    reason = (
        f"파일이 {mb:.1f}MB로 큽니다({os.path.basename(file_path)}). "
        f"통째로 읽으면 컨텍스트 토큰을 크게 소모합니다. "
        f"offset/limit으로 일부만 읽거나, Grep으로 필요한 부분만 찾거나, "
        f"셸에서 파일↔파일로 처리하는 걸 고려하세요. 그래도 전체를 읽어야 하면 승인하세요."
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
