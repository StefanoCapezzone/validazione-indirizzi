"""
Configurazione per il validatore di indirizzi.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

# Carica .env dalla directory del progetto
_env_path = Path(__file__).parent.parent / ".env"
load_dotenv(_env_path)

# Google Maps API Key - caricata da .env o variabile d'ambiente
API_KEY = os.environ.get("GOOGLE_MAPS_API_KEY", "")

# Limite lunghezza indirizzo
MAX_INDIRIZZO_LEN = 35

# Rate limiting per Google Maps API
REQUESTS_PER_SECOND = 40

# Dizionario abbreviazioni per ridurre lunghezza indirizzi
ABBREVIAZIONI = {
    "Via": "V.",
    "Viale": "V.le",
    "Piazza": "P.zza",
    "Piazzale": "P.le",
    "Corso": "C.so",
    "Largo": "L.go",
    "Vicolo": "Vic.",
    "Strada": "Str.",
    "Contrada": "C.da",
    "Località": "Loc.",
    "Frazione": "Fraz.",
    "Traversa": "Trav.",
    "Galleria": "Gall.",
    "Lungomare": "L.mare",
    "Lungotevere": "L.tevere",
    "Lungoadige": "L.adige",
    "Lungarno": "L.arno",
    "Circonvallazione": "Circ.",
    "Passaggio": "Pass.",
    "Salita": "Sal.",
    "Discesa": "Disc.",
    "Rampa": "Rpa",
    "Borgo": "B.go",
    "Rione": "R.ne",
    "Quartiere": "Q.re",
    "Centro Commerciale": "C.C.",
    "Parco Commerciale": "P.C.",
    "Zona Industriale": "Z.I.",
    "Area Industriale": "A.I.",
    "Strada Statale": "S.S.",
    "Strada Provinciale": "S.P.",
    "Strada Regionale": "S.R.",
    "Strada Comunale": "S.C.",
    "Nazionale": "Naz.",
    "Provinciale": "Prov.",
    "Regionale": "Reg.",
    "Comunale": "Com.",
    "Generale": "Gen.",
    "Maggiore": "Magg.",
    "Colonnello": "Col.",
    "Capitano": "Cap.",
    "Tenente": "Ten.",
    "Cavaliere": "Cav.",
    "Commendatore": "Comm.",
    "Professore": "Prof.",
    "Dottore": "Dott.",
    "Ingegnere": "Ing.",
    "Avvocato": "Avv.",
    "Senatore": "Sen.",
    "Onorevole": "On.",
    "Monsignore": "Mons.",
    "Santo": "S.",
    "Santa": "S.",
    "San": "S.",
    "Santi": "SS.",
    "Beato": "B.",
    "Beata": "B.",
}

# Suggerimenti per tipo di errore
SUGGERIMENTI_ERRORE = {
    "ZERO_RESULTS": "Verifica ortografia indirizzo",
    "NO_ROUTE": "Indirizzo generico, manca via/civico",
    "COMUNE_DIVERSO": "Verificare comune corretto",
    "CONTRADA": "Verificare indirizzo catastale",
    "STRADA_STATALE": "Cercare via del centro commerciale o riferimento più specifico",
    "SNC": "Aggiungere numero civico se possibile",
    "OVER_QUERY_LIMIT": "Limite API superato, riprovare più tardi",
    "REQUEST_DENIED": "API key non valida o servizio non abilitato",
    "INVALID_REQUEST": "Richiesta non valida, verificare dati",
    "UNKNOWN_ERROR": "Errore sconosciuto, riprovare",
}

# GLS Label Service Configuration
GLS_ENDPOINT = "https://labelservice.gls-italy.com/ilswebservice.asmx?wsdl"
GLS_SEDE = os.environ.get("GLS_SEDE", "")
GLS_CODICE_CLIENTE = os.environ.get("GLS_CODICE_CLIENTE", "")
GLS_PASSWORD = os.environ.get("GLS_PASSWORD", "")
GLS_CODICE_CONTRATTO = os.environ.get("GLS_CODICE_CONTRATTO", "")

# Limiti e retry per GLS API
GLS_MAX_PARCELS_PER_BATCH = 400
GLS_RETRY_ATTEMPTS = 3
GLS_RETRY_DELAY = 2  # secondi base per exponential backoff
