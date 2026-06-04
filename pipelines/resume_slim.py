# -*- coding: utf-8 -*-
"""
resume_slim.py — RESUME '최종 갱신' 헤더 줄 자동 슬림(무손실·무사고)

목적: _RESUME.md의 "최종 갱신" 한 줄에 직전 세션 기록이 누적되어
      Edit 시 거대 diff(토큰 낭비)를 유발하는 문제를 자동 정리.

안전 원칙(문제 0 보장):
  1. '최종 갱신' 줄만 대상. 활성/보류 ## 섹션은 절대 미접촉.
  2. 자를 부분에 보존마커(🔴 🟡 보류 검증대기 [활성)가 있으면
     → 자르지 않고 즉시 중단 + 알림(미해결 보류 유실 방지).
  3. 이관은 삭제가 아니라 archive append(손실 0).
  4. 백업(.bak) 먼저 + 이관 전후 글자수 일치 검증, 불일치 시 롤백.
  5. 기본 dry-run. 실제 변경은 --apply 명시할 때만.

종료코드: 0=무동작(정상/임계미달)  10=슬림수행/예정  2=보류감지중단  3=오류
"""
import os, sys, re, io, argparse, shutil
from datetime import datetime
from pathlib import Path

# 프로젝트 루트: RESUME_PROJECT_ROOT 환경변수 우선, 없으면 현재 작업 디렉터리
_ROOT = Path(os.environ.get("RESUME_PROJECT_ROOT") or Path.cwd())
RESUME = _ROOT / "_RESUME.md"
ARCHIVE = _ROOT / "_RESUME_archive.md"
THRESHOLD = 2000            # '최종 갱신' 줄이 이 글자수 초과 시 슬림 후보
SPLIT_RE = re.compile(r"⬇️\s*직전")          # 최신 세션과 직전 누적의 경계
PRESERVE = ["🔴", "🟡", "보류", "검증대기", "[활성"]   # 잘리면 안 되는 항목

def log(m): sys.stderr.write(m + "\n")

def find_header_line(lines):
    for i, ln in enumerate(lines):
        if ln.startswith("**최종 갱신**"):
            return i
    return -1

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true", help="실제 적용(미지정=dry-run)")
    ap.add_argument("--force", action="store_true",
                    help="보류마커 무시 강제(직전블록 보류를 활성섹션에 이미 보존한 경우 운영자 수동 시에만)")
    ap.add_argument("--threshold", type=int, default=THRESHOLD)
    args = ap.parse_args()

    if not RESUME.exists():
        log("[resume_slim] RESUME 없음"); return 3
    text = RESUME.read_text(encoding="utf-8")
    lines = text.split("\n")
    hi = find_header_line(lines)
    if hi < 0:
        log("[resume_slim] '최종 갱신' 줄 없음 — 무동작"); return 0

    header = lines[hi]
    if len(header) <= args.threshold:
        log(f"[resume_slim] 정상 ({len(header)}자 ≤ {args.threshold}) — 무동작"); return 0

    m = SPLIT_RE.search(header)
    if not m:
        log(f"[resume_slim] {len(header)}자지만 '⬇️직전' 경계 없음 — 수동확인 필요"); return 2

    keep = header[:m.start()].rstrip()        # 최신 세션(유지)
    move = header[m.start():].strip()          # 직전 누적(이관 후보)

    # 보존마커 검사 — 미해결 보류가 섞였으면 자동 슬림 금지
    hit = [k for k in PRESERVE if k in move]
    if hit and not args.force:
        log("[resume_slim] ⛔ 보류/미검증 항목이 직전 블록에 섞여 있어 자동 슬림 중단.")
        log(f"             감지 마커: {hit}")
        log("             → 해당 보류를 '## 활성/보류' 섹션으로 먼저 옮긴 뒤 재시도.")
        return 2
    if hit and args.force:
        # --force 안전 보강: 보류마커가 활성섹션(## 이후 본문)에도 보존됐는지 cross-check
        active = "\n".join(lines[hi+1:])
        unsaved = [k for k in hit if k not in ("보류", "[활성") and k not in active]
        if unsaved:
            log(f"[resume_slim] ⛔ --force여도 중단: 보류마커 {unsaved}가 활성섹션에 없음(유실 위험).")
            log("             → 활성섹션에 먼저 보존 후 재시도.")
            return 2
        log(f"[resume_slim] ⚠️ --force: 보류마커 {hit} 무시(활성섹션 보존 확인됨). 이관 강행.")

    # 여기부터 안전 — 이관 실행 가능
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    block = f"\n\n## [{stamp} 자동 이관] 직전 세션 누적\n{move}\n"

    if not args.apply:
        log(f"[resume_slim:dry-run] 슬림 예정: 헤더 {len(header)}→{len(keep)}자, "
            f"{len(move)}자 archive 이관 (보류마커 없음·안전)")
        return 10

    # --- 실제 적용 ---
    bak = RESUME.parent / f"_RESUME.{datetime.now().strftime('%Y%m%d-%H%M')}.md.bak"
    shutil.copy2(RESUME, bak)
    arch_before = ARCHIVE.read_text(encoding="utf-8") if ARCHIVE.exists() else ""
    try:
        lines[hi] = keep
        new_resume = "\n".join(lines)
        with io.open(ARCHIVE, "a", encoding="utf-8") as f:
            f.write(block)
        RESUME.write_text(new_resume, encoding="utf-8")

        # 손실 0 검증: archive 증가분이 이관 텍스트를 포함하는가
        arch_after = ARCHIVE.read_text(encoding="utf-8")
        if move not in arch_after or (len(arch_after) - len(arch_before)) < len(move):
            raise RuntimeError("손실 검증 실패 — archive 이관 불완전")
        log(f"[resume_slim] ✅ 슬림 완료: 헤더 {len(header)}→{len(keep)}자, "
            f"{len(move)}자 이관·검증통과. 백업={bak.name}")
        return 10
    except Exception as e:
        shutil.copy2(bak, RESUME)
        if ARCHIVE.exists():
            ARCHIVE.write_text(arch_before, encoding="utf-8")
        log(f"[resume_slim] ❌ 오류로 롤백: {e}"); return 3

if __name__ == "__main__":
    sys.exit(main())
