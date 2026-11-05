@echo off
cls
echo ===================================================
echo   Uruchamianie procesu automatyzacji Steam
echo ===================================================

:: 1. Sprawdzenie czy Python jest zainstalowany
python --version
if %errorlevel% neq 0 (
    echo.
    echo [BLAD] Python nie jest widoczny w systemie (brak w PATH lub nie zainstalowany).
    echo Zaznacz "Add python.exe to PATH" podczas instalacji Pythona!
    echo.
    pause
    exit /b 1
)

:: 2. Sprawdzenie i instalacja wymaganych bibliotek (Playwright)
echo.
echo Sprawdzanie wymaganych pakietow Python...
python -c "import playwright" >nul 2>&1
if %errorlevel% neq 0 (
    echo Brak biblioteki Playwright. Instalowanie wymaganych komponentow...
    pip install playwright
    playwright install chromium
)

:: 3. Wybór odpowiedniego pliku głównego
set TARGET_SCRIPT=""
if exist "main.py" (
    set TARGET_SCRIPT=main.py
) else if exist "main_local.py" (
    set TARGET_SCRIPT=main_local.py
) else if exist "steam_scraper.py" (
    set TARGET_SCRIPT=steam_scraper.py
)

if "%TARGET_SCRIPT%"=="" (
    echo.
    echo [BLAD] Nie znaleziono zadnego pliku Python (.py)!
    echo Upewnij sie, ze ten plik .bat znajduje sie W TYM SAMYM FOLDERZE co main.py lub main_local.py.
    echo Obecny katalog to: %cd%
    echo.
    pause
    exit /b 1
)

echo.
echo Znaleziono plik: %TARGET_SCRIPT%
echo Uruchamianie skryptu...
echo ---------------------------------------------------
python %TARGET_SCRIPT%
echo ---------------------------------------------------

echo.
echo Praca skryptu zakonczona.
pause