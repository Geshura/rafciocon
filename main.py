
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

DISCORD_WEBHOOK_URL = os.getenv(
    "DISCORD_WEBHOOK_URL",
    ""
).strip()

STEAM_PROFILE_URL = (
    f"https://steamcommunity.com/profiles/{STEAM_ID}/"
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


# ==========================================
# POBIERANIE STRONY
# ==========================================

def get_profile_page(url):
    try:
        response = requests.get(
            url,
            headers=HEADERS,
            timeout=TIMEOUT,
        )

        if response.status_code == 403:
            raise RuntimeError(
                "Steam odrzucił żądanie (HTTP 403)."
            )

        if response.status_code == 429:
            raise RuntimeError(
                "Steam ograniczył liczbę żądań (HTTP 429)."
            )

        response.raise_for_status()

        if "steamcommunity.com" not in response.url:
            raise RuntimeError(
                "Nieoczekiwane przekierowanie strony Steam."
            )

        return BeautifulSoup(
            response.text,
            "html.parser"
        )

    except requests.RequestException as exc:
        raise RuntimeError(
            f"Błąd pobierania profilu: {exc}"
        ) from exc


# ==========================================
# FUNKCJE POMOCNICZE
# ==========================================

def clean_text(element):
    if not element:
        return ""

    return " ".join(
        element.stripped_strings
    ).strip()


def extract_appid(element):
    if not element:
        return None

    for link in element.select("a[href]"):
        href = link.get("href", "")

        match = re.search(
            r"/app/(\d+)",
            href
        )

        if match:
            return match.group(1)

    return None


def extract_game_name(element):
    selectors = [
        ".game_name a",
        ".game_name",
        ".game_name a span",
        "a[href*='/app/']",
    ]

    for selector in selectors:
        node = element.select_one(selector)

        if node:
            name = clean_text(node)

            if name:
                return name

    return None


def extract_playtime(element):
    """
    Odczytuje łączny czas gry z informacji
    widocznych na profilu.
    """

    text = clean_text(element)

    patterns = [
        r"([\d,.]+)\s*hrs?\s*on\s*record",
        r"([\d,.]+)\s*hours?\s*on\s*record",
        r"([\d,.]+)\s*godz\.?\s*na\s*liczniku",
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


def extract_last_played(element):
    """
    Odczytuje datę ostatniego grania,
    jeśli Steam wyświetla ją na profilu.
    """

    text = clean_text(element)

    patterns = [
        r"last played on\s+(.+?)(?:$|\|)",
        r"ostatnio grano\s+(.+?)(?:$|\|)",
        r"ostatnio grana\s+(.+?)(?:$|\|)",
    ]

    for pattern in patterns:
        match = re.search(
            pattern,
            text,
            re.IGNORECASE
        )

        if match:
            return match.group(1).strip()

    # Alternatywne wyszukiwanie w osobnym elemencie
    selectors = [
        ".game_info_date",
        ".game_info_details",
    ]

    for selector in selectors:
        node = element.select_one(selector)

        if node:
            value = clean_text(node)

            if value:
                return value

    return None


# ==========================================
# ANALIZA OSTATNIEJ AKTYWNOŚCI
# ==========================================

def get_recent_activity(soup):

    # Wykrywanie profilu prywatnego
    page_text = soup.get_text(
        " ",
        strip=True
    ).lower()

    private_phrases = [
        "this profile is private",
        "this user's profile is private",
        "profil jest prywatny",
        "profil użytkownika jest prywatny",
    ]

    if any(
        phrase in page_text
        for phrase in private_phrases
    ):
        raise RuntimeError(
            "Profil Steam jest prywatny."
        )

    # Ogólny czas aktywności z ostatnich 14 dni
    recent_total = None

    activity_selectors = [
        ".recentgame_recentplaytime",
        ".profile_recentgame_header",
        ".recent_game_header",
    ]

    for selector in activity_selectors:
        node = soup.select_one(selector)

        if node:
            text = clean_text(node)

            match = re.search(
                r"([\d,.]+)\s*(?:hours?|hrs?|godz\.?)"
                r".{0,30}(?:past 2 weeks|last 2 weeks|"
                r"ostatnich 2 tygodni)",
                text,
                re.IGNORECASE,
            )

            if match:
                recent_total = match.group(1)
                break

    # Elementy poszczególnych gier
    game_blocks = soup.select(
        "#games_list_rows .gameListRow, "
        ".recent_game, "
        ".gameListRow"
    )

    games = []
    seen_appids = set()

    for block in game_blocks:

        name = extract_game_name(block)

        if not name:
            continue

        appid = extract_appid(block)

        if appid and appid in seen_appids:
            continue

        if appid:
            seen_appids.add(appid)

        games.append({
            "name": name,
            "appid": appid,
            "playtime": extract_playtime(block),
            "last_played": extract_last_played(block),
        })

        if len(games) >= MAX_GAMES:
            break

    # Jeżeli strona główna nie zwróciła gier,
    # sprawdzamy publiczną zakładkę ostatnio granych.
    if not games:
        return recent_total, []

    return recent_total, games


# ==========================================
# FORMATOWANIE DISCORD
# ==========================================

def create_discord_message():

    soup = get_profile_page(
        STEAM_PROFILE_URL
    )

    # Nazwa użytkownika
    profile_name = "Nieznany użytkownik"

    name_node = soup.select_one(
        ".actual_persona_name"
    )

    if name_node:
        profile_name = clean_text(name_node)

    recent_total, games = get_recent_activity(
        soup
    )

    lines = [
        f"🎮 **Steam – {profile_name}**",
        "",
        "📊 **OSTATNIA AKTYWNOŚĆ**",
    ]

    if recent_total:
        lines.append(
            f"⏱️ Łącznie w ostatnich 2 tygodniach: "
            f"**{recent_total} godz.**"
        )

    lines.extend([
        "",
        "🕹️ **OSTATNIO GRANE GRY**",
    ])

    if not games:
        lines.append(
            "⚠️ Nie znaleziono publicznej historii gier."
        )

    for index, game in enumerate(games, 1):

        name = game["name"]
        playtime = game["playtime"]
        last_played = game["last_played"]
        appid = game["appid"]

        lines.append(
            f"\n**{index}. {name}**"
        )

        if last_played:
            lines.append(
                f"📅 Ostatnio grano: {last_played}"
            )

        if playtime:
            lines.append(
                f"⏱️ Łącznie: {playtime} godz."
            )

        if appid:
            lines.append(
                f"🔗 https://store.steampowered.com/app/{appid}/"
            )

    lines.extend([
        "",
        f"🔗 [Profil Steam]({STEAM_PROFILE_URL})",
        "",
        "🤖 Dane pobrane bezpośrednio z profilu Steam.",
    ])

    message = "\n".join(lines)

    if len(message) > 2000:
        message = message[:1950] + "\n\n... (skrócono)"

    return message


# ==========================================
# WYSYŁANIE DISCORD WEBHOOK
# ==========================================

def send_discord_message(message):

    if not DISCORD_WEBHOOK_URL:
        raise RuntimeError(
            "Brak DISCORD_WEBHOOK_URL."
        )

    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={
            "content": message,
            "allowed_mentions": {
                "parse": []
            },
        },
        headers=HEADERS,
        timeout=TIMEOUT,
    )

    response.raise_for_status()


# ==========================================
# MAIN
# ==========================================

if __name__ == "__main__":

    try:
        print("Pobieranie profilu Steam...")

        message = create_discord_message()

        print(message)
        print("\nWysyłanie na Discord...")

        send_discord_message(message)

        print(
            "\n✅ Pomyślnie wysłano aktywność Steam!"
        )

    except Exception as exc:
        print(
            f"\n❌ BŁĄD: {exc}"
        )

        sys.exit(1)
