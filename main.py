import os
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_steam_status():
    # Publiczny endpoint XML Steama - nie wymaga klucza ani logowania
    url = f"https://steamcommunity.com/profiles/{STEAM_ID}/?xml=1"
    
    try:
        response = requests.get(url)
        if response.status_code != 200:
            return "❌ Nie udało się połączyć z serwerami Steam."

        # Parsowanie danych XML
        soup = BeautifulSoup(response.content, "xml")
        
        persona_name = soup.find("steamID").text if soup.find("steamID") else "Gracz"
        online_state = soup.find("onlineState").text if soup.find("onlineState") else "offline"
        state_message = soup.find("stateMessage").text if soup.find("stateMessage") else "Offline"
        
        # Sprawdzamy, czy gracz gra w coś w tym momencie
        game_name_node = soup.find("gameName")
        
        if game_name_node and game_name_node.text.strip():
            return f"🎮 **{persona_name}** gra teraz w: **{game_name_node.text.strip()}**!"
        else:
            # Oczyszczamy ewentualne znaczniki HTML ze statusu
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