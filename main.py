import html
import json
import os
import re
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


STEAM_ID = os.getenv("STEAM_ID", "76561198034890618")
STEAM_API_KEY = os.getenv("STEAM_API_KEY", "").strip()
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
STEAM_RECENT_GAMES_URL = (
    "https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v0001/"
)
STEAM_GAMES_URL = "https://api.steampowered.com/IPlayerService/GetOwnedGames/v0001/"
STEAM_RECENT_PROFILE_URL = (
    f"https://steamcommunity.com/profiles/{STEAM_ID}/games/?tab=recent"
)


def format_playtime(minutes: int) -> str:
    hours, remaining_minutes = divmod(minutes, 60)
    if hours and remaining_minutes:
        return f"{hours} godz. {remaining_minutes} min"
    if hours:
        return f"{hours} godz."
    return f"{remaining_minutes} min"


def get_profile_recent_game() -> dict[str, Any] | None:
    try:
        response = http_request(
            STEAM_RECENT_PROFILE_URL,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
            timeout=15,
        )
        response.raise_for_status()
    except RequestException:
        return None

    # Wzorzec 1: Klasyczny zapis tablicy JavaScript rgGames
    match = re.search(
        r"(?:var\s+)?rgGames\s*=\s*(\[.*?\])\s*;",
        response.text,
        re.DOTALL,
    )
    if match:
        try:
            games = json.loads(html.unescape(match.group(1)))
            if isinstance(games, list) and games and isinstance(games[0], dict):
                return games[0]
        except (json.JSONDecodeError, TypeError):
            pass

    # Wzorzec 2: Zserializowane dane JSON w strukturze profilu Steam
    match_json = re.search(
        r"data-profile-json=[\"']({.*?})[\"']",
        response.text,
        re.DOTALL,
    )
    if match_json:
        try:
            profile_data = json.loads(html.unescape(match_json.group(1)))
            games = profile_data.get("rgGames")
            if isinstance(games, list) and games and isinstance(games[0], dict):
                first_game = games[0]
                return {
                    "appid": first_game.get("appid"),
                    "name": first_game.get("name"),
                    "playtime_forever": first_game.get("hours_forever", 0) * 60
                    if "hours_forever" in first_game
                    else first_game.get("playtime_forever", 0),
                    "playtime_2weeks": first_game.get("hours_2weeks", 0) * 60
                    if "hours_2weeks" in first_game
                    else first_game.get("playtime_2weeks", 0),
                }
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def get_steam_status() -> str:
    recent_games = None
    owned_games = None

    if STEAM_API_KEY:
        query = urlencode(
            {
                "key": STEAM_API_KEY,
                "steamid": STEAM_ID,
                "format": "json",
                "include_appinfo": "1",
                "include_played_free_games": "1",
            }
        )

        for endpoint in (STEAM_RECENT_GAMES_URL, STEAM_GAMES_URL):
            try:
                response = http_request(f"{endpoint}?{query}", timeout=15)
                response.raise_for_status()
                data = json.loads(response.text)
            except (RequestException, json.JSONDecodeError, TypeError):
                continue

            if not isinstance(data, dict):
                continue
            steam_response = data.get("response")
            if not isinstance(steam_response, dict):
                continue
            candidate_games = steam_response.get("games")
            if not isinstance(candidate_games, list):
                continue
            if endpoint == STEAM_RECENT_GAMES_URL:
                recent_games = candidate_games
            else:
                owned_games = candidate_games

    profile_recent_game = get_profile_recent_game()
    last_game = None
    total_source = None
    recent_source = None

    # 1. Priorytet absolutny: Pobranie z widoku strony profilu (odpowiada dokładnie temu, co na zrzucie ekrany)
    if profile_recent_game:
        last_game = profile_recent_game
        owned_by_appid = {game.get("appid"): game for game in (owned_games or [])}
        recent_by_appid = {game.get("appid"): game for game in (recent_games or [])}
        
        total_source = owned_by_appid.get(last_game.get("appid")) or last_game
        recent_source = recent_by_appid.get(last_game.get("appid")) or last_game

    # 2. Próba ustalenia z API GetRecentlyPlayedGames (jeśli profil HTML nic nie zwrócił)
    elif recent_games:
        last_game = recent_games[0]
        recent_source = last_game
        owned_by_appid = {game.get("appid"): game for game in (owned_games or [])}
        total_source = owned_by_appid.get(last_game.get("appid")) or last_game

    # 3. Szukanie w całej bibliotece po dacie uruchomienia (rtime_last_played)
    elif owned_games:
        try:
            games_by_appid = {
                game.get("appid"): game
                for game in owned_games
                if game.get("appid") is not None
            }
            games_with_last_played = [
                game
                for game in games_by_appid.values()
                if int(game.get("playtime_forever", 0) or 0) > 0
                and int(game.get("rtime_last_played", 0) or 0) > 0
            ]
            if games_with_last_played:
                last_game = max(
                    games_with_last_played,
                    key=lambda game: int(game.get("rtime_last_played", 0)),
                )
                total_source = last_game
                recent_source = last_game
        except (AttributeError, TypeError, ValueError):
            pass

    # 4. Fallback: najwięcej ogólnego czasu
    if not last_game and owned_games:
        games_with_playtime = [
            game
            for game in owned_games
            if int(game.get("playtime_forever", 0) or 0) > 0
        ]
        if games_with_playtime:
            last_game = games_with_playtime[0]
            total_source = last_game
            recent_source = last_game

    if not last_game:
        return (
            "⚠️ Nie udało się pobrać informacji o ostatniej grze. "
            "Upewnij się, że Twój profil i widoczność gier na Steamie są ustawione jako **Publiczne**."
        )

    try:
        game_name = str(last_game.get("name", "Nieznana gra"))
        total_minutes = int(
            total_source.get("playtime_forever")
            or total_source.get("hours_forever", 0)
            or 0
        )
        recent_minutes = int(
            recent_source.get("playtime_2weeks")
            or recent_source.get("hours_2weeks", 0)
            or 0
        )
    except (AttributeError, TypeError, ValueError):
        return "⚠️ Steam zwrócił nieprawidłowy czas gry."

    if total_minutes <= 0:
        return "⚠️ Steam nie zwrócił łącznego czasu dla ostatniej gry."

    if recent_minutes < 0:
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