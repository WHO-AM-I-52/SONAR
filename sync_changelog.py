import json
import re
import os
from datetime import datetime
from github_utils import load_token, get_headers, get_json

REPO_OWNER = "WHO-AM-I-52"
REPO_NAME = "SONAR"
BRANCH = "main"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CHANGELOG_PATH = os.path.join(BASE_DIR, "changelog.py")
ROADMAP_PATH = os.path.join(BASE_DIR, "roadmap.py")

TOKEN = load_token()


def get_text(url):
    import urllib.request
    req = urllib.request.Request(url, headers={"User-Agent": "SONAR-Sync"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return r.read().decode("utf-8")


def _py_str(value: str) -> str:
    """Возвращает корректный Python-строковый литерал для любого текста.

    Использует repr() вместо ручной замены кавычек — безопасно экранирует
    одинарные кавычки, двойные кавычки, переносы строк и спецсимволы.
    fix #33
    """
    return repr(str(value))


def fetch_releases():
    data = get_json(
        f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases?per_page=100",
        agent="SONAR-Sync"
    )
    changelog = []
    for r in data:
        published_at = r.get("published_at")
        if not published_at:
            continue
        version = r["tag_name"].lstrip("v")
        try:
            date = datetime.strptime(published_at, "%Y-%m-%dT%H:%M:%SZ").strftime("%d.%m.%Y")
        except Exception:
            date = ""
        body = r.get("body", "") or ""
        changes = []
        for line in body.splitlines():
            line = line.strip()
            if line.startswith(("-", "*", "\u2013")):
                changes.append(line.lstrip("-*\u2013 ").strip())
        if not changes:
            changes = [r.get("name", f"Release {version}")]
        changelog.append({"version": version, "date": date, "changes": changes})
    return changelog


def fetch_roadmap():
    url = (f"https://raw.githubusercontent.com/"
           f"{REPO_OWNER}/{REPO_NAME}/{BRANCH}/ROADMAP.md")
    content = get_text(url)
    roadmap = []

    STATUS_MAP = {
        "В работе":      "in_progress",
        "Запланировано": "planned",
        "Идеи":          "idea",
        "Реализовано":   "done",
        "Готово":        "done",
    }

    current_status = "planned"
    current_entry = None

    for line in content.splitlines():
        if re.match(r"^##\s+", line):
            for key, val in STATUS_MAP.items():
                if key in line:
                    current_status = val
                    break
            if current_entry:
                roadmap.append(current_entry)
                current_entry = None
            continue

        title_match = re.match(r"^###\s+(.+)", line)
        if title_match:
            if current_entry:
                roadmap.append(current_entry)
            current_entry = {
                "version": "",
                "title": title_match.group(1).strip(),
                "status": current_status,
                "eta": "",
                "points": [],
            }
            continue

        if current_entry and re.match(r"^[-*]\s+", line):
            point = re.sub(r"^[-*]\s+", "", line).strip()
            current_entry["points"].append(point)

    if current_entry:
        roadmap.append(current_entry)

    roadmap = [r for r in roadmap if r["status"] != "done"]
    return roadmap


def write_changelog(changelog):
    """Записывает только CHANGELOG в changelog.py."""
    lines = ["CHANGELOG = [\n"]
    for entry in changelog:
        lines.append("    {\n")
        lines.append(f'        "version": {_py_str(entry["version"])},\n')
        lines.append(f'        "date": {_py_str(entry["date"])},\n')
        lines.append('        "changes": [\n')
        for c in entry["changes"]:
            lines.append(f'            {_py_str(c)},\n')
        lines.append("        ],\n")
        lines.append("    },\n")
    lines.append("]\n")

    with open(CHANGELOG_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def write_roadmap(roadmap):
    """Записывает только ROADMAP в roadmap.py."""
    lines = ["ROADMAP = [\n"]
    for entry in roadmap:
        lines.append("    {\n")
        lines.append(f'        "version": {_py_str(entry.get("version", ""))},\n')
        lines.append(f'        "title": {_py_str(entry["title"])},\n')
        lines.append(f'        "status": {_py_str(entry["status"])},\n')
        lines.append(f'        "eta": {_py_str(entry.get("eta", ""))},\n')
        lines.append('        "points": [\n')
        for p in entry["points"]:
            lines.append(f'            {_py_str(p)},\n')
        lines.append("        ],\n")
        lines.append("    },\n")
    lines.append("]\n")

    with open(ROADMAP_PATH, "w", encoding="utf-8") as f:
        f.writelines(lines)


def main():
    print("  Синхронизация changelog с GitHub...")
    if TOKEN:
        print("  Токен найден — лимит 5000 запросов/час")
    else:
        print("  Токен не найден — лимит 60 запросов/час")
    try:
        releases = fetch_releases()
        print(f"  Релизов найдено: {len(releases)}")

        roadmap = fetch_roadmap()
        print(f"  ROADMAP записей: {len(roadmap)}")

        if not releases:
            print("  [!] Релизов нет — CHANGELOG не обновляется.")
            from changelog import CHANGELOG as existing
            releases = [{"version": e["version"],
                         "date": e["date"],
                         "changes": e["changes"]} for e in existing]

        write_changelog(releases)
        print("  changelog.py обновлён.")

        write_roadmap(roadmap)
        print("  roadmap.py обновлён.")

    except Exception as e:
        print(f"  [ОШИБКА] {e}")


if __name__ == "__main__":
    main()
