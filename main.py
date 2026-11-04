import html
import json
import os
import re
from typing import Any

import requests


STEAM_ID = os.getenv("STEAM_ID", "76561198034890618")
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
STEAM_PROFILE_URL = f"https://steamcommunity.com/profiles/{STEAM_ID}/games/?tab=all"


def format_playtime(minutes: int) -> str:
    hours, remaining_minutes = divmod(minutes, 60)
    if hours and remaining_minutes:
        return f"{hours} godz. {remaining_minutes} min"
    if hours:
        return f"{hours} godz."
    return f"{remaining_minutes} min"


def get_steam_status() -> str:
    if not STEAM_LOGIN_SECURE:
        return "❌ Brak sekretu STEAM_LOGIN_SECURE."

    try:
        response = requests.get(
            STEAM_PROFILE_URL,
            cookies={"steamLoginSecure": STEAM_LOGIN_SECURE},
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=15,
        )
        response.raise_for_status()
    except requests.RequestException as error:
        return f"⚠️ Nie udało się połączyć ze Steam: {error}"

    if "login" in response.url.lower():
        return "❌ Sekret STEAM_LOGIN_SECURE wygasł lub jest nieprawidłowy."

    match = re.search(r"var rgGames = (\[.*?\]);", response.text, re.DOTALL)
    if not match:
        return "💤 Steam nie udostępnił listy gier. Sprawdź widoczność biblioteki profilu."

    try:
        games: list[dict[str, Any]] = json.loads(html.unescape(match.group(1)))
    except (json.JSONDecodeError, TypeError):
        return "⚠️ Nie udało się odczytać danych gier ze strony Steam."

    if not games:
        return "💤 Brak gier zapisanych w bibliotece Steam."

    games_with_playtime = [
        game for game in games if int(game.get("hours_forever", 0) or 0) > 0
    ]
    if not games_with_playtime:
        return "💤 Steam nie zwrócił czasu gry dla żadnej gry."

    last_game = games_with_playtime[0]
    game_name = last_game.get("name", "Nieznana gra")
    total_hours = int(last_game.get("hours_forever", 0) or 0)
    recent_hours = int(last_game.get("hours_2weeks", 0) or 0)

    return (
        "🎮 **Ostatnia gra na Steamie:**\n"
        f"📌 **{game_name}**\n"
        f"⏱️ Łączny czas gry: **{format_playtime(total_hours * 60)}**\n"
        f"📅 W ostatnich 2 tygodniach: **{format_playtime(recent_hours * 60)}**"
    )


if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak sekretu DISCORD_WEBHOOK_URL.")
        raise SystemExit(1)

    message = get_steam_status()
    response = requests.post(
        DISCORD_WEBHOOK_URL,
        json={"content": message},
        timeout=15,
    )
    response.raise_for_status()
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")
