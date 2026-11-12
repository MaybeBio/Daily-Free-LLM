from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = ROOT / "config"
DATA_DIR = ROOT / "data"
SITE_DIR = ROOT / "site"
SNAPSHOT_DIR = DATA_DIR / "snapshots"
DAILY_DIR = DATA_DIR / "daily"
REFS_DIR = ROOT / "refers_template"

CST = timezone(timedelta(hours=8))


def ensure_dirs() -> None:
    for path in (CONFIG_DIR, DATA_DIR, SNAPSHOT_DIR, DAILY_DIR, SITE_DIR):
        path.mkdir(parents=True, exist_ok=True)


def now_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_cst(fmt: str = "%Y-%m-%d %H:%M:%S") -> str:
    return datetime.now(CST).strftime(fmt)


def today_iso() -> str:
    return datetime.now(CST).strftime("%Y-%m-%d")


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(text, encoding="utf-8", newline="\n")
    os.replace(tmp, path)


def read_json(path: Path, default=None):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        raise SystemExit(f"JSON 解析失败: {path}: {exc}") from exc


def write_json(path: Path, data) -> None:
    text = json.dumps(data, ensure_ascii=False, indent=2) + "\n"
    atomic_write(path, text)


def read_jsonl(path: Path) -> list[dict]:
    if not Path(path).exists():
        return []
    records = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            log(f"跳过损坏的 JSONL 行: {path}")
    return records


def append_jsonl(path: Path, record: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(record, ensure_ascii=False) + "\n")


def sha(text: str, length: int = 16) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:length]


def slugify_id(text: str) -> str:
    import unicodedata

    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    plain = re.sub(r"[^a-zA-Z0-9]+", "-", plain).strip("-").lower()
    if not plain:
        plain = "x-" + hashlib.sha1(text.encode("utf-8")).hexdigest()[:8]
    return plain[:64]


def log(message: str) -> None:
    print(message, file=sys.stderr)


def load_env_file(path: Path | None = None) -> None:
    path = path or (ROOT / ".env")
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'\"")
        if key and key not in os.environ:
            os.environ[key] = value


def expand_env(text: str) -> str:
    def repl(match: re.Match[str]) -> str:
        return os.environ.get(match.group(1), match.group(0))

    return re.sub(r"\{([A-Z0-9_]+)\}", repl, text)


def http_request(
    method: str,
    url: str,
    data: bytes | None = None,
    headers: dict | None = None,
    timeout: float = 30.0,
) -> tuple[int, str, dict]:
    request_headers = {
        "User-Agent": "freellm-shovel/0.1 (+https://github.com/)",
        "Accept": "application/json, text/plain, */*",
    }
    if headers:
        request_headers.update(headers)
    req = urllib.request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read().decode("utf-8", "replace"), dict(resp.headers)
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", "replace") if exc.fp else ""
        return exc.code, body, dict(exc.headers or {})
    except urllib.error.URLError as exc:
        return 0, str(exc.reason), {}
    except TimeoutError:
        return 0, "timeout", {}


def parse_int(value) -> int | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    match = re.search(r"(\d+(?:\.\d+)?)([kKmMbB])?", str(value).replace(",", ""))
    if not match:
        return None
    scale = {"k": 1_000, "m": 1_000_000, "b": 1_000_000_000}.get(
        (match.group(2) or "").lower(), 1
    )
    return int(float(match.group(1)) * scale)
