
import os
import re
import sys
import requests

from bs4 import BeautifulSoup


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")


# ==========================================
# KONFIGURACJA
# ==========================================

STEAM_ID = os.getenv(
    "STEAM_ID",
    "76561198034890618"
).strip()

STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()

DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    ""
).strip()

PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/"

RECENT_URL = (
    f"https://steamcommunity.com/profiles/{STEAM_ID}/games/"
    "?tab=recent"
)

API_RECENT_URL = (
    "https://api.steampowered.com/"
    "IPlayerService/GetRecentlyPlayedGames/v1/"
)

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


# ==========================================
# POBIERANIE STRONY
# ==========================================

def fetch_page(url):
    response = session.get(
        url,
        timeout=TIMEOUT,
    )

    response.raise_for_status()

    return BeautifulSoup(
        response.text,
        "html.parser"
    ), response.url, response.text


# ==========================================
# FUNKCJE POMOCNICZE
# ==========================================

def clean_text(element):
    if not element:
        return ""

    return " ".join(
        element.stripped_strings
    ).strip()


def get_appid(href):
    if not href:
        return None

    match = re.search(
        r"/app/(\d+)",
        href
    )

    return match.group(1) if match else None


def get_game_name(element):
    # Nazwa z tekstu linku
    text = clean_text(element)

    if text and len(text) < 150:
        return text

    # Nazwa z grafiki
    image = element.select_one("img")

    if image:
        for attribute in ("alt", "title"):
            value = image.get(attribute, "").strip()

            if value:
                return value

    # Nazwa z atrybutu title
    title = element.get("title", "").strip()

    if title:
        return title

    return None


