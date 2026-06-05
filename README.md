# claude-code-agent-system

Claude Code로 AI 에이전트를 운영하면서 만든 **재사용 가능한 도구·스킬 모음**입니다.
사업·개인 내용은 모두 제외하고, 어디서나 쓸 수 있는 범용 조각만 추렸습니다.

> 🇰🇷 한국어 환경(Windows + 한글 경로)에서 만들었지만, 대부분 OS·언어 무관하게 동작합니다.

**요구사항**: Python 3.8+ (표준 라이브러리만 사용 — 별도 설치(`pip install`) 없음).
clone 직후 바로 확인하려면:

```bash
python verify.py   # 3개 도구를 안전한 dry-run으로 실행 → 전부 PASS면 작동 보장
```

## 무엇이 들어있나

| 항목 | 위치 | 용도 |
|------|------|------|
| **한글 경로 NFC/NFD 가드** | `tools/fix_nfc.py` | 맥/윈도우/클라우드를 오가며 한글 파일명이 깨져 "파일 없음(Exit 1)"이 날 때, 진짜 경로를 찾아주거나 일괄 정규화 |
| **RESUME 자동 슬림** | `pipelines/resume_slim.py` | 작업 재개 메모(`_RESUME.md`)의 헤더 한 줄이 비대해지면 안전하게 아카이브로 이관(무손실·보류 항목 보호) |
| **아침 뉴스 브리핑 봇** | `pipelines/news_brief.py` | 경제/부동산/AI 뉴스(RSS)를 모아 텔레그램으로 무인 전송. 외부 의존성 0(파이썬 표준 라이브러리만) |
| **기업정보 조회 스킬** | `skills/company-info/` | 한국·미국 회사 기업정보를 무료로 끝까지 조회(결제 전 데이터 존재여부 확인) |
| **디스크 정리 스킬** | `skills/disk-cleanup/` | PC 용량을 실측·등급 분류 후 승인 받아 안전 삭제 |

## 빠른 시작

### 도구 (파이썬)
```bash
# 한글 경로 깨짐 해소
python tools/fix_nfc.py resolve "어떤/한글/경로.md"
python tools/fix_nfc.py sweep "대상폴더" --apply

# 아침 뉴스봇 (토큰 없으면 dry-run 미리보기)
python pipelines/news_brief.py

# RESUME 메모 자동 슬림 (기본 dry-run, --apply 시에만 실제 변경)
#   _RESUME.md가 있는 폴더에서 실행하거나 RESUME_PROJECT_ROOT로 지정
RESUME_PROJECT_ROOT=/path/to/project python pipelines/resume_slim.py
```

뉴스봇을 실제 전송하려면 텔레그램 봇 토큰·chat_id가 필요합니다.
환경변수(`TELEGRAM_TOKEN`, `CHAT_ID`) 또는 `pipelines/news_brief_config.json`으로 설정합니다.
예시는 `pipelines/news_brief_config.example.json` 참고.

### 스킬 (Claude Code)
`skills/` 아래 폴더를 Claude Code의 스킬 디렉터리(`.claude/skills/`)로 복사하면
해당 작업을 요청할 때 자동으로 인식됩니다.

## 내 프로젝트에 맞게 고쳐 쓰기 (fork & adapt)

각 조각은 독립적이라 필요한 것만 골라 쓰면 됩니다.
- **뉴스봇 출처 변경**: `news_brief.py` 상단의 RSS 소스 목록(카테고리·URL·키워드 필터)을 본인 관심사로 교체.
- **경로 설정**: 개인 경로를 코드에 박지 않았습니다. `resume_slim.py`는 `RESUME_PROJECT_ROOT` 환경변수(없으면 현재 폴더)를 씁니다.
- **스킬 추가**: `skills/<이름>/SKILL.md` 형식을 그대로 따라 새 스킬을 만들 수 있습니다.

고친 뒤 `python verify.py`로 회귀 확인하세요.

## 설계 원칙

이 도구들이 공유하는 공통 철학:
- **수치를 지어내지 않는다** — 못 얻은 건 "못 얻음"이라고 명시.
- **파괴적 작업은 승인 후에만** — 삭제·이관은 dry-run이 기본, 실제 적용은 명시할 때만.
- **무손실** — 백업 먼저, 변경 전후 검증, 실패 시 자동 롤백.

## 라이선스

MIT — `LICENSE` 참고.
