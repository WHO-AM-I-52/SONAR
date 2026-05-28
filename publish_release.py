# publish_release.py
# Создаёт GitHub Releases из changelog.py
# Кладёт собой: python publish_release.py
# Требуется .env с GITHUB_TOKEN
#
# Как получить токен:
# github.com → Settings → Developer settings → Personal access tokens → Fine-grained
# Права: Contents (read/write), Metadata (read)

import urllib.error
import os
from github_utils import load_token, get_json, post_json

REPO_OWNER = "WHO-AM-I-52"
REPO_NAME  = "SONAR"
BRANCH     = "main"

AGENT = "SONAR-Publisher"


def get_existing_tags(token):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases?per_page=100"
    data = get_json(url, agent=AGENT)
    return {r["tag_name"] for r in data}


def create_release(tag, name, body):
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/releases"
    status, resp = post_json(url, {
        "tag_name":         tag,
        "target_commitish": BRANCH,
        "name":             name,
        "body":             body,
        "draft":            False,
        "prerelease":       False,
    }, agent=AGENT)
    if status == 201:
        return True, resp.get("html_url", "")
    return False, resp.get("message", str(resp))


def load_releases_from_changelog():
    try:
        from changelog import CHANGELOG
    except ImportError:
        print("[ERROR] changelog.py not found")
        return []
    result = []
    for entry in CHANGELOG:
        version = entry["version"]
        if not version.startswith("v"):
            version = "v" + version
        name = version
        body = "\n".join(f"- {c}" for c in entry.get("changes", []))
        result.append({"tag": version, "name": name, "body": body})
    return result


def main():
    print()
    print(" ================================================")
    print("  SONAR — Публикация GitHub Releases")
    print(" ================================================")
    print()

    token = load_token()
    if not token:
        print("[ERROR] Не найден GITHUB_TOKEN в .env")
        print()
        print("  Создай файл .env рядом со скриптом:")
        print("  GITHUB_TOKEN=ghp_xxxxxxxxxxxxxxxxxxxx")
        print()
        print("  Где взять токен:")
        print("  github.com → Settings → Developer settings")
        print("  → Personal access tokens → Fine-grained tokens")
        print("  Права: Contents (read/write), Metadata (read)")
        print()
        input("Press any key to exit...")
        return

    releases = load_releases_from_changelog()
    if not releases:
        print("[ERROR] changelog.py пустой или не найден")
        return

    print(f"  Найдено версий в changelog.py: {len(releases)}")
    print("  Проверяю существующие релизы на GitHub...")
    print()

    try:
        existing = get_existing_tags(token)
    except Exception as e:
        print(f"[ERROR] Не удалось получить список релизов: {e}")
        return

    created = 0
    skipped = 0
    errors  = 0

    for r in reversed(releases):
        tag = r["tag"]
        if tag in existing:
            print(f"  ⏭  {tag} — уже существует, пропускаю")
            skipped += 1
            continue
        ok, info = create_release(tag, r["name"], r["body"])
        if ok:
            print(f"  ✅  {tag} — опубликован")
            created += 1
        else:
            print(f"  ❌  {tag} — ошибка: {str(info)[:120]}")
            errors += 1

    print()
    print(f"  Итог: создано {created}, пропущено {skipped}, ошибок {errors}")
    print()
    input("Press any key to exit...")


if __name__ == "__main__":
    main()
