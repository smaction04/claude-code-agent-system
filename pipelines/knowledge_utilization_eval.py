"""
knowledge_utilization_eval.py
Agent memory utilization evaluator — claude CLI + TruLens

Measures whether crawled/synthesized knowledge in agent memory files
is actually showing up in real agent responses.

Usage:
  python knowledge_utilization_eval.py                  # all agents
  python knowledge_utilization_eval.py dev-engineer     # single agent
  python knowledge_utilization_eval.py --dashboard      # TruLens dashboard

Requirements:
  pip install trulens trulens-providers-litellm anthropic

Setup:
  1. Install Claude Code CLI: https://claude.ai/download
  2. Configure your agents in .claude/settings.json
  3. Edit BENCHMARKS below to match your agent names and knowledge
"""

import sys
import json
import shutil
import platform
import subprocess
from pathlib import Path
from datetime import datetime

from trulens.core import TruSession, Metric
from trulens.apps.basic import TruBasicApp

DB_PATH = Path.cwd() / "trulens_eval.db"

# ─────────────────────────────────────────────────────────
# Edit this section to match YOUR agents and their knowledge.
#
# Format per agent:
#   "agent-name": {
#       "questions": [...],   <- test prompts targeting specific knowledge
#       "keywords":  [...],   <- terms that MUST appear if the agent uses the knowledge
#       "source":    "...",   <- label for reporting (e.g. crawl date or topic)
#   }
#
# Tip: pick keywords that are specific to the injected knowledge,
# not generic words the agent would say anyway.
# ─────────────────────────────────────────────────────────
BENCHMARKS = {
    "dev-engineer": {
        "questions": [
            "How do you apply the Search→Ask→Do pipeline in a multi-agent system?",
            "How do you set hybrid search weights like 0.7/0.3?",
        ],
        "keywords": ["Search", "Ask", "Do", "hybrid", "0.7", "0.3", "PRINCE"],
        "source": "crawl-2026-06-18",
    },
    "design-expert": {
        "questions": [
            "How do you improve design output using a Judge-Evaluate-Iterate loop?",
            "How should design evaluation criteria be defined in the AI era?",
        ],
        "keywords": ["Judge", "Evaluate", "Iterate", "criteria", "cognitive"],
        "source": "crawl-2026-06-18",
    },
    "data-analyst": {
        "questions": [
            "How do you optimize a churn threshold using FN/FP cost sweep?",
            "How do you evaluate a churn model from a unit economics perspective?",
        ],
        "keywords": ["FN", "FP", "unit economics", "churn", "threshold", "cost"],
        "source": "crawl-2026-06-18",
    },
    "content-creator": {
        "questions": [
            "How do AEO/GEO strategies increase content citation in AI search?",
            "How do you split content strategy across AI engines per BrightEdge?",
        ],
        "keywords": ["AEO", "GEO", "citation", "agent", "BrightEdge"],
        "source": "crawl-2026-06-12",
    },
}


# ─────────────────────────────────────────────────────────
# Claude CLI auto-detection (Windows PowerShell / Mac / Linux)
# ─────────────────────────────────────────────────────────
def _find_claude_cli() -> str | None:
    direct = shutil.which("claude")
    if direct:
        return direct
    npm_ps1 = Path.home() / "AppData" / "Roaming" / "npm" / "claude.ps1"
    if npm_ps1.exists():
        return str(npm_ps1)
    return None


CLAUDE_CLI = _find_claude_cli()


def call_agent(agent_name: str, question: str) -> str:
    if not CLAUDE_CLI:
        return "[error] claude CLI not found. Install from https://claude.ai/download"

    if platform.system() == "Windows" and CLAUDE_CLI.endswith(".ps1"):
        safe_q = question.replace("'", "''")
        cmd = f"& '{CLAUDE_CLI}' -p --agent {agent_name} --output-format text '{safe_q}'"
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", cmd],
            capture_output=True, text=True, timeout=150,
        )
    else:
        result = subprocess.run(
            [CLAUDE_CLI, "-p", "--agent", agent_name, "--output-format", "text", question],
            capture_output=True, text=True, timeout=150,
        )

    if result.returncode != 0:
        return f"[error] {result.stderr[:300]}"
    return result.stdout.strip()


# ─────────────────────────────────────────────────────────
# Evaluation logic
# ─────────────────────────────────────────────────────────
def keyword_score(text: str, keywords: list) -> float:
    hits = sum(1 for kw in keywords if kw.lower() in text.lower())
    return round(hits / len(keywords), 2)


def eval_agent(agent_name: str, session: TruSession) -> dict | None:
    if agent_name not in BENCHMARKS:
        print(f"  No benchmark defined for: {agent_name}")
        return None

    bm = BENCHMARKS[agent_name]
    keywords = bm["keywords"]

    def keyword_utilization(response: str) -> float:
        return keyword_score(response, keywords)

    metric = Metric(keyword_utilization, name="keyword_utilization").on_output()

    def agent_fn(question: str) -> str:
        return call_agent(agent_name, question)

    tru_app = TruBasicApp(
        agent_fn,
        app_name=agent_name,
        app_version="eval_" + datetime.now().strftime("%Y%m%d"),
        feedbacks=[metric],
    )

    print(f"\n{'─'*58}")
    print(f"  Agent: {agent_name}  |  Source: {bm['source']}")
    print(f"  Keywords: {keywords}")
    print(f"{'─'*58}")

    scores = []
    for q in bm["questions"]:
        print(f"\n  Q: {q}")
        with tru_app:
            response = agent_fn(q)
        score = keyword_score(response, keywords)
        hit_words = [kw for kw in keywords if kw.lower() in response.lower()]
        scores.append(score)
        preview = response[:200].replace("\n", " ")
        print(f"  A: {preview}...")
        print(f"  ▶ utilization: {score:.0%}  found: {hit_words}")

    avg = sum(scores) / len(scores)
    print(f"\n  ✅ avg: {avg:.0%}")
    return {"agent": agent_name, "avg": avg, "source": bm["source"]}


def main():
    args = sys.argv[1:]
    session = TruSession(database_url=f"sqlite:///{DB_PATH}")

    if "--dashboard" in args:
        print("Starting dashboard at http://localhost:8501 ...")
        session.run_dashboard()
        return

    targets = [a for a in args if not a.startswith("--")] or list(BENCHMARKS.keys())

    print(f"\n🔍 Agent memory utilization eval  ({datetime.now().strftime('%Y-%m-%d %H:%M')})")
    print(f"   Agents: {targets}")

    results = []
    for name in targets:
        r = eval_agent(name, session)
        if r:
            results.append(r)

    if not results:
        return

    print(f"\n{'='*58}")
    print("📊 Summary")
    print(f"{'='*58}")
    for r in sorted(results, key=lambda x: x["avg"], reverse=True):
        bar = "█" * int(r["avg"] * 10) + "░" * (10 - int(r["avg"] * 10))
        flag = "🔴" if r["avg"] < 0.3 else ("🟡" if r["avg"] < 0.6 else "🟢")
        print(f"  {flag} {r['agent']:<22} {bar}  {r['avg']:.0%}")

    overall = sum(r["avg"] for r in results) / len(results)
    print(f"\n  Overall: {overall:.0%}")
    print(f"\n  Dashboard: python {Path(__file__).name} --dashboard")

    out_path = Path(__file__).parent / f"eval_result_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    out_path.write_text(json.dumps(results, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"  Saved: {out_path.name}")


if __name__ == "__main__":
    main()
