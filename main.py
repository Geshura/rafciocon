import os
import re
import sys
from typing import Optional

import requests
from bs4 import BeautifulSoup, Tag


# ============================================================
# KONFIGURACJA
# ============================================================

STEAM_ID = os.getenv("STEAM_ID", "76561198034890618").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/"
RECENT_URL = f"{PROFILE_URL}games/?tab=recent"

MAX_GAMES = 5
TIMEOUT = 20

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9,pl;q=0.8",
}

session = requests.Session()
session.headers.update(HEADERS)


# ============================================================
# HTTP
# ============================================================

def fetch_page(url: str) -> tuple[BeautifulSoup, str]:
    response = session.get(url, timeout=TIMEOUT)
    response.raise_for_status()

    # Zwracamy HTML dokładnie tej strony, którą pobraliśmy.
    soup = BeautifulSoup(response.text, "html.parser")
    return soup, response.text


# ============================================================
# PARSOWANIE
# ============================================================

def clean_text(element: Optional[Tag]) -> str:
    if element is None:
        return ""
    return " ".join(element.stripped_strings).strip()


def get_appid_from_url(url: str) -> Optional[str]:
    match = re.search(r"/app/(\d+)", url or "")
    return match.group(1) if match else None


def find_appid(block: Tag) -> Optional[str]:
    for link in block.select("a[href]"):
        appid = get_appid_from_url(link.get("href", ""))
        if appid:
            return appid
    return None


def find_game_name(block: Tag) -> Optional[str]:
    # Typowe nazwy w wierszach listy gier Steam.
    selectors = (
        ".gameListRowItemName",
        ".game_name",
        ".game_name a",
        ".recent_game_name",
        ".recentgame_name",
        "a[href*='/app/']",
    )

    for selector in selectors:
        node = block.select_one(selector)
        if node:
            # Jeśli to link z obrazkiem, preferuj tekst/alt, nie pusty tekst.
            name = clean_text(node)
            if name:
                return name

            image = node.select_one("img")
            if image:
                name = (
                    image.get("alt", "").strip()
                    or image.get("title", "").strip()
                )
                if name:
                    return name

    image = block.select_one("img")
    if image:
        name = (
            image.get("alt", "").strip()
            or image.get("title", "").strip()
        )
        if name:
            return name

    return None


def find_hours(block: Tag, kind: str) -> Optional[str]:
    """
    kind='recent' - czas z ostatnich dwóch tygodni
    kind='total'  - łączny czas na liczniku

    Odczytujemy osobne elementy, jeśli istnieją, a potem tekst wiersza.
    """
    selectors = {
        "recent": (
            ".gameListRowItemHours",
            ".game_info_details",
            ".recentgame_recentplaytime",
            ".gameListRowItemRecentPlaytime",
        ),
        "total": (
            ".gameListRowItemHours",
            ".game_info_details",
            ".gameListRowItemPlaytime",
        ),
    }

    for selector in selectors[kind]:
        for node in block.select(selector):
            text = clean_text(node)
            value = parse_hours_from_text(text, kind)
            if value is not None:
                return value

    return parse_hours_from_text(clean_text(block), kind)


def parse_hours_from_text(text: str, kind: str) -> Optional[str]:
    text = text.replace(",", ".")

    if kind == "recent":
        patterns = (
            r"([\d.]+)\s*(?:hrs?|hours?)\s*(?:in\s*)?"
            r"(?:the\s*)?(?:past|last)\s*2\s*weeks",
            r"([\d.]+)\s*(?:hrs?|hours?)\s*last\s*two\s*weeks",
            r"([\d.]+)\s*(?:godz\.?|godziny|godzin)\s*"
            r"(?:w\s*)?(?:ostatnich\s*)?2\s*tygodniach",
        )
    else:
        patterns = (
            r"([\d.]+)\s*(?:hrs?|hours?)\s*on\s*record",
            r"([\d.]+)\s*(?:hrs?|hours?)\s*total",
            r"([\d.]+)\s*(?:godz\.?|godziny|godzin)\s*łącznie",
        )

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1)

    return None


def parse_game_rows(soup: BeautifulSoup) -> list[dict]:
    """
    Parsuje wiersze gier w kolejności DOM.
    Celowo NIE sortuje ich po czasie gry ani AppID.
    """
    games = []
    seen_appids = set()

    # Na stronie /games/?tab=recent Steam zwykle renderuje wiersze
    # listy gier jako .gameListRow.
    selectors = (
        "#games_list_rows .gameListRow",
        ".gameListRow",
        ".recent_game",
        ".recentgame",
    )

    rows = []
    for selector in selectors:
        found = soup.select(selector)
        if found:
            rows = found
            break

    for row in rows:
        appid = find_appid(row)
        name = find_game_name(row)

        if not appid or not name or appid in seen_appids:
            continue

        seen_appids.add(appid)

        games.append({
            "appid": appid,
            "name": name,
            "recent": find_hours(row, "recent"),
            "total": find_hours(row, "total"),
        })

    return games


