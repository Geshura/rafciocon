import json
import os
import re
import sys
from typing import Optional

requests = __import__("requests")


# ============================================================
# KONFIGURACJA
# ============================================================

STEAM_ID = os.getenv("STEAM_ID", "76561198034890618").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/"

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
# POBIERANIE DANYCH Z PROFILU STEAM (JSON)
# ============================================================

def get_profile_data() -> tuple[str, list[dict]]:
    """
    Pobiera dane profilu oraz osadzone w kodzie strony JSON-y z grami,
    omijając problem braku statycznych elementów w HTML.
    """
    print(f"[STEAM] Pobieranie profilu: {PROFILE_URL}")
    response = session.get(PROFILE_URL, timeout=TIMEOUT)
    response.raise_for_status()
    html_text = response.text

    profile_name = "Użytkownik Steam"
    
    # Wyciąganie nazwy profilu
    match_name = re.search(r'<span class="actual_persona_name">(.*?)</span>', html_text)
    if match_name:
        profile_name = match_name.group(1).strip()

    games = []

    # Steam umieszcza dane gier w zmiennej JavaScript rgGames lub jako data-profile-json
    match_games = re.search(r"(?:var\s+)?rgGames\s*=\s*(\[.*?\])\s*;", html_text, re.DOTALL)
    
    if not match_games:
        # Alternatywne szukanie w strukturach JSON profilu
        match_json = re.search(r"data-profile-json=[\"']({.*?})[\"']", html_text, re.DOTALL)
        if match_json:
            try:
                profile_json = json.loads(match_json.group(1).replace("&quot;", '"'))
                raw_games = profile_json.get("rgGames", [])
                if isinstance(raw_games, list):
                    games = raw_games
            except Exception:
                pass
    else:
        try:
            games = json.loads(match_games.group(1))
        except Exception:
            pass

    parsed_games = []
    for g in games[:MAX_GAMES]:
        if not isinstance(g, dict):
            continue
        
        appid = str(g.get("appid", ""))
        name = g.get("name", "Nieznana gra")
        
        # Czas z ostatnich 2 tygodni (w minutach lub godzinach w zależności od struktury)
        hours_2weeks = g.get("hours_2weeks", g.get("playtime_2weeks", 0))
        if isinstance(hours_2weeks, (int, float)) and hours_2weeks > 100:  # Jeśli to minuty
            hours_2weeks = round(hours_2weeks / 60, 1)

        # Łączny czas
        hours_forever = g.get("hours_forever", g.get("playtime_forever", 0))
        if isinstance(hours_forever, (int, float)) and hours_forever > 1000:  # Jeśli to minuty
            hours_forever = round(hours_forever / 60, 1)

        parsed_games.append({
            "appid": appid,
            "name": name,
            "recent": str(hours_2weeks) if hours_2weeks else None,
            "total": str(hours_forever) if hours_forever else None,
        })

    return profile_name, parsed_games


# ============================================================
# WIADOMOŚĆ DISCORD
# ============================================================

def create_message() -> str:
    profile_name, games = get_profile_data()

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
            "⚠️ Nie udało się odczytać listy gier ze struktury profilu Steam.",
            "Upewnij się, że ustawienia prywatności szczegółów gier są publiczne.",
        ])
    else:
        for index, game in enumerate(games, start=1):
            lines.append(f"\n**{index}. {game['name']}**")

            if game.get("recent") is not None and float(game["recent"]) > 0:
                lines.append(
                    f"📅 Ostatnie 2 tygodnie: {game['recent']} godz."
                )

            if game.get("total") is not None:
                lines.append(
                    f"⏱️ Łącznie: {game['total']} godz."
                )

            if game.get("appid"):
                lines.append(
                    f"🔗 https://store.steampowered.com/app/{game['appid']}/"
                )

    lines.extend([
        "",
        f"🔗 [Profil Steam]({PROFILE_URL})",
        "",
        "🤖 Źródło: publiczny profil Steam.",
    ])

    message = "\n".join(lines)

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