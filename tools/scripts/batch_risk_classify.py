#!/usr/bin/env python3
"""
Batch risk classifier for agentic skills using the Anthropic Batches API.

Submits all skills to Claude at once for context-aware risk reclassification,
at 50% off standard pricing.

Requirements (not included in tools/requirements.txt to keep CI lean):
    pip install -r tools/requirements-batch.txt

Usage:
    python tools/scripts/batch_risk_classify.py              # dry run, all skills
    python tools/scripts/batch_risk_classify.py --limit 5    # test with 5 skills
    python tools/scripts/batch_risk_classify.py --filter-risk unknown  # only unknown
    python tools/scripts/batch_risk_classify.py --apply      # write changes back
    python tools/scripts/batch_risk_classify.py --resume <batch_id>  # resume a batch
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path

import anthropic

REPO_ROOT = Path(__file__).parent.parent.parent
SKILLS_INDEX = REPO_ROOT / "skills_index.json"
RESULTS_FILE = Path(__file__).parent / "batch_risk_results.json"
REPORT_FILE = Path(__file__).parent / "batch_risk_report.csv"

VALID_RISKS = {"safe", "critical", "none", "unknown", "offensive"}
SKILL_CONTENT_LIMIT = 3_000  # chars — keeps tokens manageable

SYSTEM_PROMPT = """You classify agentic skill files by their risk level.

Risk levels:
- safe       — read-only, diagnostic, analysis, visualization; no side effects on files/APIs/systems
- none       — general-purpose assistant behavior with no clear risk signal either way
- unknown    — genuinely ambiguous; could be safe or risky depending on how it is invoked
- critical   — writes or modifies files, commits code, deploys to servers, calls mutating APIs,
               handles secrets/credentials, or performs any action that changes external state
- offensive  — explicitly designed for penetration testing, red teaming, exploit development,
               malware research, or jailbreak attempts

Output exactly one line of JSON with two keys, nothing else:
{"risk": "<level>", "reason": "<one concise sentence explaining the classification>"}"""


def load_skills(limit: int | None, filter_risk: str | None) -> list[dict]:
    with open(SKILLS_INDEX) as f:
        skills = json.load(f)

    if filter_risk:
        skills = [s for s in skills if s.get("risk") == filter_risk]

    if limit is not None:
        skills = skills[:limit]

    return skills


def read_skill_content(skill: dict) -> str:
    skill_path = REPO_ROOT / skill["path"] / "SKILL.md"
    if not skill_path.exists():
        return f"name: {skill['id']}\ndescription: {skill.get('description', '')}"

    content = skill_path.read_text(encoding="utf-8", errors="replace")
    if len(content) > SKILL_CONTENT_LIMIT:
        content = content[:SKILL_CONTENT_LIMIT] + "\n[truncated]"
    return content


def build_batch_requests(skills: list[dict]) -> list[dict]:
    requests = []
    for skill in skills:
        content = read_skill_content(skill)
        requests.append({
            "custom_id": skill["id"],
            "params": {
                "model": "claude-haiku-4-5",
                "max_tokens": 128,
                "system": SYSTEM_PROMPT,
                "messages": [{"role": "user", "content": content}],
            },
        })
    return requests


def submit_batch(client: anthropic.Anthropic, requests: list[dict]) -> str:
    print(f"Submitting batch of {len(requests)} requests...")
    batch = client.messages.batches.create(requests=requests)
    print(f"Batch ID: {batch.id}")
    print(f"Status:   {batch.processing_status}")
    return batch.id


def poll_until_done(client: anthropic.Anthropic, batch_id: str, poll_interval: int = 30) -> None:
    while True:
        batch = client.messages.batches.retrieve(batch_id)
        counts = batch.request_counts
        total = counts.processing + counts.succeeded + counts.errored + counts.canceled + counts.expired
        done = counts.succeeded + counts.errored + counts.canceled + counts.expired
        print(f"  [{batch.processing_status}] {done}/{total} done "
              f"(succeeded={counts.succeeded}, errored={counts.errored})")

        if batch.processing_status == "ended":
            break

        time.sleep(poll_interval)


def parse_risk_from_text(text: str) -> tuple[str, str]:
    """Extract risk and reason from Claude's JSON response. Returns (risk, reason)."""
    # Try to find JSON in the response
    match = re.search(r'\{[^}]+\}', text, re.DOTALL)
    if match:
        try:
            data = json.loads(match.group())
            risk = str(data.get("risk", "")).strip().lower()
            reason = str(data.get("reason", "")).strip()
            if risk in VALID_RISKS:
                return risk, reason
        except json.JSONDecodeError:
            pass

    # Fallback: scan for a bare risk keyword
    for level in ("offensive", "critical", "safe", "none", "unknown"):
        if re.search(rf'\b{level}\b', text, re.IGNORECASE):
            return level, "extracted from unstructured response"

    return "unknown", "could not parse response"


