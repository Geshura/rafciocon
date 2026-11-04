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
    except error.HTTPError as exception:
        details = exception.read().decode("utf-8", errors="replace").strip()
        message = f"HTTP {exception.code}"
        if details:
            message = f"{message}: {details[:300]}"
        raise RequestException(message) from exception
    except (error.URLError, TimeoutError) as exception:
        raise RequestException(str(exception)) from exception


STEAM_ID = "76561198034890618"
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
STEAM_RECENT_GAMES_URL = (
    "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"
)
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
        return "❌ Brak sekretu STEAM_API_KEY w środowisku."

    query = urlencode(
        {
            "key": STEAM_API_KEY,
            "steamid": STEAM_ID,
            "format": "json",
            "include_appinfo": "1",
            "include_played_free_games": "1",
        }
    )

    recent_games = []
    owned_games = []

    try:
        response = http_request(f"{STEAM_RECENT_GAMES_URL}?{query}", timeout=15)
        response.raise_for_status()
        data = json.loads(response.text)
        if isinstance(data, dict):
            recent_games = data.get("response", {}).get("games", []) or []
    except (RequestException, json.JSONDecodeError, TypeError):
        pass

    try:
        response = http_request(f"{STEAM_GAMES_URL}?{query}", timeout=15)
        response.raise_for_status()
        data = json.loads(response.text)
        if isinstance(data, dict):
            owned_games = data.get("response", {}).get("games", []) or []
    except (RequestException, json.JSONDecodeError, TypeError):
        pass

    if not recent_games and not owned_games:
        return (
            "⚠️ Nie udało się pobrać gier z API Steama. "
            "Upewnij się, że Twój profil i szczegóły gier są publiczne."
        )

    owned_by_appid = {game.get("appid"): game for game in owned_games if game.get("appid") is not None}

    # Wymuszenie poprawnej kolejności gier z ostatnich 2 tygodni (najwięcej czasu / najświeższe na górze)
    if recent_games:
        recent_games.sort(
            key=lambda g: int(g.get("playtime_2weeks", 0) or 0),
            reverse=True
        )
        last_game = recent_games[0]
    elif owned_games:
        games_with_playtime = [g for g in owned_games if int(g.get("playtime_forever", 0) or 0) > 0]
        if games_with_playtime:
            last_game = games_with_playtime[0]
        else:
            return "💤 Brak aktywności w grach."
    else:
        return "💤 Brak informacji o grach."

    app_id = last_game.get("appid")
    matched_owned = owned_by_appid.get(app_id, {})

    game_name = str(last_game.get("name", "Nieznana gra"))
    total_minutes = int(
        matched_owned.get("playtime_forever")
        or last_game.get("playtime_forever")
        or 0
    )
    recent_minutes = int(
        last_game.get("playtime_2weeks")
        or matched_owned.get("playtime_2weeks")
        or 0
    )

    if total_minutes <= 0:
        return "⚠️ Steam nie zwrócił łącznego czasu dla ostatniej gry."

    return (
        "🎮 **Ostatnia gra na Steamie (`geshurapl`):**\n"
        f"📌 **{game_name}**\n"
        f"⏱️ Łączny czas gry: **{format_playtime(total_minutes)}**\n"
        f"📅 W ostatnich 2 tygodniach: **{format_playtime(recent_minutes)}**"
    )


if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak sekretu DISCORD_WEBHOOK_URL.")
        raise SystemExit(1)

    message = get_steam_status()
    try:
        response = http_request(
            DISCORD_WEBHOOK_URL,
            method="POST",
            headers={
                "Accept": "application/json",
                "User-Agent": "rafciocon/1.0",
            },
            json_data={"content": message},
            timeout=15,
        )
        response.raise_for_status()
    except RequestException as error:
        print(
            "Błąd wysyłania wiadomości na Discorda. "
            "Sprawdź, czy sekret DISCORD_WEBHOOK_URL zawiera aktualny URL webhooka: "
            f"{error}"
        )
        raise SystemExit(1) from error

    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")