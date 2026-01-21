# Validazione Indirizzi

Applicazione per la validazione di indirizzi italiani tramite Google Maps Geocoding API e upload delle spedizioni su GLS Label Service.

## Funzionalità

- **Validazione indirizzi**: Verifica e normalizza indirizzi usando Google Maps API
- **Supporto multi-formato**: OLD Layout, NEW Layout, AGENZIE
- **Abbreviazione automatica**: Riduce la lunghezza degli indirizzi (max 35 caratteri)
- **Upload GLS**: Carica le spedizioni validate su GLS Label Service via SOAP
- **Tracciamento duplicati**: Evita upload doppi delle stesse spedizioni
- **Interfaccia grafica**: GUI Tkinter intuitiva con due tab (Validazione e Upload GLS)

## Installazione

```bash
# Clona il repository
git clone https://github.com/StefanoCapezzone/validazione-indirizzi.git
cd validazione-indirizzi

# Installa le dipendenze
pip install -r requirements.txt

# Configura le credenziali
cp .env.example .env
# Modifica .env con le tue API key e credenziali
```

## Configurazione

Crea un file `.env` nella root del progetto:

```bash
# Google Maps Geocoding API Key
GOOGLE_MAPS_API_KEY=la-tua-api-key

# GLS Label Service Credentials
GLS_SEDE=XX
GLS_CODICE_CLIENTE=000000
GLS_PASSWORD=la-tua-password
GLS_CODICE_CONTRATTO=00
```

## Utilizzo

### Interfaccia Grafica (consigliato)

```bash
python run_gui.py
```

### Linea di Comando

```bash
# Validazione singolo file
python run.py file.xlsx

# Validazione cartella
python run.py /path/to/folder

# Dry run (senza scrivere file)
python run.py file.xlsx --dry-run
```

## Struttura Progetto

```
validazione-indirizzi/
├── address_validator/
│   ├── __init__.py
│   ├── config.py          # Configurazione e costanti
│   ├── models.py          # Modelli dati validazione
│   ├── formats.py         # Rilevamento formato file
│   ├── geocoding.py       # Client Google Maps API
│   ├── abbreviator.py     # Abbreviazione indirizzi
│   ├── processor.py       # Processore validazione
│   ├── excel_io.py        # Lettura/scrittura Excel
│   ├── gui.py             # Interfaccia grafica
│   ├── gls_models.py      # Modelli dati GLS
│   ├── gls_client.py      # Client SOAP GLS
│   ├── gls_processor.py   # Processore upload GLS
│   └── upload_tracker.py  # Tracciamento upload
├── docs/
│   ├── specifiche.md      # Specifiche funzionali
│   └── spec-api.md        # Specifiche API GLS
├── .env.example
├── requirements.txt
├── run.py                 # Entry point CLI
├── run_gui.py             # Entry point GUI
└── README.md
```

## Output

### Validazione
- `*_VALIDATO.xlsx`: Indirizzi validati con successo
- `*_NON_VALIDATI.xlsx`: Indirizzi con errori da verificare manualmente
- `*_REPORT_ERRORI.csv`: Report dettagliato degli errori

### Upload GLS
- `.gls_uploads.json`: Tracciamento delle spedizioni caricate (nella cartella dei file)

## Formati Supportati

| Formato | Colli | Peso | Identificazione |
|---------|-------|------|-----------------|
| OLD Layout | 1 | 3 kg | Colonna "Layout" |
| NEW Layout | 2 | 3 kg | Colonna "LOCATION NEGOZIO" |
| AGENZIE | Manuale | Manuale | Colonne "Area", "N° Point serviti" |

## Requisiti

- Python 3.10+
- Google Maps API Key (con Geocoding API abilitata)
- Credenziali GLS Label Service (per upload spedizioni)

## License

Proprietario - Uso interno
