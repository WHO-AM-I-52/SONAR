# ╔════════════════════════════════════════════════════════════════════════╗
# ║                         _updater.py                                     ║
# ║  Скачивает обновления SONAR с GitHub одним zip-архивом (1 API-запрос)   ║
# ║  Режим --check: сравнивает SHA и выходит без скачивания                 ║
# ║  Не трогает БД и файлы пользователя.                                    ║
# ║  get_commits_between: список коммитов для панели обновлений              ║
# ╚════════════════════════════════════════════════════════════════════════╝

import urllib.request
import urllib.error
import zipfile
import shutil
import hashlib
import json
import subprocess
import sys
import os
import re
import ast
import time

REPO_OWNER    = "WHO-AM-I-52"
REPO_NAME     = "SONAR"
BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
API_BASE      = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}"
COMMIT_FILE   = os.path.join(BASE_DIR, "_last_commit.txt")
BRANCH_FILE   = os.path.join(BASE_DIR, "_branch.txt")
FALLBACK_KB   = 600

# ── Читаем активную ветку из _branch.txt (по умолчанию main) ─────────────────
def load_branch() -> str:
    if os.path.exists(BRANCH_FILE):
        try:
            val = open(BRANCH_FILE, encoding="utf-8").read().strip()
            if val in ("main", "dev"):
                return val
        except Exception:
            pass
    return "main"

BRANCH = load_branch()

BAT_NAME = "start SONAR.bat"

# update.bat намеренно НЕ защищён — обновляется автоматически как обычный файл
PROTECTED_FILES = {
    "database.db",
    "database_backup.db",
    "_secret.key",
    "_last_commit.txt",
    "_update_available.json",
    "_updating.lock",
    "_restart.flag",
    "_branch.txt",
    ".env",
    BAT_NAME,
}


