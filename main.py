import os
import re
import json
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_steam_status():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    games_url = f"https://steamcommunity.com/profiles/{STEAM_ID}/games/?tab=recent"
    
    try:
        response = requests.get(games_url, headers=headers)
        if response.status_code != 200:
            return "❌ Nie udało się pobrać strony profilu Steam (sprawdź czy profil/szczegóły gier są publiczne)."

        soup = BeautifulSoup(response.content, "html.parser")
        
        # Pobieranie nazwy użytkownika
        name_node = soup.find("a", class_="header_real_name") or soup.find("span", class_="actual_persona_name")
        persona_name = name_node.text.strip() if name_node else "Gracz"

        # Steam zapisuje listę ostatnich gier w skrypcie JavaScript jako zmienna rgGames
        match = re.search(r'var rgGames = (\[.*?\]);', response.text, re.DOTALL)
        if match:
            games_data = json.loads(match.group(1))
            if games_data:
                last_game = games_data[0]
                game_title = last_game.get("name", "Nieznana gra")
                
                # Czas w ostatnich 2 tygodniach (podawany w minutach lub jako zmienna hours)
                minutes_2weeks = last_game.get("hours_2weeks", 0)
                # Czas w godzinach zaokrąglony do 1 miejsca po przecinku
                hours_2weeks = round(minutes_2weeks, 1) if isinstance(minutes_2weeks, (int, float)) else 0
                
                # Jeśli klucz hours_2weeks ma format stringa lub inny, wyciągnijmy z fields jeśli trzeba
                if not hours_2weeks and "hours_2weeks" in last_game:
                    try:
                        hours_2weeks = float(str(last_game["hours_2weeks"]).replace(",", "."))
                    except:
                        hours_2weeks = 0

                return f"🎮 **{persona_name}** (status: Niewidoczny/Offline)\nOstatnio odpalona gra: **{game_title}** — **{hours_2weeks} h** w ostatnich 2 tygodniach."

        return f"💤 **{persona_name}** jest offline, a na profilu brak danych o ostatnich grach."

    except Exception as e:
        return f"⚠️ Błąd podczas parsowania Steam: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")