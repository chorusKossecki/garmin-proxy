from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import httpx
import time
import os
import pandas as pd

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

CSV_FILE = '/tmp/moje_zaawansowane_dane.csv'

# TWOJE KLUCZE Z INTERVALS.ICU
INTERVALS_ATHLETE_ID = "TWÓJ_SKOPIOWANY_ATHLETE_ID"  
INTERVALS_API_KEY = "TWÓJ_SKOPIOWANY_API_KEY"

# KLUCZ GEMINI (Zostaw pusty, jeśli na razie testujesz same liczby)
GEMINI_API_KEY = ""

async def generuj_porade_ai(resting_hr, srednie_hr, czy_anomalia):
    if not GEMINI_API_KEY:
        return "Zrób mocny trening lub odpocznij w zależności od samopoczucia."
    url = f"https://googleapis.com{GEMINI_API_KEY}"
    prompt = f"Jesteś trenerem. Dzisiejsze tętno biegacza: {resting_hr} bpm (średnia: {srednie_hr}). Przemęczenie: {czy_anomalia}. Napisz poradę w 2 zdaniach po polsku."
    try:
        async with httpx.AsyncClient() as client:
            res = await client.post(url, json={"contents": [{"parts": [{"text": prompt}]}]}, timeout=5.0)
            if res.status_code == 200:
                return res.json()['candidates']['content']['parts']['text'].strip()
    except Exception:
        pass
    return "Brak połączenia z asystentem AI."

@app.get("/pobierz-treningi")
async def get_sport_data():
    dzis = time.strftime("%Y-%m-%d")
    wczoraj = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    auth = ("athlete", INTERVALS_API_KEY)
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. Próba pobrania danych z dzisiaj
            url_dzis = f"https://intervals.icu{INTERVALS_ATHLETE_ID}/wellness/{dzis}"
            response = await client.get(url_dzis, auth=auth)
            dane = response.json() if response.status_code == 200 else None
            
            # 2. Jeśli dzisiejszy dzień jest jeszcze pusty w bazie, pobieramy wczoraj
            if not dane or not dane.get('restingHR'):
                url_wczoraj = f"https://intervals.icu{INTERVALS_ATHLETE_ID}/wellness/{wczoraj}"
                response = await client.get(url_wczoraj, auth=auth)
                if response.status_code == 200:
                    dane = response.json()
                    
        if dane:
            rhr = dane.get('restingHR', 55)
            spo2 = dane.get('spO2', 98.0)
            
            # Zapis do pliku CSV
            nowy_wiersz = pd.DataFrame([{'Data': dzis, 'Tetno_Spoczynkowe': rhr, 'Natlenienie': spo2}])
            if os.path.exists(CSV_FILE):
                df_obecny = pd.read_csv(CSV_FILE)
                df_obecny = pd.concat([df_obecny, nowy_wiersz]).drop_duplicates(subset=['Data'], keep='last')
                df_obecny.to_csv(CSV_FILE, index=False)
            else:
                nowy_wiersz.to_csv(CSV_FILE, index=False)
            
            # Analiza anomalii
            df_hist = pd.read_csv(CSV_FILE)
            srednie_hr = df_hist['Tetno_Spoczynkowe'].mean()
            czy_anomalia = 1 if rhr > (srednie_hr + 4) else 0
            
            porada = await generuj_porade_ai(rhr, round(srednie_hr, 1), czy_anomalia)
            
            return {
                "srednie_tetno_hist": round(srednie_hr, 1),
                "tryb": "online",
                "ostatnie_dane": {
                    "Anomalia_Przemeczenie": czy_anomalia,
                    "Natlenienie_Krwi": spo2,
                    "Strategia_AI": porada
                }
            }
        raise Exception("Brak danych na dziś i wczoraj.")
        
    except Exception as e:
        return {
            "srednie_tetno_hist": 55.0,
            "tryb": "offline_tryb_awaryjny",
            "log_bledu": str(e),
            "ostatnie_dane": {
                "Anomalia_Przemeczenie": 0,
                "Natlenienie_Krwi": 98.0,
                "Strategia_AI": "Odpocznij i zregeneruj siły."
            }
        }
