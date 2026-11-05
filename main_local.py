import json
import os
import re
import sys
from pathlib import Path
from typing import Any
from urllib import error, request

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ============================================================
# KONFIGURACJA LOKALNA
# ============================================================

STEAM_ID = os.getenv("STEAM_ID", "76561198034890618").strip()
PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/"

# Ustaw zmienne środowiskowe zamiast wpisywać sekrety do kodu.
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
TARGET_GAME = os.getenv("TARGET_GAME", "").strip()
STEAM_BROWSER_PROFILE = os.getenv(
    "STEAM_BROWSER_PROFILE", ".steam-playwright-profile"
).strip()
if not os.path.isabs(STEAM_BROWSER_PROFILE):
    STEAM_BROWSER_PROFILE = str(Path(__file__).resolve().parent / STEAM_BROWSER_PROFILE)
STEAM_STORAGE_STATE = str(Path(STEAM_BROWSER_PROFILE).parent / "steam-storage-state.json")
STEAM_COOKIES_FILE = os.getenv("STEAM_COOKIES_FILE", "").strip()
STEAM_HEADLESS = os.getenv("STEAM_HEADLESS", "1").strip() != "0"

TIMEOUT = 20

# ============================================================
# POBIERANIE I PARSOWANIE HTML
# ============================================================

def load_steam_cookies(context: Any) -> None:
    if not STEAM_COOKIES_FILE:
        return

    try:
        with open(STEAM_COOKIES_FILE, encoding="utf-8") as cookies_file:
            cookie_data = json.load(cookies_file)
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(
            f"Nie można odczytać pliku cookies: {STEAM_COOKIES_FILE}"
        ) from exc

    cookies = (
        cookie_data.get("cookies")
        if isinstance(cookie_data, dict)
        else cookie_data
    )
    if not isinstance(cookies, list) or not cookies:
        raise RuntimeError(
            "Plik cookies musi zawierać listę cookies albo obiekt "
            "storage_state z polem 'cookies'."
        )

    steam_cookies = [
        cookie
        for cookie in cookies
        if isinstance(cookie, dict)
        and (
            "steamcommunity.com" in str(cookie.get("domain", ""))
            or "steampowered.com" in str(cookie.get("domain", ""))
        )
    ]
    if not steam_cookies:
        raise RuntimeError(
            "Plik cookies nie zawiera cookies dla steamcommunity.com "
            "ani steampowered.com."
        )

    context.add_cookies(steam_cookies)
    print(f" Wczytano {len(steam_cookies)} cookies Steam.")