def get_token() -> str | None:
    env_path = os.path.join(BASE_DIR, ".env")
    token = os.environ.get("GITHUB_TOKEN")
    if not token and os.path.exists(env_path):
        try:
            with open(env_path, encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GITHUB_TOKEN="):
                        token = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    return token


def gh_headers() -> dict:
    token = get_token()
    h = {"User-Agent": "SONAR-Updater", "Accept": "application/vnd.github+json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers=gh_headers())
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read().decode())


def show_rate_limit(headers):
    remaining = headers.get("x-ratelimit-remaining", "?")
    limit     = headers.get("x-ratelimit-limit",     "?")
    reset_ts  = headers.get("x-ratelimit-reset")
    reset_str = None
    if reset_ts:
        try:
            from datetime import datetime
            reset_str = datetime.fromtimestamp(int(reset_ts)).strftime("%H:%M:%S")
        except Exception:
            pass
    print(f"  [GitHub API] лимит запросов: {remaining}/{limit}"
          + (f" (сброс в {reset_str})" if reset_str else ""))


# ─── Список коммитов между двумя SHA ────────────────────────────────────────

def get_commits_between(local_sha: str, remote_sha: str) -> list:
    """Возвращает список коммитов между local_sha и remote_sha (до 20 шт.).
    Каждый элемент: {'sha': str, 'message': str, 'date': str}.
    Используется панелью обновлений в changelog.html.
    """
    try:
        data = get_json(f"{API_BASE}/compare/{local_sha}...{remote_sha}")
        commits = []
        for c in data.get("commits", [])[:20]:
            msg      = c.get("commit", {}).get("message", "").split("\n")[0]
            sha      = c.get("sha", "")[:7]
            date_raw = c.get("commit", {}).get("author", {}).get("date", "")
            date_str = date_raw[:10] if date_raw else ""
            commits.append({"sha": sha, "message": msg, "date": date_str})
        commits.reverse()  # новые сверху
        return commits
    except Exception as e:
        print(f"  [Внимание] Не удалось получить список коммитов: {e}")
        return []


# ─── Проверка обновлений по SHA ─────────────────────────────────────────────

def get_remote_sha() -> str | None:
    try:
        url = f"{API_BASE}/git/refs/heads/{BRANCH}"
        req = urllib.request.Request(url, headers=gh_headers())
        with urllib.request.urlopen(req, timeout=20) as r:
            show_rate_limit(r.headers)
            data = json.loads(r.read().decode())
        sha = data.get("object", {}).get("sha")
        print(f"  Последний коммит GitHub: {sha[:12] if sha else 'N/A'}")
        return sha
    except urllib.error.HTTPError as e:
        print(f"  [Ошибка] GitHub API: HTTP {e.code}")
        return None
    except Exception as e:
        print(f"  [Ошибка] Не удалось получить SHA: {e}")
        return None


def get_local_sha() -> str | None:
    if os.path.exists(COMMIT_FILE):
        try:
            return open(COMMIT_FILE, encoding="utf-8").read().strip()
        except Exception:
            pass
    return None


def save_local_sha(sha: str):
    try:
        with open(COMMIT_FILE, "w", encoding="utf-8") as f:
            f.write(sha)
    except Exception as e:
        print(f"  [Предупреждение] Не удалось сохранить SHA: {e}")


def check_for_updates() -> int:
    print()
    print("  ================================================")
    print(f"   SONAR - Проверка обновлений (ветка: {BRANCH})")
    print("  ================================================")
    print()
    print("  Подключаемся к GitHub...")
    remote_sha = get_remote_sha()
    if not remote_sha:
        print("  Не удалось получить данные с GitHub.")
        return 2
    local_sha = get_local_sha()
    print(f"  Установленная версия:  {local_sha[:12] if local_sha else 'неизвестна'}")
    print(f"  GitHub версия: {remote_sha[:12]}")
    if local_sha and remote_sha.startswith(local_sha) or local_sha == remote_sha:
        print("  Установлена актуальная версия.")
        return 0
    print("  Доступно обновление!")
    return 1


# ─── Размер архива ───────────────────────────────────────────────────────────

def get_zip_size_kb() -> int:
    url = f"{API_BASE}/zipball/{BRANCH}"
    try:
        req = urllib.request.Request(url, headers=gh_headers(), method="HEAD")
        with urllib.request.urlopen(req, timeout=10) as r:
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl) // 1024
    except Exception:
        pass
    try:
        req2 = urllib.request.Request(url, headers=gh_headers())
        with urllib.request.urlopen(req2, timeout=10) as r:
            cl = r.headers.get("Content-Length")
            if cl:
                return int(cl) // 1024
    except Exception:
        pass
    return FALLBACK_KB


SPINNER = ["|  ", " | ", "  |"]


