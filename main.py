import os
import re
import json
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")

def get_steam_status():
    if not STEAM_LOGIN_SECURE:
        return "❌ Brak skonfigurowanego sekretu STEAM_LOGIN_SECURE w GitHubie!"

    # Ciasteczko sesyjne autoryzujące zapytanie
    cookies = {
        'steamLoginSecure': STEAM_LOGIN_SECURE
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # Strona ostatnich gier z autoryzacją ciasteczkiem
    games_url = f"https://steamcommunity.com/profiles/{STEAM_ID}/games/?tab=recent"
    
    try:
        response = requests.get(games_url, cookies=cookies, headers=headers)
        
        if response.status_code != 200 or "login" in response.url:
            return "❌ Ciasteczko steamLoginSecure wygasło lub jest niepoprawne. Zaktualizuj je w sekretach GitHub."

        # Steam zapisuje ostatnie gry w zmiennej JavaScript rgGames
        match = re.search(r'var rgGames = (\[.*?\]);', response.text, re.DOTALL)
        if match:
            games_data = json.loads(match.group(1))
            if games_data:
                last_game = games_data[0]
                game_title = last_game.get("name", "Nieznana gra")
                hours_2weeks = last_game.get("hours_2weeks", 0)
                hours_forever = last_game.get("hours_forever", 0)

                return f"🎮 **Ostatnia aktywność na Steamie:**\n📌 Gra: **{game_title}**\n⏱️ W ostatnich 2 tyg.: **{hours_2weeks} h** (Łącznie: {hours_forever} h)"

        return "💤 Brak publicznej historii ostatnich gier na profilu."

    except Exception as e:
        return f"⚠️ Błąd podczas parsowania Steam: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")