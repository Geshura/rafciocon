import os
from typing import Any

import requests


STEAM_API_URL = "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"
STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_ID = os.getenv("STEAM_ID")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")


def format_playtime(minutes: int) -> str:
    """Convert Steam's playtime in minutes to a readable value."""
    hours, remaining_minutes = divmod(minutes, 60)
    if hours and remaining_minutes:
        return f"{hours} godz. {remaining_minutes} min"
    if hours:
        return f"{hours} godz."
    return f"{remaining_minutes} min"


def get_steam_status() -> str:
    if not STEAM_API_KEY:
        return "❌ Brak sekretu STEAM_API_KEY."
    if not STEAM_ID:
        return "❌ Brak zmiennej STEAM_ID z identyfikatorem użytkownika Steam."

    try:
        response = requests.get(
            STEAM_API_URL,
            params={
                "key": STEAM_API_KEY,
                "steamid": STEAM_ID,
                "format": "json",
            },
            timeout=15,
        )
        response.raise_for_status()
        payload: dict[str, Any] = response.json()
    except requests.RequestException as error:
        return f"⚠️ Nie udało się połączyć z Steam Web API: {error}"
    except ValueError:
        return "⚠️ Steam Web API zwróciło nieprawidłową odpowiedź JSON."

    steam_response = payload.get("response")
    if not isinstance(steam_response, dict):
        return "⚠️ Steam Web API zwróciło nieprawidłową strukturę odpowiedzi."

    games = steam_response.get("games", [])
    if not isinstance(games, list):
        return "⚠️ Steam Web API zwróciło nieprawidłową listę gier."
    if not games:
        return "💤 Brak publicznej historii ostatnio uruchamianych gier."

    last_game = games[0]
    if not isinstance(last_game, dict):
        return "⚠️ Steam Web API zwróciło nieprawidłowe dane gry."

    game_name = last_game.get("name", "Nieznana gra")
    try:
        total_minutes = int(last_game.get("playtime_forever", 0))
        recent_minutes = int(last_game.get("playtime_2weeks", 0))
    except (TypeError, ValueError):
        return "⚠️ Steam Web API zwróciło nieprawidłowy czas gry."

    return (
        "🎮 **Ostatnia gra na Steamie:**\n"
        f"📌 **{game_name}**\n"
        f"⏱️ Łączny czas gry: **{format_playtime(total_minutes)}**\n"
        f"📅 W ostatnich 2 tygodniach: **{format_playtime(recent_minutes)}**"
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
