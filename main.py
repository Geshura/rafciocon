import json
import os
from typing import Any
from urllib import error, request
from urllib.parse import urlencode


class RequestException(Exception):
    pass


class Response:
    def __init__(self, response: Any, body: bytes) -> None:
        self.url = response.geturl()
        self.text = body.decode("utf-8", errors="replace")
        self.status_code = response.status

    def raise_for_status(self) -> None:
        if not 200 <= self.status_code < 300:
            raise RequestException(f"HTTP {self.status_code}")


def http_request(
    url: str,
    *,
    method: str = "GET",
    headers: dict[str, str] | None = None,
    cookies: dict[str, str] | None = None,
    json_data: dict[str, str] | None = None,
    timeout: int = 15,
) -> Response:
    request_headers = dict(headers or {})
    if cookies:
        request_headers["Cookie"] = "; ".join(
            f"{name}={value}" for name, value in cookies.items()
        )
    body = None
    if json_data is not None:
        body = json.dumps(json_data).encode("utf-8")
        request_headers["Content-Type"] = "application/json"

    try:
        with request.urlopen(
            request.Request(url, data=body, headers=request_headers, method=method),
            timeout=timeout,
        ) as response:
            return Response(response, response.read())
    except (error.HTTPError, error.URLError, TimeoutError) as exception:
        raise RequestException(str(exception)) from exception


STEAM_ID = os.getenv("STEAM_ID", "76561198034890618")
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
STEAM_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"


def format_playtime(minutes: int) -> str:
    hours, remaining_minutes = divmod(minutes, 60)
    if hours and remaining_minutes:
        return f"{hours} godz. {remaining_minutes} min"
    if hours:
        return f"{hours} godz."
    return f"{remaining_minutes} min"


def get_steam_status() -> str:
    if not STEAM_API_KEY:
        return "❌ Brak sekretu STEAM_API_KEY."

    try:
        response = http_request(
            f"{STEAM_GAMES_URL}?{urlencode({
                'key': STEAM_API_KEY,
                'steamid': STEAM_ID,
                'format': 'json',
                'include_appinfo': '1',
                'include_played_free_games': '1',
            })}",
            timeout=15,
        )
        response.raise_for_status()
    except RequestException as error:
        return f"⚠️ Nie udało się połączyć ze Steam: {error}"

    try:
        data = json.loads(response.text)
    except (json.JSONDecodeError, TypeError):
        return "⚠️ Steam zwrócił nieprawidłową odpowiedź API."

    if not isinstance(data, dict):
        return "⚠️ Steam zwrócił nieprawidłową odpowiedź API."

    steam_response = data.get("response")
    if not isinstance(steam_response, dict):
        return "⚠️ Steam zwrócił nieprawidłową odpowiedź API."

    games = steam_response.get("games")
    if not isinstance(games, list):
        return (
            "⚠️ Steam nie udostępnił listy gier. Sprawdź STEAM_API_KEY "
            "oraz ustaw widoczność profilu i gier na Publiczną."
        )

    if not games:
        return "💤 Brak gier zapisanych w bibliotece Steam."

    try:
        games_with_playtime = [
            game
            for game in games
            if int(game.get("playtime_forever", 0) or 0) > 0
        ]
    except (AttributeError, TypeError, ValueError):
        return "⚠️ Steam zwrócił nieprawidłowy czas gry."
    if not games_with_playtime:
        return "💤 Steam nie zwrócił czasu gry dla żadnej gry."

    try:
        games_with_playtime.sort(
            key=lambda game: int(game.get("rtime_last_played", 0) or 0),
            reverse=True,
        )
    except (AttributeError, TypeError, ValueError):
        return "⚠️ Steam zwrócił nieprawidłową datę ostatniego uruchomienia gry."
    last_game = games_with_playtime[0]
    game_name = last_game.get("name", "Nieznana gra")
    total_minutes = int(last_game.get("playtime_forever", 0) or 0)
    try:
        recent_minutes = int(last_game.get("playtime_2weeks", 0) or 0)
    except (TypeError, ValueError):
        return "⚠️ Steam zwrócił nieprawidłowy czas gry."

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
    response = http_request(
        DISCORD_WEBHOOK_URL,
        method="POST",
        json_data={"content": message},
        timeout=15,
    )
    response.raise_for_status()
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")
