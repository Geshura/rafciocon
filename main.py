import os
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
STEAM_LOGIN_SECURE = os.getenv("STEAM_LOGIN_SECURE")

def get_steam_status():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cookie": f"steamLoginSecure={STEAM_LOGIN_SECURE}" if STEAM_LOGIN_SECURE else ""
    }

    # Pobieramy główną stronę profilu, która zawiera sekcję wyróżnionych gier i status
    profile_url = f"https://steamcommunity.com/profiles/{STEAM_ID}/"
    
    try:
        response = requests.get(profile_url, headers=headers)
        if response.status_code != 200:
            return f"❌ Błąd HTTP ze Steama: {response.status_code}"

        soup = BeautifulSoup(response.content, "html.parser")
        
        # Sprawdzamy status online/offline z nagłówka profilu
        status_node = soup.find("div", class_="profile_in_game_header")
        status_text = status_node.text.strip() if status_node else "Offline"
        
        # Szukamy wyróżnionych gier z sekcji kolekcjonera gier (widocznych w HTML)
        games_slots = soup.find_all("div", class_="showcase_slot showcase_gamecollector_game")
        featured_games = []
        
        for slot in games_slots:
            link = slot.find("a")
            if link and "href" in link.attrs:
                app_id = link["href"].rstrip("/").split("/")[-1]
                featured_games.append(app_id)

        # Informacja o grze na żywo lub ostatnio widzianych wyróżnionych
        if "In Game" in str(soup) or (status_node and status_node.text.strip() not in ["Offline", "Snooze"]):
            return f"🎮 **Wizzkey** gra obecnie! Status: **{status_text}**"
        
        games_info = f" (Wyróżnione AppID: {', '.join(featured_games)})" if featured_games else ""
        return f"💤 **Wizzkey** jest obecnie w stanie: **{status_text}**{games_info}"

    except Exception as e:
        return f"⚠️ Wystąpił błąd podczas analizy profilu: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")
