import os
import requests
from bs4 import BeautifulSoup
import json

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_steam_status():
    # Pobieramy publiczną stronę profilu Steam
    profile_url = f"https://steamcommunity.com/profiles/{STEAM_ID}/?xml=1"
    
    try:
        response = requests.get(profile_url)
        if response.status_code != 200:
            return "❌ Nie udało się pobrać strony profilu Steam."

        # Parsujemy dane XML udostępniane publicznie przez Steam
        soup = BeautifulSoup(response.content, "xml")
        
        persona_name = soup.find("steamID").text if soup.find("steamID") else "Gracz"
        online_state = soup.find("onlineState").text if soup.find("onlineState") else "offline"
        
        # Sprawdzamy czy aktualnie gra
        in_game_node = soup.find("inGameInfo")
        game_name_node = soup.find("gameName")

        if online_state == "online" and game_name_node:
            game_name = game_name_node.text
            return f"🎮 **{persona_name}** aktualnie gra w **{game_name}**!"
        else:
            # Jeśli nie gra, sprawdzamy status tekstowy (np. "Offline", "Last Online 3 days ago")
            state_message = soup.find("stateMessage").text if soup.find("stateMessage") else "Offline"
            # Oczyszczamy tekst ze zbędnych znaczników HTML jeśli występują
            clean_state = BeautifulSoup(state_message, "html.parser").get_text()
            return f"💤 **{persona_name}** jest obecnie w stanie: *{clean_state}*"

    except Exception as e:
        return f"⚠️ Wystąpił błąd podczas sprawdzania statusu Steam: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")