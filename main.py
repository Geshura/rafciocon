import os
import time
import random
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_steam_status():
    # Losowe opóźnienie od 2 do 5 sekund, żeby nie spamować serwera Steama
    time.sleep(random.randint(2, 5))
    
    url = f"https://steamcommunity.com/profiles/{STEAM_ID}/?xml=1"
    
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }
    
    try:
        response = requests.get(url, headers=headers)
        
        # Jeśli Steam nadal wyrzuca błąd zbyt wielu żądań
        if response.status_code == 429:
            return "⏳ Steam zablokował tymczasowo zapytania (Too Many Requests). Spróbujemy ponownie za godzinę."
            
        if response.status_code != 200:
            return f"❌ Błąd HTTP ze Steama: {response.status_code}"

        soup = BeautifulSoup(response.content, "xml")
        
        persona_name = soup.find("steamID").text if soup.find("steamID") else "Gracz"
        online_state = soup.find("onlineState").text if soup.find("onlineState") else "offline"
        state_message = soup.find("stateMessage").text if soup.find("stateMessage") else "Offline"
        
        game_name_node = soup.find("gameName")
        
        if game_name_node and game_name_node.text.strip():
            return f"🎮 **{persona_name}** gra teraz w: **{game_name_node.text.strip()}**!"
        else:
            clean_state = BeautifulSoup(state_message, "html.parser").get_text()
            return f"💤 **{persona_name}** jest obecnie w stanie: *{clean_state}*"

    except Exception as e:
        return f"⚠️ Wystąpił błąd podczas pobierania statusu: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")