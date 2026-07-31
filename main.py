from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from playwright.sync_api import sync_playwright
import os
import time
import json
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Ścieżka do trwałego dysku Render (Persistent Disk)
DATA_DIR = '/opt/render/project/src/data'
os.makedirs(DATA_DIR, exist_ok=True)

CSV_FILE = os.path.join(DATA_DIR, 'moje_zaawansowane_dane.csv')
COOKIES_FILE = os.path.join(DATA_DIR, 'garmin_cookies.json')

# Wpisz swoje dane do Garmina
GARMIN_EMAIL = "w.horodejczuk@gmail.com"
GARMIN_PASSWORD = "Juzek1986!(*^"

def analizuj_dane_i_anomalie():
    if os.path.exists(CSV_FILE):
        df_hist = pd.read_csv(CSV_FILE).dropna(subset=['Tetno_Spoczynkowe']).sort_values('Data')
    else:
        df_hist = pd.DataFrame({'Data': [time.strftime("%Y-%m-%d")], 'Tetno_Spoczynkowe': [55]})
        df_hist.to_csv(CSV_FILE, index=False)

    if not df_hist.empty:
        srednie_tetno_hist = df_hist['Tetno_Spoczynkowe'].mean()
        df_hist['Anomalia_Przemeczenie'] = (df_hist['Tetno_Spoczynkowe'] > (srednie_tetno_hist + 4)).astype(int)
        ostatni_wiersz = df_hist.iloc[-1].to_dict()
        return {
            "srednie_tetno_hist": round(srednie_tetno_hist, 1),
            "ostatnie_dane": {
                "Anomalia_Przemeczenie": int(ostatni_wiersz['Anomalia_Przemeczenie'])
            }
        }
    return {"srednie_tetno_hist": 55, "ostatnie_dane": {"Anomalia_Przemeczenie": 0}}

def pobierz_z_garmin_przez_przegladarke():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        if os.path.exists(COOKIES_FILE):
            with open(COOKIES_FILE, 'r') as f:
                context.add_cookies(json.load(f))

        page = context.new_page()
        dzis = time.strftime("%Y-%m-%d")
        page.goto("https://garmin.com")
        
        try:
            js_script = f"""
            async () => {{
                let res = await fetch('https://garmin.com{dzis}');
                if (res.status === 401 || res.status === 403) return null;
                return await res.json();
            }}
            """
            dane = page.evaluate(js_script)
        except Exception:
            dane = None

        if not dane:
            page.goto("https://garmin.com")
            page.wait_for_selector('input[type="email"]')
            page.fill('input[type="email"]', GARMIN_EMAIL)
            page.fill('input[type="password"]', GARMIN_PASSWORD)
            page.click('button[type="submit"]')
            
            page.wait_for_url("**/modern/**", timeout=25000)

            with open(COOKIES_FILE, 'w') as f:
                json.dump(context.cookies(), f)

            dane = page.evaluate(js_script)

        browser.close()
        return dane

@app.get("/pobierz-treningi")
def get_garmin_data():
    dzisiejsza_data = time.strftime("%Y-%m-%d")
    try:
        nowe_dane = pobierz_z_garmin_przez_przegladarke()
        rhr = nowe_dane.get('restingHeartRate', 55) if nowe_dane else 55
        
        nowy_wiersz = pd.DataFrame([{'Data': dzisiejsza_data, 'Tetno_Spoczynkowe': rhr}])
        if os.path.exists(CSV_FILE):
            df_obecny = pd.read_csv(CSV_FILE)
            df_obecny = pd.concat([df_obecny, nowy_wiersz]).drop_duplicates(subset=['Data'], keep='last')
            df_obecny.to_csv(CSV_FILE, index=False)
        else:
            nowy_wiersz.to_csv(CSV_FILE, index=False)
            
        wynik = analizuj_dane_i_anomalie()
        wynik["tryb"] = "online"
        return wynik
    except Exception as e:
        wynik_offline = analizuj_dane_i_anomalie()
        wynik_offline["tryb"] = "offline_tryb_awaryjny"
        wynik_offline["log_bledu"] = str(e)
        return wynik_offline
