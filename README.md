# rafciocon

Skrypt odczytuje ze strony Steam ostatnio uruchamianą grę użytkownika, jej
łączny czas gry oraz czas z ostatnich dwóch tygodni, a następnie wysyła status
na Discorda. Nie wymaga `STEAM_API_KEY`.

## Konfiguracja

Ustaw zmienne środowiskowe:

- `STEAM_LOGIN_SECURE` - aktualna wartość ciasteczka `steamLoginSecure`
- `STEAM_ID` - 64-bitowy Steam ID użytkownika (domyślnie: `76561198034890618`)
- `DISCORD_WEBHOOK_URL` - adres webhooka Discord

Profil Steam musi udostępniać dane gier dla zalogowanej sesji.

Uruchom:

```bash
pip install -r requirements.txt
python main.py
```