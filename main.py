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


STEAM_PROFILE_XML_URL = "https://steamcommunity.com/id/geshurapl/?xml=1"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()


def format_playtime(hours_str: str) -> str:
    try:
        clean_val = hours_str.replace(",", ".").strip()
        hours_float = float(clean_val)
        total_minutes = int(round(hours_float * 60))
        hours, remaining_minutes = divmod(total_minutes, 60)
        if hours and remaining_minutes:
            return f"{hours} godz. {remaining_minutes} min"
        if hours:
            return f"{hours} godz."
        return f"{remaining_minutes} min"
    except (ValueError, TypeError):
        return f"{hours_str} godz."


def get_steam_status() -> str:
    try:
        response = http_request(
            STEAM_PROFILE_XML_URL,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
            },
            timeout=15,
        )
        response.raise_for_status()
    except RequestException:
        return "⚠️ Nie udało się połączyć z profilem Steam."

    xml_text = response.text

    if "<error>" in xml_text or "The specified profile could not be found" in xml_text:
        return "⚠️ Profil Steam nie został znaleziony lub jest prywatny."

    recent_games_match = re.search(r"<recentgames>(.*?)</recentgames>", xml_text, re.DOTALL)
    if not recent_games_match:
        return "💤 Brak publicznych informacji o ostatnio granych tytułach na profilu."

    games_block = recent_games_match.group(1)
    
    game_match = re.search(r"<game>(.*?)</game>", games_block, re.DOTALL)
    if not game_match:
        return "💤 Brak gier w sekcji ostatniej aktywności."

    game_content = game_match.group(1)

    def extract_tag(tag: str) -> str:
        m = re.search(f"<{tag}>(.*?)</{tag}>", game_content, re.DOTALL)
        return html.unescape(m.group(1).strip()) if m else ""

    game_name = extract_tag("name")
    hours_recent = extract_tag("hoursLast2Weeks")
    hours_forever = extract_tag("hoursOnRecord")

    if not game_name:
        return "⚠️ Nie udało się odczytać nazwy ostatniej gry ze struktury profilu."

    return (
        "🎮 **Ostatnia gra na Steamie (`geshurapl`):**\n"
        f"📌 **{game_name}**\n"
        f"⏱️ Łączny czas gry: **{format_playtime(hours_forever)}**\n"
        f"📅 W ostatnich 2 tygodniach: **{format_playtime(hours_recent)}**"
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