def _print_progress(downloaded: int, estimated_kb: int, spinner_idx: int):
    dl_kb = downloaded // 1024
    if estimated_kb > 0:
        pct = min(100, int(dl_kb * 100 / estimated_kb))
        bar = "#" * (pct // 5) + "-" * (20 - pct // 5)
        line = f"  {SPINNER[spinner_idx % 3]} Скачано: {dl_kb} КБ / ~{estimated_kb} КБ  [{bar}] {pct}%"
    else:
        line = f"  {SPINNER[spinner_idx % 3]} Скачано: {dl_kb} КБ"
    print(f"\r{line}", end="", flush=True)


def download_zip(zip_path: str):
    print(f"  Определяем размер архива обновления (ветка: {BRANCH})...")
    estimated_kb = get_zip_size_kb()
    print(f"  Ожидаемый размер архива: ~{estimated_kb} КБ")
    url = f"{API_BASE}/zipball/{BRANCH}"
    req = urllib.request.Request(url, headers=gh_headers())
    try:
        with urllib.request.urlopen(req, timeout=60) as r, open(zip_path, "wb") as f:
            chunk_size   = 8192
            downloaded   = 0
            spinner_idx  = 0
            last_print   = time.monotonic()
            while True:
                chunk = r.read(chunk_size)
                if not chunk:
                    break
                f.write(chunk)
                downloaded  += len(chunk)
                spinner_idx += 1
                now = time.monotonic()
                if now - last_print > 0.15:
                    _print_progress(downloaded, estimated_kb, spinner_idx)
                    last_print = now
        print()
        print(f"  Архив скачан: {downloaded // 1024} КБ")
    except urllib.error.HTTPError as e:
        print(f"\n  [Ошибка] HTTP {e.code} при скачивании архива")
        raise
    except Exception as e:
        print(f"\n  [Ошибка] {e}")
        raise


PROTECTED_EXTENSIONS = {".db", ".key", ".env", ".lock", ".flag"}


def should_skip(rel_path: str) -> bool:
    name = os.path.basename(rel_path)
    if name in PROTECTED_FILES:
        return True
    _, ext = os.path.splitext(name)
    if ext in PROTECTED_EXTENSIONS:
        return True
    # Пропускаем папку uploads и reports
    parts = rel_path.replace("\\", "/").split("/")
    if "uploads" in parts or "reports" in parts:
        return True
    return False


def apply_zip(zip_path: str, dest_dir: str) -> str | None:
    """Распаковывает обновление из zip в dest_dir.
    Возвращает SHA нового коммита (из имени корневой папки архива) или None."""
    new_sha = None
    with zipfile.ZipFile(zip_path, "r") as zf:
        names = zf.namelist()
        if not names:
            print("  [Ошибка] Пустой архив")
            return None
        root_prefix = names[0]  # WHO-AM-I-52-SONAR-<sha>/
        # Извлекаем SHA из имени папки
        try:
            new_sha = root_prefix.rstrip("/").split("-")[-1]
        except Exception:
            pass

        total   = len(names)
        updated = 0
        skipped = 0
        print(f"  Применяем обновление... (файлов в архиве: {total})")
        for member in names:
            rel = member[len(root_prefix):]
            if not rel:
                continue
            if should_skip(rel):
                skipped += 1
                continue
            target = os.path.join(dest_dir, rel)
            if member.endswith("/"):
                os.makedirs(target, exist_ok=True)
            else:
                os.makedirs(os.path.dirname(target), exist_ok=True)
                with zf.open(member) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                updated += 1
    print(f"  Обновлено файлов: {updated}, пропущено защищённых: {skipped}")
    return new_sha


def load_changelog():
    changelog_path = os.path.join(BASE_DIR, "changelog.py")
    if not os.path.exists(changelog_path):
        return None, None
    try:
        with open(changelog_path, encoding="utf-8") as f:
            source = f.read()

        match = re.search(r"CHANGELOG\s*=\s*(\[.*?\])", source, re.DOTALL)
        if not match:
            return None, None

        cl = ast.literal_eval(match.group(1))
        if not cl:
            return None, None

        latest = cl[0]
        version = latest.get("version", "").strip()
        items   = latest.get("items",   [])
        body    = "\n".join(f"- {item}" for item in items) if items else ""
        return version, body or f"Release {version}"
    except Exception as e:
        print(f"  [Предупреждение] Не удалось прочитать changelog.py: {e}")
        return None, None


def ensure_github_release():
    token = get_token()
    if not token:
        print("  [Релиз] Токен не найден — автосоздание релиза пропущено.")
        return

    # Релиз создаём только для main-ветки
    if BRANCH != "main":
        print(f"  [Релиз] Ветка {BRANCH} — автосоздание релиза пропущено.")
        return

    version, body = load_changelog()
    if not version:
        print("  [Релиз] Не удалось определить версию — пропуск.")
        return

    tag = f"v{version}"
    try:
        existing_url = f"{API_BASE}/releases/tags/{tag}"
        req = urllib.request.Request(existing_url, headers=gh_headers())
        with urllib.request.urlopen(req, timeout=10):
            print(f"  [Релиз] {tag} уже существует — пропуск.")
            return
    except urllib.error.HTTPError as e:
        if e.code != 404:
            print(f"  [Релиз] Ошибка проверки существующего релиза: {e.code}")
            return

    payload = json.dumps({
        "tag_name":         tag,
        "target_commitish": "main",
        "name":             f"SONAR {tag}",
        "body":             body,
        "draft":            False,
        "prerelease":       False,
    }).encode()

    headers = {**gh_headers(), "Content-Type": "application/json"}
    try:
        req = urllib.request.Request(
            f"{API_BASE}/releases", data=payload, headers=headers, method="POST"
        )
        with urllib.request.urlopen(req, timeout=15) as r:
            resp = json.loads(r.read().decode())
        print(f"  [Релиз] Создан: {resp.get('html_url', '')}")
    except Exception as e:
        print(f"  [Релиз] Ошибка создания: {e}")


def run_sync_changelog():
    """Синхронизирует changelog.py с GitHub Releases после обновления."""
    sync_path = os.path.join(BASE_DIR, "sync_changelog.py")
    if not os.path.exists(sync_path):
        print("  [Changelog] sync_changelog.py не найден — пропуск.")
        return
    try:
        result = subprocess.run(
            [sys.executable, sync_path],
            cwd=BASE_DIR,
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            print("  [Changelog] Синхронизация выполнена.")
        else:
            print(f"  [Changelog] Ошибка: {result.stderr[-200:]}")
    except Exception as e:
        print(f"  [Changelog] Не удалось запустить sync_changelog.py: {e}")


def main():
    is_check = "--check" in sys.argv
    print()
    print("  ================================================")
    print("   SONAR - Менеджер обновлений")
    print("  ================================================")
    print()

    token = get_token()
    if token:
        print("  Токен найден — лимит 5000 запросов/час")
    else:
        print("  Токен не найден — лимит 60 запросов/час")
    print(f"  Активная ветка: {BRANCH}")

    remote_sha = get_remote_sha()
    if not remote_sha:
        print("  Нет соединения с GitHub или ошибка API.")
        sys.exit(2)

    local_sha = get_local_sha()
    print(f"  Установленная версия:  {local_sha[:12] if local_sha else 'неизвестна'}")
    print(f"  GitHub версия: {remote_sha[:12]}")
    print()

    if local_sha and (remote_sha.startswith(local_sha) or local_sha == remote_sha):
        print("  Установлена актуальная версия.")
        if is_check:
            sys.exit(0)
    else:
        print("  Доступно обновление!")
        if is_check:
            print("  Используйте интерфейс SONAR или update.bat для обновления.")
            sys.exit(1)

    # ── Скачивание и применение ──────────────────────────────────────────────
    lock_path = os.path.join(BASE_DIR, "_updating.lock")
    if os.path.exists(lock_path):
        print("  Обновление уже выполняется (lock-файл найден).")
        sys.exit(2)

    try:
        open(lock_path, "w").write("updating")
    except Exception:
        pass

    zip_path = os.path.join(BASE_DIR, "_update.zip")
    bat_updated = False

    try:
        print("  Скачиваем архив обновления...")
        download_zip(zip_path)

        print("  Проверяем содержимое архива...")
        with zipfile.ZipFile(zip_path, "r") as zf:
            names = zf.namelist()
        bat_in_zip = any(os.path.basename(n) == BAT_NAME for n in names)
        if bat_in_zip:
            bat_updated = True

        print("  Распаковываем обновление...")
        new_sha = apply_zip(zip_path, BASE_DIR)

        if new_sha:
            save_local_sha(new_sha)
            print(f"  Новая версия: {new_sha[:12]}")
        else:
            save_local_sha(remote_sha)

        ensure_github_release()

    finally:
        try:
            os.remove(zip_path)
        except Exception:
            pass
        try:
            os.remove(lock_path)
        except Exception:
            pass

    run_sync_changelog()

    print()
    print(f"  Обновление завершено (ветка: {BRANCH}). База данных и файлы пользователей не тронуты.")

    if bat_updated:
        print()
        print(f"  Обнаружено обновление {BAT_NAME}.")
        print("  Для применения изменений запускового скрипта перезапустите сервер вручную.")


if __name__ == "__main__":
    if "--check" in sys.argv:
        sys.exit(check_for_updates())
    main()
