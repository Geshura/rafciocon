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
    except (error.HTTPError, error.URLError, TimeoutError) as exception:
        raise RequestException(str(exception)) from exception


STEAM_ID = os.getenv("STEAM_ID", "76561198034890618")
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE", "").strip()
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
        response = http_request(
            STEAM_PROFILE_URL,
            cookies={
                "steamLoginSecure": STEAM_LOGIN_SECURE,
                "browserid": "0",
            },
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/131.0 Safari/537.36"
                ),
                "Accept-Language": "pl,en;q=0.8",
            },
            timeout=15,
        )
        response.raise_for_status()
    except RequestException as error:
        return f"⚠️ Nie udało się połączyć ze Steam: {error}"

    if "login" in response.url.lower() or "Sign in" in response.text:
        return "❌ Sekret STEAM_LOGIN_SECURE wygasł lub jest nieprawidłowy."

    match = re.search(
        r"(?:var\s+)?rgGames\s*=\s*(\[.*?\])\s*;",
        response.text,
        re.DOTALL,
    )
    if not match:
        return (
            "⚠️ Steam zalogował sesję, ale nie udostępnił listy gier. "
            "Ustaw widoczność gier na Publiczna."
        )

    try:
        games: list[dict[str, Any]] = json.loads(html.unescape(match.group(1)))
    except (json.JSONDecodeError, TypeError):
        return "⚠️ Nie udało się odczytać danych gier ze strony Steam."

    if not games:
        return "💤 Brak gier zapisanych w bibliotece Steam."

    try:
        games_with_playtime = [
            game for game in games if int(game.get("hours_forever", 0) or 0) > 0
        ]
    except (AttributeError, TypeError, ValueError):
        return "⚠️ Steam zwrócił nieprawidłowy czas gry."
    if not games_with_playtime:
        return "💤 Steam nie zwrócił czasu gry dla żadnej gry."

    last_game = games_with_playtime[0]
    game_name = last_game.get("name", "Nieznana gra")
    # Steam's hours_* fields are actually measured in minutes.
    total_minutes = int(last_game.get("hours_forever", 0) or 0)
    try:
        recent_minutes = int(last_game.get("hours_2weeks", 0) or 0)
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
