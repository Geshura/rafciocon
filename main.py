import os
import re
import requests
from bs4 import BeautifulSoup

STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_steam_status():
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "pl-PL,pl;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    # 1. Sprawdzamy główną stronę profilu XML (czy gra w coś na żywo)
    xml_url = f"https://steamcommunity.com/profiles/{STEAM_ID}/?xml=1"
    
    try:
        res_xml = requests.get(xml_url, headers=headers)
        if res_xml.status_code == 200:
            soup_xml = BeautifulSoup(res_xml.content, "xml")
            persona_name = soup_xml.find("steamID").text if soup_xml.find("steamID") else "Gracz"
            game_name_node = soup_xml.find("gameName")

            # Jeśli gra w coś w tej chwili (nawet jeśli ma status niewidoczny, czasem tu trafia)
            if game_name_node and game_name_node.text.strip():
                return f"🎮 **{persona_name}** aktualnie gra w **{game_name_node.text.strip()}**!"

        # 2. Jeśli status to offline/niewidoczny, skrapujemy bezpośrednio stronę ostatnich gier HTML
        games_url = f"https://steamcommunity.com/profiles/{STEAM_ID}/games/?tab=recent"
        res_games = requests.get(games_url, headers=headers)
        
        # Wyciągamy nazwisko gracza z nagłówka strony
        soup_html = BeautifulSoup(res_games.content, "html.parser")
        name_node = soup_html.find("a", class_="header_real_name") or soup_html.find("span", class_="actual_persona_name")
        persona_name = name_node.text.strip() if name_node else "Gracz"

        # Steam trzyma dane o ostatnich grach w zmiennej JavaScript `rgGames` na stronie
        match = re.search(r'var rgGames = (\[.*?\]);', res_games.text, re.DOTALL)
        if match:
            import json
            games_data = json.loads(match.group(1))
            if games_data:
                last_game = games_data[0]
                game_title = last_game.get("name", "Nieznana gra")
                hours_2w = last_game.get("hours_forever", "0") # lub hours w 2w jeśli dostępne
                hours_recent = last_game.get("hours", None)
                
                if hours_recent:
                    return f"👀 **{persona_name}** (status: Niewidoczny/Offline)\nOstatnio grał w: **{game_title}** ({hours_recent} h w ostatnich 2 tygodniach)."
                else:
                    return f"👀 **{persona_name}** (status: Niewidoczny/Offline)\nOstatnio grał w: **{game_title}**."

        # Alternatywne parsowanie z bloku profilowego HTML
        recent_block = soup_html.find_all("div", class_="recent_game")
        if recent_block:
            first_game = recent_block[0]
            game_title = first_game.find("div", class_="game_name").text.strip()
            time_played = first_game.find("div", class_="game_info").text.strip()
            return f"👀 **{persona_name}** (status: Niewidoczny/Offline)\nOstatnia aktywność: **{game_title}** ({time_played})."

        return f"💤 **{persona_name}** jest niewidoczny/offline i brak publicznych ostatnich gier."

    except Exception as e:
        return f"⚠️ Błąd podczas pobierania profilu: {e}"

if __name__ == "__main__":
    if not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanego sekretu DISCORD_WEBHOOK_URL!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")