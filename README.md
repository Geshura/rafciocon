# rafciocon

Skrypt odczytuje ze strony Steam ostatnio uruchamianą grę użytkownika, jej
łączny czas gry oraz czas z ostatnich dwóch tygodni, a następnie wysyła status
na Discorda za pomocą Steam Web API.

## Konfiguracja

Ustaw zmienne środowiskowe:

- `STEAM_API_KEY` - klucz Steam Web API
- `STEAM_ID` - 64-bitowy Steam ID użytkownika (domyślnie: `76561198034890618`)
- `DISCORD_WEBHOOK_URL` - adres webhooka Discord

Profil Steam musi udostępniać dane gier publicznie. Klucz API można uzyskać na
stronie [Steam Web API Key](https://steamcommunity.com/dev/apikey).

Uruchom:

```bash
pip install -r requirements.txt
python main.py
```