def extract_playtime(text):
    patterns = [
        r"([\d,.]+)\s*(?:hrs?|hours?)\s*on\s*record",
        r"([\d,.]+)\s*hours?",
        r"([\d,.]+)\s*hrs?",
        r"([\d,.]+)\s*godz\.?",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return None


def extract_recent_time(text):
    patterns = [
        r"([\d,.]+)\s*(?:hrs?|hours?)\s*"
        r"(?:past|in the past|last)\s*2\s*weeks",

        r"([\d,.]+)\s*hours?\s*"
        r"in the last 2 weeks",

        r"([\d,.]+)\s*godz\.?\s*"
        r"w ostatnich 2 tygodniach",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1)

    return None


# ==========================================
# ANALIZA ELEMENTU GRY
# ==========================================

def parse_game_block(block):

    appid = None

    for link in block.select("a[href]"):
        appid = get_appid(link.get("href"))

        if appid:
            break

    if not appid:
        return None

    name = None

    # Typowe elementy Steam
    selectors = [
        ".gameListRowItemName",
        ".game_name",
        ".game_name a",
        ".gameListRowItemName a",
    ]

    for selector in selectors:
        node = block.select_one(selector)

        if node:
            name = clean_text(node)

            if name:
                break

    # Szukanie nazwy w linkach
    if not name:
        for link in block.select("a[href]"):
            if get_appid(link.get("href")) == appid:
                name = get_game_name(link)
                if name:
                    break

    # Szukanie nazwy w obrazkach
    if not name:
        image = block.select_one("img")

        if image:
            name = (
                image.get("alt")
                or image.get("title")
            )

    if not name:
        return None

    text = clean_text(block)

    return {
        "appid": appid,
        "name": name.strip(),
        "total": extract_playtime(text),
        "recent": extract_recent_time(text),
        "last_played": None,
    }


# ==========================================
# ODCZYT GRY Z HTML
# ==========================================

def parse_games_page(soup):

    games = []
    seen = set()

    # Najpierw konkretne wiersze biblioteki Steam
    selectors = [
        ".gameListRow",
        "#games_list_rows .gameListRow",
        ".recent_game",
        ".recentgame",
    ]

    blocks = []

    for selector in selectors:
        blocks.extend(
            soup.select(selector)
        )

    for block in blocks:

        game = parse_game_block(block)

        if not game:
            continue

        if game["appid"] in seen:
            continue

        seen.add(game["appid"])
        games.append(game)

    # Druga metoda: szukanie linków do gier
    if not games:

        for link in soup.select("a[href*='/app/']"):

            appid = get_appid(
                link.get("href")
            )

            if not appid or appid in seen:
                continue

            name = get_game_name(link)

            if not name:
                continue

            parent = link.parent

            for _ in range(3):
                if parent and parent.parent:
                    parent = parent.parent

            text = clean_text(parent)

            games.append({
                "appid": appid,
                "name": name,
                "total": extract_playtime(text),
                "recent": extract_recent_time(text),
                "last_played": None,
            })

            seen.add(appid)

    return games


# ==========================================
# STEAM API - FALLBACK
# ==========================================

def get_games_from_api():

    if not STEAM_API_KEY:
        return []

    try:
        response = session.get(
            API_RECENT_URL,
            params={
                "key": STEAM_API_KEY,
                "steamid": STEAM_ID,
                "count": MAX_GAMES,
            },
            timeout=TIMEOUT,
        )

        response.raise_for_status()

        data = response.json()

        games = data.get(
            "response", {}
        ).get("games", [])

        result = []

        for game in games:
            appid = str(game.get("appid", "")).strip()
            name = str(game.get("name", "")).strip()

            if not appid or not name:
                continue

            recent_minutes = game.get("playtime_2weeks", 0)

            result.append({
                "appid": appid,
                "name": name,
                "total": None,
                "recent": str(
                    round(
                        int(recent_minutes) / 60,
                        1
                    )
                ),
                "last_played": None,
            })

        return result

    except (
        requests.RequestException,
        ValueError,
        TypeError,
    ) as exc:

        print(f"[API] Nie udało się pobrać gier: {exc}")

        return []


# ==========================================
# DIAGNOSTYKA
# ==========================================

def save_debug(html, url):

    with open(
        "steam_debug.html",
        "w",
        encoding="utf-8"
    ) as file:

        file.write(
            f"<!-- URL: {url} -->\n"
        )

        file.write(html)

    print(
        "[DEBUG] Zapisano odpowiedź Steam do steam_debug.html"
    )


# ==========================================
# POBIERANIE OSTATNIEJ AKTYWNOŚCI
# ==========================================

def get_recent_activity():

    # Web API nie zależy od zmiennego HTML-a profilu Steam.
    if STEAM_API_KEY:
        print("[STEAM] Pobieranie danych z Web API...")
        api_games = get_games_from_api()

        if api_games:
            return api_games[:MAX_GAMES]

        print("[STEAM] Web API nie zwróciło gier, używam HTML jako fallbacku.")

    all_games = []
    seen = set()
    debug_html = ""
    debug_url = PROFILE_URL

    urls = [
        PROFILE_URL,
        RECENT_URL,
    ]

    for url in urls:

        print(f"[STEAM] Pobieranie: {url}")

        try:
            soup, final_url, html = fetch_page(url)

            debug_html = html
            debug_url = final_url

            print(
                f"[STEAM] HTTP OK: {final_url}"
            )

            title = clean_text(
                soup.select_one("title")
            )

            print(
                f"[STEAM] Tytuł strony: {title}"
            )

            games = parse_games_page(soup)

            print(
                f"[STEAM] Znaleziono gier: {len(games)}"
            )

            for game in games:

                if game["appid"] in seen:
                    continue

                seen.add(game["appid"])
                all_games.append(game)

        except requests.RequestException as exc:

            print(
                f"[STEAM] Błąd pobierania: {exc}"
            )

    if not all_games and debug_html:

        save_debug(
            debug_html,
            debug_url
        )

    return all_games


# ==========================================
# NAZWA PROFILU
# ==========================================

def get_profile_name(soup):

    selectors = [
        ".actual_persona_name",
        ".profile_header_name",
    ]

    for selector in selectors:

        node = soup.select_one(selector)

        if node:
            return clean_text(node)

    return "Użytkownik Steam"


# ==========================================
# TWORZENIE WIADOMOŚCI
# ==========================================

def create_message():

    try:
        soup, _, _ = fetch_page(PROFILE_URL)

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Nie można pobrać profilu: {exc}"
        ) from exc

    profile_name = get_profile_name(soup)

    games = get_recent_activity()

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
            "⚠️ Nie znaleziono publicznej historii gier.",
            "",
            "Możliwe przyczyny:",
            "• Prywatne szczegóły gier.",
            "• Brak ostatnio granych gier.",
            "• Steam nie zwrócił sekcji gier w HTML.",
            "• Strona wymaga dodatkowej weryfikacji.",
        ])

    else:

        for index, game in enumerate(
            games[:MAX_GAMES],
            1
        ):

            lines.append(
                f"\n**{index}. {game['name']}**"
            )

            if game.get("recent") is not None:
                lines.append(
                    f"📅 Ostatnie 2 tygodnie: "
                    f"{game['recent']} godz."
                )

            if game.get("total") is not None:
                lines.append(
                    f"⏱️ Łącznie: {game['total']} godz."
                )

            if game.get("appid"):
                lines.append(
                    f"🔗 https://store.steampowered.com/app/"
                    f"{game['appid']}/"
                )

    lines.extend([
        "",
        f"🔗 [Profil Steam]({PROFILE_URL})",
        "",
        "🤖 Źródło: publiczny profil Steam / Steam Web API.",
    ])

    return "\n".join(lines)[:2000]


# ==========================================
# DISCORD
# ==========================================

def send_discord(message):

    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "Brak DISCORD_WEBHOOK_URL."
        )

    response = session.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": message,
            "allowed_mentions": {
                "parse": []
            },
        },
        timeout=TIMEOUT,
    )

    response.raise_for_status()


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    try:

        print("=" * 45)
        print("STEAM PROFILE MONITOR")
        print("=" * 45)

        message = create_message()

        print("\nWIADOMOŚĆ:")
        print("-" * 45)
        print(message)
        print("-" * 45)

        send_discord(message)

        print("\n[OK] Wysłano wiadomość na Discord.")

    except Exception as exc:

        print(f"\n[BŁĄD] {exc}")
        sys.exit(1)
