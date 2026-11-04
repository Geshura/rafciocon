import os
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")

def get_steam_status():
    if not STEAM_LOGIN_SECURE:
        return "❌ Brak skonfigurowanego sekretu STEAM_LOGIN_SECURE w GitHubie!"

    # Ciasteczko sesyjne autoryzujące zapytanie jako Ty
    cookies = {
        'steamLoginSecure': STEAM_LOGIN_SECURE
    }
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }

    # Endpoint XML dla ostatnich gier - sortuje po ostatniej aktywności i nie blokuje skryptów
    url = f"https://steamcommunity.com/profiles/{STEAM_ID}/games/?tab=recent&xml=1"
    
    try:
        response = requests.get(url, cookies=cookies, headers=headers)
        
        if response.status_code != 200 or "login" in response.url:
            return "❌ Ciasteczko steamLoginSecure wygasło lub jest niepoprawne. Zaktualizuj je w sekretach GitHub."

        # Parsujemy odpowiedź jako XML
        soup = BeautifulSoup(response.content, "xml")
        
        games = soup.find_all("game")
        if not games:
            return "💤 Profil nie posiada publicznej listy gier lub historia jest ukryta."

        # Pierwsza gra na liście to ta odpalana/grana ostatnio
        last_game = games[0]
        game_name = last_game.find("name").text if last_game.find("name") else "Nieznana gra"
        hours_on_record = last_game.find("hoursOnRecord").text if last_game.find("hoursOnRecord") else "0"
        
        # Sprawdzamy czas w ostatnich 2 tygodniach, jeśli tag istnieje w XML
        hours_2w_tag = last_game.find("hours_2weeks")
        hours_2w_text = f" ({hours_2w_tag.text} h w ostatnich 2 tygodniach)" if hours_2w_tag and hours_2w_tag.text else ""

        return f"🎮 **Wizzkey** – Ostatnia aktywność (gra):\n📌 **{game_name}**\n⏱️ Łącznie: **{hours_on_record} h**{hours_2w_text}"

    except Exception as e:
        return f"⚠️ Błąd podczas pobierania danych o grach: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")