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

# --- TUTAJ WPISZ SWOJE DANE Z INTERVALS.ICU ---
INTERVALS_ATHLETE_ID = "659882"  
INTERVALS_API_KEY = "26ddnzto5f3iqqmi6m76jrc2n"
# -----------------------------------------------

@app.get("/pobierz-treningi")
async def get_sport_data():
    dzis = time.strftime("%Y-%m-%d")
    wczoraj = time.strftime("%Y-%m-%d", time.localtime(time.time() - 86400))
    
    # Poprawiony format autoryzacji dla Intervals.icu
    auth = ("API_KEY", INTERVALS_API_KEY)
    
    try:
        async with httpx.AsyncClient() as client:
            # 1. Próba pobrania danych z dzisiaj (UZUPEŁNIONO PEŁNĄ ŚCIEŻKĘ API)
            url_dzis = f"https://intervals.icu{INTERVALS_ATHLETE_ID}/wellness/{dzis}"
            response = await client.get(url_dzis, auth=auth)
            dane = response.json() if response.status_code == 200 else None
            
            # 2. Jeśli dzisiaj jest puste, pobieramy wczoraj (UZUPEŁNIONO PEŁNĄ ŚCIEŻKĘ API)
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
            
            return {
                "srednie_tetno_hist": round(srednie_hr, 1),
                "tryb": "online",
                "ostatnie_dane": {
                    "Anomalia_Przemeczenie": czy_anomalia,
                    "Natlenienie_Krwi": spo2
                }
            }
        raise Exception("Brak danych wellness na dzis i wczoraj.")
        
    except Exception as e:
        return {
            "srednie_tetno_hist": 55.0,
            "tryb": "offline_tryb_awaryjny",
            "log_bledu": str(e),
            "ostatnie_dane": {
                "Anomalia_Przemeczenie": 0,
                "Natlenienie_Krwi": 98.0
            }
        }
