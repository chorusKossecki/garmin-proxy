from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from garminconnect import Garmin
import os
import time
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
TOKEN_DIR = '/tmp/garmin_tokens' # Miejsce na zapisanie bezpiecznej sesji

GARMIN_EMAIL = "TWÓJ_EMAIL"
GARMIN_PASSWORD = "TWOJE_HASŁO"

def analizuj_dane_i_anomalie():
    if os.path.exists(CSV_FILE):
        df_hist = pd.read_csv(CSV_FILE).dropna(subset=['Tetno_Spoczynkowe']).sort_values('Data')
    else:
        # Zmieniliśmy domyślną wartość na 55, aby pasowała do Twojego realnego tętna
        dane_startowe = {'Data': [time.strftime("%Y-%m-%d")], 'Tetno_Spoczynkowe': [55]}
        df_hist = pd.DataFrame(dane_startowe)
        df_hist.to_csv(CSV_FILE, index=False)

    if not df_hist.empty:
        srednie_tetno_hist = df_hist['Tetno_Spoczynkowe'].mean()
        df_hist['Anomalia_Przemeczenie'] = (df_hist['Tetno_Spoczynkowe'] > (srednie_tetno_hist + 4)).astype(int)
        return {
            "status": "success",
            "srednie_tetno_hist": round(srednie_tetno_hist, 1),
            "ostatnie_dane": df_hist.iloc[-1].to_dict()
        }
    return {"status": "error", "message": "Brak danych"}

@app.get("/pobierz-treningi")
def get_garmin_data():
    dzisiejsza_data = time.strftime("%Y-%m-%d")
    os.makedirs(TOKEN_DIR, exist_ok=True)
    
    try:
        # Przekazujemy ścieżkę token_store. Python najpierw spróbuje użyć zapisanego tokenu!
        client = Garmin(GARMIN_EMAIL, GARMIN_PASSWORD, token_store=TOKEN_DIR)
        client.login() # Jeśli token istnieje, zaloguje natychmiast bez generowania błędu 429
        
        nowe_dane = client.get_rhr_and_details(dzisiejsza_data)
        rhr = nowe_dane.get('restingHeartRate', 55)
        
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
