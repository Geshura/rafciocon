import json
import os
import re
import sys
from pathlib import Path
from urllib import error, request

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

STEAM_ID = os.getenv("STEAM_ID", "76561198034890618").strip()
PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
STEAM_STORAGE_STATE = os.getenv("STEAM_STORAGE_STATE", "steam-storage-state.json")
TARGET_GAME = os.getenv("TARGET_GAME", "").strip()
TIMEOUT = 30


def configure_page(page: object) -> None:
    page.set_extra_http_headers(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
            "Accept-Language": "pl-PL,pl;q=0.9",
        }
    )


def get_latest_steam_activity() -> dict[str, str]:
    storage_state = Path(STEAM_STORAGE_STATE)
    if not storage_state.is_file():
        raise RuntimeError(
            f"Brak pliku sesji Steam: {storage_state}. "
            "Utwórz storage_state.json i dodaj go jako sekret GitHub."
        )

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True)
        context = browser.new_context(
            storage_state=str(storage_state),
            locale="pl-PL",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()
        configure_page(page)
        try:
            print(f"[STEAM] Otwieranie profilu: {PROFILE_URL}")
            page.goto(
                PROFILE_URL,
                wait_until="domcontentloaded",
                timeout=TIMEOUT * 1000,
            )
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                page.wait_for_timeout(4000)

            page_content = page.content()
            Path("steam_rendered_profile.html").write_text(
                page_content, encoding="utf-8"
            )
            logged_in = bool(
                re.search(r'logged_in(?:&quot;|")\s*:\s*(?:true)', page_content)
            )
            if not logged_in:
                raise RuntimeError(
                    "Sesja Steam wygasła albo storage_state.json jest nieprawidłowy."
                )

            if TARGET_GAME:
                result = (
                    "Znaleziono"
                    if TARGET_GAME.casefold() in page_content.casefold()
                    else "Nie znaleziono"
                )
                print(f"[STEAM] {result}: {TARGET_GAME}")

            profile_name = (
                page.locator(".actual_persona_name").first.text_content()
                or "Profil Steam"
            ).strip()
            games = page.locator(".recent_game")
            if not games.count():
                return (
                    {"warning": (
                        "Steam nie wyświetlił ostatnio granych gier.\n"
                        "Sprawdź prywatność profilu i aktywność z ostatnich 2 tygodni."
                    )}
                )

            game = games.first
            game_name = (
                game.locator(".game_name").first.text_content()
                or "Nieznana gra"
            ).strip()
            game_image = (
                game.locator("img.game_capsule").first.get_attribute("src")
                or ""
            ).strip()
            app_id_match = re.search(r"/apps/(\d+)/", game_image)
            if app_id_match:
                game_image = (
                    "https://cdn.cloudflare.steamstatic.com/steam/apps/"
                    f"{app_id_match.group(1)}/header.jpg"
                )
            game_details = game.locator(".game_info_details").first.inner_text()
            recent_summary = page.locator(
                ".recentgame_recentplaytime"
            ).first.inner_text()
        finally:
            context.close()
            browser.close()

    total_match = re.search(r"([\d.,]+)\s*godz\.\s*łącznie", game_details)
    last_played_match = re.search(
        r"Ostatnia gra:\s*([^\r\n]+)", game_details
    )
    recent_match = re.search(r"([\d.,]+)\s*godz\.", recent_summary)
    total = total_match.group(1) if total_match else "?"
    last_played = (
        last_played_match.group(1).strip()
        if last_played_match
        else "?"
    )
    recent = recent_match.group(1) if recent_match else "?"

    return {
        "profile_name": profile_name,
        "game_name": game_name,
        "game_image": game_image,
        "total": total,
        "last_played": last_played,
        "recent": recent,
    }


def send_to_discord(activity: dict[str, str]) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("Brak zmiennej DISCORD_WEBHOOK_URL.")

    if "warning" in activity:
        payload_data = {
            "content": f"⚠️ {activity['warning']}",
            "allowed_mentions": {"parse": []},
        }
    else:
        recent = activity.get("recent", "?")
        fields = [
            {
                "name": "🎮 Ostatnia gra",
                "value": f"**{activity['game_name']}**",
            },
            {
                "name": "⏱️ Czas gry (ogólnie)",
                "value": f"**{activity['total']} godz.**",
            },
        ]
        if activity.get("last_played", "?") != "?":
            fields.append(
                {
                    "name": "🗓️ Ostatnio uruchomiona",
                    "value": f"**{activity['last_played']}**",
                    "inline": True,
                }
            )
        if recent != "?":
            fields.append(
                {
                    "name": "📅 Czas gry (ostatnie 2 tygodnie)",
                    "value": f"**{recent} godz.**",
                    "inline": True,
                }
            )
    embed = {
        "title": "RAFCION",
        "description": f"**{activity['profile_name']}** uruchomił ostatnio:",
        "url": PROFILE_URL,
        "color": 34303,
        "fields": fields,
        "footer": {
            "text": "RAFCIOCON",
            "icon_url": "https://i.imgur.com/cblxnZz.png",
        },
    }
    if activity.get("game_image"):
        embed["image"] = {"url": activity["game_image"]}
    embed["thumbnail"] = {"url": "https://i.imgur.com/cblxnZz.png"}
    payload_data = {
        "content": None,
        "embeds": [embed],
        "allowed_mentions": {"parse": []},
        "attachments": [],
    }

    payload = json.dumps(
        payload_data
    ).encode("utf-8")
    req = request.Request(
        DISCORD_WEBHOOK_URL,
        data=payload,
        headers={"Content-Type": "application/json", "User-Agent": "rafciocon"},
        method="POST",
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT):
            print("[OK] Wysłano wiadomość na Discord.")
    except error.HTTPError as exc:
        raise RuntimeError(f"Discord zwrócił kod HTTP {exc.code}.") from exc


if __name__ == "__main__":
    try:
        if not STEAM_ID:
            raise RuntimeError("Brak STEAM_ID.")
        activity = get_latest_steam_activity()
        if "warning" in activity:
            print(f"⚠️ {activity['warning']}")
        else:
            print(
                f"🎮 {activity['game_name']} | "
                f"{activity['total']} godz. łącznie"
            )
            send_to_discord(activity)
    except Exception as exc:
        print(f"[BŁĄD] {exc}")
        sys.exit(1)
