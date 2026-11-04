import os
import requests

STEAM_API_KEY = os.getenv("STEAM_API_KEY")
STEAM_ID = "76561198034890618"
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

def get_steam_status():
    summary_url = f"https://api.steampowered.com/ISteamUser/GetPlayerSummaries/v2/?key={STEAM_API_KEY}&steamids={STEAM_ID}"
    res_summary = requests.get(summary_url).json()
    players = res_summary.get("response", {}).get("players", [])
    
    if not players:
        return "Nie znaleziono gracza o podanym ID."
        
    player = players[0]
    persona_name = player.get("personaname", "Gracz")
    current_game = player.get("gameextrainfo")

    if current_game:
        return f"🎮 **{persona_name}** aktualnie gra w **{current_game}**!"

    recent_url = f"https://api.steampowered.com/IPlayerService/GetRecentlyPlayedGames/v1/?key={STEAM_API_KEY}&steamid={STEAM_ID}"
    res_recent = requests.get(recent_url).json()
    games = res_recent.get("response", {}).get("games", [])

    if games:
        last_game = games[0]["name"]
        playtime_2w = round(games[0]["playtime_2weeks"] / 60, 1)
        return f"💤 **{persona_name}** jest offline. Ostatnio grał w **{last_game}** ({playtime_2w} h w ostatnich 2 tygodniach)."
    else:
        return f"💤 **{persona_name}** jest offline i brak aktywności w ostatnich 2 tygodniach."

if __name__ == "__main__":
    if not STEAM_API_KEY or not DISCORD_WEBHOOK_URL:
        print("Błąd: Brak skonfigurowanych kluczy w sekretach GitHub!")
        exit(1)
        
    message = get_steam_status()
    response = requests.post(DISCORD_WEBHOOK_URL, json={"content": message})
    print(f"Wysłano status na Discorda. Kod odpowiedzi: {response.status_code}")