def configure_page(page: Any) -> None:
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
    print(" Uruchamianie przeglądarki Chromium przez Playwright...")
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=STEAM_HEADLESS)
        context_options = {
            "locale": "pl-PL",
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/131.0.0.0 Safari/537.36"
            ),
        }
        if os.path.isfile(STEAM_STORAGE_STATE):
            context_options["storage_state"] = STEAM_STORAGE_STATE
        context = browser.new_context(**context_options)
        load_steam_cookies(context)
        page = context.pages[0] if context.pages else context.new_page()
        configure_page(page)
        try:
            print(f" Otwieranie profilu: {PROFILE_URL}")
            page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
            print(" Oczekiwanie na wykonanie skryptów JavaScript...")
            try:
                page.wait_for_load_state("networkidle", timeout=5000)
            except PlaywrightTimeoutError:
                page.wait_for_timeout(4000)

            page_content = page.content()
            logged_in = bool(
                re.search(r'logged_in(?:&quot;|")\s*:\s*(?:true)', page_content)
            )
            if not logged_in and not STEAM_HEADLESS:
                print(
                    " Zaloguj się w otwartym oknie Chromium, a następnie wróć tutaj."
                )
                input(" Naciśnij Enter po zakończeniu logowania...")
                open_pages = [candidate for candidate in context.pages if not candidate.is_closed()]
                page = open_pages[-1] if open_pages else context.new_page()
                configure_page(page)
                page.goto(PROFILE_URL, wait_until="domcontentloaded", timeout=TIMEOUT * 1000)
                page.wait_for_timeout(4000)
                page_content = page.content()
                logged_in = bool(
                    re.search(r'logged_in(?:&quot;|")\s*:\s*(?:true)', page_content)
                )
            if not logged_in:
                print(
                    " Profil jest otwarty bez sesji Steam; używane będą tylko dane publiczne."
                )
            else:
                context.storage_state(path=STEAM_STORAGE_STATE)
                print(" Zapisano sesję Steam: steam-storage-state.json")

            page_content = page.content()
            with open("steam_rendered_profile.html", "w", encoding="utf-8") as debug_file:
                debug_file.write(page_content)
            print(" Zapisano wyrenderowany HTML: steam_rendered_profile.html")

            if TARGET_GAME:
                if TARGET_GAME.casefold() in page_content.casefold():
                    print(f" Znaleziono szukaną grę: {TARGET_GAME}")
                else:
                    print(f" Nie znaleziono szukanej gry: {TARGET_GAME}")

            profile_name = (
                page.locator(".actual_persona_name").first.text_content() or "Profil Steam"
            ).strip()
            games = page.locator(".recent_game")
            if not games.count():
                return (
                    "⚠️ Steam nie wyświetlił ostatnio granych gier.\n"
                    "Upewnij się, że profil i **Szczegóły gry** są publiczne "
                    "oraz że gra była uruchomiona w ostatnich 2 tygodniach."
                )

            game = games.first
            game_name = (
                game.locator(".game_name").first.text_content() or "Nieznana gra"
            ).strip()
            game_details = game.locator(".game_info_details").first.inner_text()
            recent_summary = page.locator(".recentgame_recentplaytime").first.inner_text()
        finally:
            context.close()
            browser.close()

    total_match = re.search(r"([\d.,]+)\s*godz\.\s*łącznie", game_details)
    recent_match = re.search(r"([\d.,]+)\s*godz\.", recent_summary)
    hours_forever = total_match.group(1) if total_match else "?"
    hours_recent = recent_match.group(1) if recent_match else "?"

    message = (
        f"🎮 **Ostatnia gra na Steamie ({profile_name}):**\n"
        f"📌 **{game_name}**\n"
        f"⏱️ Łączny czas gry: **{hours_forever} godz.**"
    )
    if hours_recent != "?":
        message += f"\n📅 W ostatnich 2 tygodniach: **{hours_recent} godz.**"

    return message


# ============================================================
# WYSYŁANIE NA DISCORDA
# ============================================================

def send_to_discord(message: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "Brak zmiennej DISCORD_WEBHOOK_URL. Ustaw ją w środowisku przed uruchomieniem."
        )

    print(" Wysyłanie powiadomienia na Discorda...")
    data = json.dumps({"content": message}).encode("utf-8")
    req = request.Request(
        DISCORD_WEBHOOK_URL,
        data=data,
        headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"},
        method="POST"
    )
    try:
        with request.urlopen(req, timeout=TIMEOUT):
            print("✅ [OK] Wysłano pomyślnie na Discorda!")
    except error.HTTPError as exc:
        print(f"❌ [BŁĄD] Discord zwrócił kod {exc.code}")


# ============================================================
# GŁÓWNY PROGRAM
# ============================================================

if __name__ == "__main__":
    print("=" * 50)
    print(" LOKALNY SKRYPT HTML PARSER -> DISCORD")
    print("=" * 50)

    try:
        status_msg = get_latest_steam_activity()
        print("\n Treść wiadomości:")
        print("-" * 50)
        print(status_msg)
        print("-" * 50)

        if not status_msg.startswith("⚠️"):
            send_to_desktop = send_to_discord(status_msg)
    except Exception as exc:
        print(f"\n❌ [BŁĄD] {exc}")
        sys.exit(1)