# ============================================================
# OSTATNIA AKTYWNOŚĆ
# ============================================================

def get_profile_name(soup: BeautifulSoup) -> str:
    for selector in (".actual_persona_name", ".profile_header_name"):
        node = soup.select_one(selector)
        if node:
            name = clean_text(node)
            if name:
                return name
    return "Użytkownik Steam"


def get_recent_activity() -> tuple[str, list[dict]]:
    """
    Najpierw czytamy wyłącznie zakładkę Recent.
    Nie używamy GetRecentlyPlayedGames jako fallbacku, bo API może
    sortować wynik według czasu gry z 14 dni, a nie kolejności profilu.
    """
    print(f"[STEAM] Pobieranie zakładki Recent: {RECENT_URL}")

    soup, html = fetch_page(RECENT_URL)
    games = parse_game_rows(soup)

    if games:
        print(
            f"[STEAM] Znaleziono {len(games)} gier "
            "(kolejność HTML, bez sortowania)."
        )
        return html, games[:MAX_GAMES]

    # Fallback tylko do sekcji ostatniej aktywności na profilu.
    # Nie łączymy wyników obu stron, aby nie zmieniać kolejności.
    print("[STEAM] Nie znaleziono wierszy na zakładce Recent.")
    print("[STEAM] Sprawdzam sekcję ostatniej aktywności profilu.")

    profile_soup, profile_html = fetch_page(PROFILE_URL)
    games = parse_game_rows(profile_soup)

    if games:
        print(
            f"[STEAM] Znaleziono {len(games)} gier na profilu "
            "(kolejność HTML, bez sortowania)."
        )
        return profile_html, games[:MAX_GAMES]

    # Zapis diagnostyczny do sprawdzenia rzeczywistej odpowiedzi Steam.
    with open("steam_debug.html", "w", encoding="utf-8") as file:
        file.write(html)

    print("[DEBUG] Zapisano HTML do steam_debug.html.")
    return html, []


# ============================================================
# WIADOMOŚĆ DISCORD
# ============================================================

def create_message() -> str:
    profile_soup, _ = fetch_page(PROFILE_URL)
    profile_name = get_profile_name(profile_soup)

    _, games = get_recent_activity()

    lines = [
        f"🎮 **Steam – {profile_name}**",
        "",
        "📊 **OSTATNIA AKTYWNOŚĆ**",
        "",
        "🕹️ **OSTATNIO GRANE GRY**",
    ]

    if not games:
        lines.extend([
            "",
            "⚠️ Nie udało się odczytać listy gier z HTML Steam.",
            "Sprawdź plik steam_debug.html oraz ustawienia "
            "prywatności szczegółów gier.",
        ])
    else:
        for index, game in enumerate(games, start=1):
            lines.append(f"\n**{index}. {game['name']}**")

            if game.get("recent") is not None:
                lines.append(
                    f"📅 Ostatnie 2 tygodnie: {game['recent']} godz."
                )

            if game.get("total") is not None:
                lines.append(
                    f"⏱️ Łącznie: {game['total']} godz."
                )

            lines.append(
                f"🔗 https://store.steampowered.com/app/{game['appid']}/"
            )

    lines.extend([
        "",
        f"🔗 [Profil Steam]({PROFILE_URL})",
        "",
        "🤖 Źródło: zakładka Recent na publicznym profilu Steam.",
    ])

    message = "\n".join(lines)

    # Limit Discorda dla zwykłej wiadomości.
    if len(message) > 1900:
        message = message[:1890] + "\n…"

    return message


def send_discord(message: str) -> None:
    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError("Brak zmiennej DISCORD_WEBHOOK_URL.")

    response = session.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=TIMEOUT,
    )
    response.raise_for_status()


# ============================================================
# MAIN
# ============================================================

if __name__ == "__main__":
    try:
        if not STEAM_ID:
            raise RuntimeError("Brak STEAM_ID.")

        print("=" * 50)
        print("STEAM PROFILE MONITOR")
        print("=" * 50)

        message = create_message()

        print("\nWIADOMOŚĆ:")
        print("-" * 50)
        print(message)
        print("-" * 50)

        send_discord(message)
        print("\n[OK] Wysłano wiadomość na Discord.")

    except (requests.RequestException, RuntimeError) as exc:
        print(f"\n[BŁĄD] {exc}")
        sys.exit(1)
    except Exception as exc:
        print(f"\n[NIEOCZEKIWANY BŁĄD] {exc}")
        sys.exit(1)
