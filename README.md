# rafciocon

Skrypt odczytuje ze strony Steam ostatnio uruchamianą grę użytkownika, jej
łączny czas gry oraz czas z ostatnich dwóch tygodni, a następnie wysyła status
na Discorda za pomocą Steam Web API.

## Konfiguracja

Ustaw zmienne środowiskowe:

- `STEAM_ID` - 64-bitowy Steam ID użytkownika (domyślnie: `76561198034890618`)
- `DISCORD_WEBHOOK_URL` - adres webhooka Discord

Profil Steam musi udostępniać dane gier publicznie. Klucz API można uzyskać na
stronie [Steam Web API Key](https://steamcommunity.com/dev/apikey).

Przykład dla PowerShell:

```powershell
$env:DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."
```

W zwykłym wierszu polecenia CMD użyj zamiast tego:

```bat
set STEAM_HEADLESS=1
set DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
python main_local.py
```

Nie zapisuj klucza ani webhooka bezpośrednio w plikach źródłowych. Jeśli zostały
upublicznione, unieważnij klucz Steam i wygeneruj nowy webhook Discorda.

Uruchom:

```bash
pip install -r requirements.txt
python main.py
```

Wariant lokalny korzystający z renderowania profilu przez Playwright:

```bash
playwright install chromium
python main_local.py
```

Jeżeli dane są widoczne tylko po zalogowaniu w kliencie Steam, Playwright musi
mieć własną zapisaną sesję. Przy pierwszym uruchomieniu użyj widocznego okna:

```powershell
$env:STEAM_HEADLESS = "0"
python main_local.py
```

Zaloguj się w otwartym Chromium i uruchom skrypt ponownie. Sesja zostanie
zapisana w `.steam-playwright-profile`; nie udostępniaj tego katalogu, bo
zawiera cookies logowania. Kolejne uruchomienia mogą działać w tle:

```powershell
$env:STEAM_HEADLESS = "1"
python main_local.py
```

Skrypt korzysta za każdym razem z tego samego profilu zapisanego obok
`main_local.py`. Jeśli Steam unieważni sesję, jednorazowo powtórz logowanie z
`STEAM_HEADLESS=0`; nie twórz nowego katalogu profilu.

Po udanym logowaniu skrypt zapisuje także sesję Playwright w
`steam-storage-state.json` i ładuje ją przy kolejnych uruchomieniach. Ten plik
jest sekretem i został dodany do `.gitignore`.

Możesz również użyć własnego eksportu cookies w formacie Playwright. Plik może
być listą cookies albo plikiem `storage_state.json` zawierającym pole
`"cookies"`:

```powershell
$env:STEAM_COOKIES_FILE = "C:\bezpieczna\sciezka\steam-storage-state.json"
python main_local.py
```

Cookies Steam są danymi logowania. Nie commituj pliku, nie wysyłaj go nikomu i
nie umieszczaj go w katalogu projektu. Po eksporcie wyloguj lub unieważnij sesję,
jeśli plik został przypadkowo ujawniony.

Opcjonalnie możesz ustawić `TARGET_GAME`, aby sprawdzić, czy wskazana nazwa
znajduje się w wyrenderowanym HTML:

```powershell
$env:TARGET_GAME = "Jurassic World"
```

## Automatyczne uruchamianie na GitHub

Workflow `.github/workflows/check_status.yml` uruchamia `main.py` co godzinę
oraz może zostać uruchomiony ręcznie z zakładki **Actions**. Przed pierwszym
uruchomieniem dodaj w repozytorium, w **Settings → Secrets and variables →
Actions**, sekrety:

- `DISCORD_WEBHOOK_URL`
- `STEAM_STORAGE_STATE_B64`

Następnie wypchnij kod:

```bat
git add .github README.md requirements.txt main.py .gitignore
git commit -m "Configure Steam status workflow"
git push origin main
```

W zakładce **Actions** wybierz **Steam Status Check**, kliknij **Run workflow**
i sprawdź logi. GitHub uruchamia workflow niezależnie od tego, czy lokalna
konsola jest otwarta.

`main_local.py` korzysta z lokalnej sesji Chromium i nie jest używany przez
workflow. Aby utworzyć sekret sesji dla GitHub Actions po udanym logowaniu
lokalnym, wykonaj w PowerShell:

```powershell
$state = [Convert]::ToBase64String(
  [IO.File]::ReadAllBytes("steam-storage-state.json")
)
$state | Set-Clipboard
```

W GitHub dodaj skopiowaną zawartość jako sekret
`STEAM_STORAGE_STATE_B64`. Nie wysyłaj do repozytorium katalogu
`.steam-playwright-profile`, pliku `steam-storage-state.json` ani webhooka.