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
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "https://discord.com/api/webhooks/1567676263769051196/JAlTVOPxQwfoJhtu5MknY9pT55iUAkO6xLRKbzIqF1R8ByatlA6DXx0Bk4pqGM_CRk6p").strip()
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


def get_latest_steam_activity() -> str:
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
                    "⚠️ Steam nie wyświetlił ostatnio granych gier.\n"
                    "Sprawdź prywatność profilu i aktywność z ostatnich 2 tygodni."
                )

            game = games.first
            game_name = (
                game.locator(".game_name").first.text_content()
                or "Nieznana gra"
            ).strip()
            game_details = game.locator(".game_info_details").first.inner_text()
            recent_summary = page.locator(
                ".recentgame_recentplaytime"
            ).first.inner_text()
        finally:
            context.close()
            browser.close()

    total_match = re.search(r"([\d.,]+)\s*godz\.\s*łącznie", game_details)
    recent_match = re.search(r"([\d.,]+)\s*godz\.", recent_summary)
    total = total_match.group(1) if total_match else "?"
    recent = recent_match.group(1) if recent_match else "?"

    message = (
        f"🎮 **Ostatnia gra na Steamie ({profile_name}):**\n"
        f"📌 **{game_name}**\n"
        f"⏱️ Łącznie: **{total} godz.**"
    )
    if recent != "?":
        message += f"\n📅 Ostatnie 2 tygodnie: **{recent} godz.**"
    return message


def send_to_discord(message: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("Brak zmiennej DISCORD_WEBHOOK_URL.")

    payload = json.dumps(
        {"content": message, "allowed_mentions": {"parse": []}}
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
        message = get_latest_steam_activity()
        print(message)
        if not message.startswith("⚠️"):
            send_to_discord(message)
    except Exception as exc:
        print(f"[BŁĄD] {exc}")
        sys.exit(1)
