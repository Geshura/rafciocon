# rafciocon

Skrypt pobiera z Steam Web API ostatnio uruchamianą grę użytkownika, jej
łączny czas gry oraz czas z ostatnich dwóch tygodni, a następnie wysyła status
na Discorda.

## Konfiguracja

Ustaw zmienne środowiskowe:

- `STEAM_API_KEY` - klucz Steam Web API z
  [steamcommunity.com/dev/apikey](https://steamcommunity.com/dev/apikey)
- `STEAM_ID` - 64-bitowy Steam ID użytkownika
- `DISCORD_WEBHOOK_URL` - adres webhooka Discord

Profil Steam musi mieć publiczne dane gier. Steam Web API nie zwróci historii
ostatnio uruchamianych gier dla profilu prywatnego.

Uruchom:

```bash
pip install -r requirements.txt
python main.py
```