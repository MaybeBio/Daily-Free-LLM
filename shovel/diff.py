from __future__ import annotations

import json
import re
from pathlib import Path

from . import util

_VOLATILE = re.compile(
    r"(访问量|浏览量|阅读量|在线人数|今日更新|updated at|generated at|统计时间|"
    r"last updated|page views)",
    re.IGNORECASE,
)


def normalize_lines(text: str) -> list[str]:
    lines = []
    for raw in str(text or "").splitlines():
        line = re.sub(r"\s+", " ", raw).strip()
        if not line or _VOLATILE.search(line):
            continue
        lines.append(line)
    return lines


def diff_lines(old: list[str], new: list[str]) -> dict:
    old_set, new_set = set(old), set(new)
    added = sorted(new_set - old_set)
    removed = sorted(old_set - new_set)
    return {
        "added": added,
        "removed": removed,
        "added_count": len(added),
        "removed_count": len(removed),
    }


def update_snapshot(
    source_id: str,
    content: str,
    snapshot_dir: Path | None = None,
) -> dict:
    snapshot_dir = snapshot_dir or util.SNAPSHOT_DIR
    path = snapshot_dir / f"{source_id}.txt"
    previous = path.read_text(encoding="utf-8") if path.exists() else None
    util.atomic_write(path, content)
    if previous is None:
        return {
            "baseline": True,
            "added": [],
            "removed": [],
            "added_count": 0,
            "removed_count": 0,
        }
    result = diff_lines(normalize_lines(previous), normalize_lines(content))
    result["baseline"] = False
    return result


def append_changes(
    path: Path,
    source_id: str,
    name: str,
    diff: dict,
    at: str | None = None,
    cap: int = 50,
) -> dict | None:
    if not diff.get("added") and not diff.get("removed"):
        return None
    record = {
        "at": at or util.now_utc(),
        "source": source_id,
        "name": name,
        "added_count": diff.get("added_count", 0),
        "removed_count": diff.get("removed_count", 0),
        "added": diff.get("added", [])[:cap],
        "removed": diff.get("removed", [])[:cap],
    }
    util.append_jsonl(path, record)
    return record


def append_history(path: Path, record: dict, keep: int = 500) -> None:
    records = util.read_jsonl(path)
    records.append(record)
    records = records[-keep:]
    text = "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records)
    util.atomic_write(path, text)
