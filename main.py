import html
import json
import os
import re
from typing import Any
from urllib import error, request


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
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
# Wchodzimy bezpośrednio na zakładkę /games/?tab=recent profilu publicznego
STEAM_PROFILE_RECENT_URL = (
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
        # Używamy przeglądarkowego User-Agenta, żeby Steam nie odrzucił żądania jako bota
        response = http_request(
            STEAM_PROFILE_RECENT_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                              "AppleWebKit/537.36 (KHTML, like Gecko) "
                              "Chrome/120.0.0.0 Safari/537.36",
                "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
            },
            timeout=15,
        )
        response.raise_for_status()
    except RequestException:
        return None

    # Metoda 1: Szukanie zmiennej JavaScript rgGames przypisanej na stronie
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

    # Metoda 2: Szukanie zserializowanego JSON-a w atrybutach elementów (np. struktury profilu)
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
                # Konwersja formatów godzinowych na minuty, jeśli występują
                return {
                    "name": first_game.get("name"),
                    "playtime_forever": int(
                        first_game.get("hours_forever", 0) * 60
                        if "hours_forever" in first_game
                        else first_game.get("playtime_forever", 0)
                    ),
                    "playtime_2weeks": int(
                        first_game.get("hours_2weeks", 0) * 60
                        if "hours_2weeks" in first_game
                        else first_game.get("playtime_2weeks", 0)
                    ),
                }
        except (json.JSONDecodeError, TypeError):
            pass

    return None


def get_steam_status() -> str:
    game = get_profile_recent_game()
    if not game:
        return (
            "⚠️ Nie udało się pobrać danych ze strony profilu Steam. "
            "Upewnij się, że Twój profil oraz szczegóły gier są ustawione jako **Publiczne**."
        )

    try:
        game_name = str(game.get("name", "Nieznana gra"))
        total_minutes = int(game.get("playtime_forever", 0) or 0)
        recent_minutes = int(game.get("playtime_2weeks", 0) or 0)
    except (AttributeError, TypeError, ValueError):
        return "⚠️ Steam zwrócił nieprawidłowe dane o czasie gry."

    if total_minutes <= 0:
        return "⚠️ Steam nie zwrócił łącznego czasu dla ostatniej gry."

    return (
        "🎮 **Ostatnia gra na Steamie (z profilu):**\n"
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