def collect_results(
    client: anthropic.Anthropic,
    batch_id: str,
    skills_by_id: dict[str, dict],
) -> list[dict]:
    results = []
    print("Streaming results...")
    for result in client.messages.batches.results(batch_id):
        skill_id = result.custom_id
        skill = skills_by_id.get(skill_id, {})
        old_risk = skill.get("risk", "unknown")

        if result.result.type == "succeeded":
            message = result.result.message
            text = ""
            for block in message.content:
                if block.type == "text":
                    text = block.text
                    break
            new_risk, reason = parse_risk_from_text(text)
            error = None
        elif result.result.type == "errored":
            new_risk = old_risk  # keep original on API error
            reason = "API error; kept original risk"
            error = str(result.result.error)
        else:
            new_risk = old_risk
            reason = f"result type={result.result.type}; kept original"
            error = None

        results.append({
            "id": skill_id,
            "category": skill.get("category", ""),
            "old_risk": old_risk,
            "new_risk": new_risk,
            "reason": reason,
            "changed": new_risk != old_risk,
            "error": error,
        })

    return results


def write_outputs(results: list[dict]) -> None:
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2)
    print(f"Results written to {RESULTS_FILE}")

    with open(REPORT_FILE, "w", newline="") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["id", "category", "old_risk", "new_risk", "reason", "changed", "error"],
        )
        writer.writeheader()
        writer.writerows(results)
    print(f"Report written to {REPORT_FILE}")


def print_summary(results: list[dict]) -> None:
    changed = [r for r in results if r["changed"]]
    errors = [r for r in results if r["error"]]

    from collections import Counter
    old_dist = Counter(r["old_risk"] for r in results)
    new_dist = Counter(r["new_risk"] for r in results)

    print(f"\n{'='*50}")
    print(f"Total: {len(results)}  Changed: {len(changed)}  Errors: {len(errors)}")
    print(f"\nBefore: {dict(old_dist)}")
    print(f"After:  {dict(new_dist)}")

    if changed:
        print(f"\nSample changes ({min(5, len(changed))}):")
        for r in changed[:5]:
            print(f"  {r['id']}: {r['old_risk']} → {r['new_risk']}  ({r['reason']})")


def apply_to_index(results: list[dict]) -> None:
    with open(SKILLS_INDEX) as f:
        skills = json.load(f)

    result_map = {r["id"]: r["new_risk"] for r in results}
    updated = 0
    for skill in skills:
        new_risk = result_map.get(skill["id"])
        if new_risk and skill.get("risk") != new_risk:
            skill["risk"] = new_risk
            updated += 1

    with open(SKILLS_INDEX, "w") as f:
        json.dump(skills, f, indent=2)
        f.write("\n")

    print(f"Updated {updated} skills in {SKILLS_INDEX.name}")


def apply_to_frontmatter(results: list[dict], skills_by_id: dict[str, dict]) -> None:
    RISK_RE = re.compile(r"^(risk:\s*)(.+)$", re.MULTILINE)
    updated = 0

    for r in results:
        if not r["changed"]:
            continue
        skill = skills_by_id.get(r["id"])
        if not skill:
            continue

        skill_md = REPO_ROOT / skill["path"] / "SKILL.md"
        if not skill_md.exists():
            continue

        content = skill_md.read_text(encoding="utf-8", errors="replace")
        new_content = RISK_RE.sub(lambda m: f"{m.group(1)}{r['new_risk']}", content, count=1)

        if new_content != content:
            skill_md.write_text(new_content, encoding="utf-8")
            updated += 1

    print(f"Updated frontmatter in {updated} SKILL.md files")


def main() -> None:
    parser = argparse.ArgumentParser(description="Batch-classify skill risk levels with Claude")
    parser.add_argument("--apply", action="store_true", help="Write changes back to files")
    parser.add_argument("--limit", type=int, metavar="N", help="Only process first N skills")
    parser.add_argument("--filter-risk", metavar="LEVEL", help="Only process skills with this risk level")
    parser.add_argument("--resume", metavar="BATCH_ID", help="Resume polling an existing batch")
    parser.add_argument("--poll-interval", type=int, default=30, metavar="SECS")
    args = parser.parse_args()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    skills = load_skills(limit=args.limit, filter_risk=args.filter_risk)
    if not skills:
        print("No skills matched. Nothing to do.")
        sys.exit(0)

    print(f"Loaded {len(skills)} skills")
    skills_by_id = {s["id"]: s for s in skills}

    if args.resume:
        batch_id = args.resume
        print(f"Resuming batch {batch_id}")
    else:
        requests = build_batch_requests(skills)
        batch_id = submit_batch(client, requests)

    print("Polling for completion...")
    poll_until_done(client, batch_id, poll_interval=args.poll_interval)

    results = collect_results(client, batch_id, skills_by_id)
    write_outputs(results)
    print_summary(results)

    if args.apply:
        print("\nApplying changes...")
        apply_to_index(results)
        apply_to_frontmatter(results, skills_by_id)
        print("Done. Run `git diff` to review changes before committing.")
    else:
        print("\nDry run complete. Use --apply to write changes back to files.")


if __name__ == "__main__":
    main()
