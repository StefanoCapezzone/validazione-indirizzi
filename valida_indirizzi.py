#!/usr/bin/env python3
"""
Validatore Indirizzi - Normalizza indirizzi usando Google Maps Geocoding API

Converte indirizzi nel formato: <via>, <civico>
- Massimo 35 caratteri
- CAP con 5 cifre (padding zeri)
- Provincia come sigla

Uso: python valida_indirizzi.py <file.xlsx> [--dry-run]
"""

import pandas as pd
import requests
import time
import sys
import re
from pathlib import Path
from datetime import datetime

# Configurazione
API_KEY = '***REMOVED***'
MAX_INDIRIZZO_LEN = 35
REQUESTS_PER_SECOND = 40  # Lasciamo margine sul limite di 50

# Abbreviazioni per ridurre lunghezza
ABBREVIAZIONI = [
    (r'\bViale\b', 'V.le'),
    (r'\bVIALE\b', 'V.LE'),
    (r'\bPiazza\b', 'P.za'),
    (r'\bPIAZZA\b', 'P.ZA'),
    (r'\bPiazzale\b', 'P.le'),
    (r'\bPIAZZALE\b', 'P.LE'),
    (r'\bCorso\b', 'C.so'),
    (r'\bCORSO\b', 'C.SO'),
    (r'\bLargo\b', 'L.go'),
    (r'\bLARGO\b', 'L.GO'),
    (r'\bStrada\b', 'Str.'),
    (r'\bSTRADA\b', 'STR.'),
    (r'\bVicolo\b', 'Vic.'),
    (r'\bVICOLO\b', 'VIC.'),
    (r'\bContrada\b', 'C.da'),
    (r'\bCONTRADA\b', 'C.DA'),
    (r'\bLocalità\b', 'Loc.'),
    (r'\bLOCALITÀ\b', 'LOC.'),
    (r'\bSan\b', 'S.'),
    (r'\bSAN\b', 'S.'),
    (r'\bSanta\b', 'S.'),
    (r'\bSANTA\b', 'S.'),
    (r'\bSanto\b', 'S.'),
    (r'\bSANTO\b', 'S.'),
    (r'\bGiovanni\b', 'G.'),
    (r'\bGIOVANNI\b', 'G.'),
    (r'\bGiuseppe\b', 'G.'),
    (r'\bGIUSEPPE\b', 'G.'),
    (r'\bFrancesco\b', 'F.'),
    (r'\bFRANCESCO\b', 'F.'),
    (r'\bStatale\b', 'Stat.'),
    (r'\bSTATALE\b', 'STAT.'),
    (r'\bNazionale\b', 'Naz.'),
    (r'\bNAZIONALE\b', 'NAZ.'),
    (r'\bProvinciale\b', 'Prov.'),
    (r'\bPROVINCIALE\b', 'PROV.'),
    # Nomi lunghi comuni
    (r'\bCamillo Benso Conte di Cavour\b', 'Cavour'),
    (r'\bFerdinando Stagno d\'Alcontres\b', 'F. Stagno d\'Alcontres'),
    (r'\bGaribaldi\b', 'Garibaldi'),
    (r'\bVittorio Emanuele\b', 'V. Emanuele'),
    (r'\bUmberto I\b', 'Umberto I'),
    (r'\bRe Umberto\b', 'Re Umberto'),
]


def abbrevia_indirizzo(indirizzo):
    """Applica abbreviazioni per ridurre la lunghezza dell'indirizzo"""
    result = indirizzo
    for pattern, replacement in ABBREVIAZIONI:
        if len(result) <= MAX_INDIRIZZO_LEN:
            break
        result = re.sub(pattern, replacement, result)
    return result


def geocode_google(indirizzo, citta, cap, provincia):
    """
    Geocodifica con Google Maps e restituisce indirizzo standardizzato.

    Returns:
        tuple: (indirizzo_formattato, status, indirizzo_completo_google, cap_corretto, comune_corretto)
    """
    # Costruisci query
    cap_str = str(cap).zfill(5) if pd.notna(cap) else ''
    query = f'{indirizzo}, {cap_str} {citta} {provincia}, Italia'

    url = 'https://maps.googleapis.com/maps/api/geocode/json'
    params = {
        'address': query,
        'key': API_KEY,
        'language': 'it',
        'region': 'it'
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        if data['status'] == 'OK':
            result = data['results'][0]
            components = {c['types'][0]: c for c in result['address_components']}

            route = components.get('route', {}).get('long_name', '')
            street_number = components.get('street_number', {}).get('long_name', '')
            postal_code = components.get('postal_code', {}).get('long_name', '')
            locality = components.get('locality', {}).get('long_name', '')
            admin_area_3 = components.get('administrative_area_level_3', {}).get('long_name', '')

            # Comune: preferisci locality, fallback su admin_area_3
            comune = locality or admin_area_3 or ''

            if route:
                if street_number:
                    formatted = f'{route}, {street_number}'
                else:
                    formatted = route

                # Abbrevia se troppo lungo
                if len(formatted) > MAX_INDIRIZZO_LEN:
                    formatted = abbrevia_indirizzo(formatted)

                return formatted, 'OK', result.get('formatted_address', ''), postal_code, comune
            else:
                return None, 'NO_ROUTE', result.get('formatted_address', ''), postal_code, comune
        else:
            return None, data['status'], None, None, None

    except requests.exceptions.Timeout:
        return None, 'TIMEOUT', None, None, None
    except Exception as e:
        return None, f'ERROR: {str(e)[:50]}', None, None, None


def correggi_cap(cap):
    """Corregge il CAP aggiungendo zeri iniziali se necessario"""
    if pd.isna(cap):
        return ''
    cap_str = str(cap).strip()
    # Rimuovi eventuali decimali (.0)
    if '.' in cap_str:
        cap_str = cap_str.split('.')[0]
    return cap_str.zfill(5)


def trova_colonne(df):
    """Trova le colonne rilevanti nel dataframe"""
    colonne = {}

    for col in df.columns:
        col_lower = str(col).lower().strip()
        if 'indirizzo' in col_lower and 'indirizzo' not in colonne:
            colonne['indirizzo'] = col
        elif col_lower in ['località', 'localita', 'comune'] or 'comune' in col_lower:
            colonne['citta'] = col
        elif 'cap' in col_lower:
            colonne['cap'] = col
        elif 'provincia' in col_lower:
            colonne['provincia'] = col

    return colonne


def processa_file(input_file, dry_run=False):
    """Processa un file Excel e valida gli indirizzi"""

    print(f"\n{'='*60}")
    print(f"File: {input_file}")
    print('='*60)

    # Leggi file
    df = pd.read_excel(input_file)
    print(f"Righe totali: {len(df)}")

    # Trova colonne
    colonne = trova_colonne(df)
    print(f"Colonne trovate: {colonne}")

    if 'indirizzo' not in colonne:
        print("ERRORE: Colonna indirizzo non trovata!")
        return None

    # Prepara colonne output
    col_ind = colonne['indirizzo']
    col_citta = colonne.get('citta', None)
    col_cap = colonne.get('cap', None)
    col_prov = colonne.get('provincia', None)

    # Crea colonne per i risultati
    df['_indirizzo_validato'] = ''
    df['_status'] = ''
    df['_indirizzo_google'] = ''
    df['_cap_corretto'] = ''
    df['_note'] = ''

    # Contatori
    ok_count = 0
    error_count = 0
    skip_count = 0
    troppo_lungo_count = 0

    # Processa ogni riga
    total = len(df)
    start_time = time.time()

    for idx, row in df.iterrows():
        indirizzo = row[col_ind] if pd.notna(row[col_ind]) else ''
        citta = row[col_citta] if col_citta and pd.notna(row[col_citta]) else ''
        cap = row[col_cap] if col_cap and pd.notna(row[col_cap]) else ''
        provincia = row[col_prov] if col_prov and pd.notna(row[col_prov]) else ''

        # Salta righe vuote
        if not indirizzo:
            df.at[idx, '_status'] = 'SKIP_EMPTY'
            skip_count += 1
            continue

        # Progress
        if (idx + 1) % 50 == 0 or idx == 0:
            elapsed = time.time() - start_time
            rate = (idx + 1) / elapsed if elapsed > 0 else 0
            eta = (total - idx - 1) / rate if rate > 0 else 0
            print(f"  Elaborazione: {idx+1}/{total} ({rate:.1f}/sec, ETA: {eta:.0f}s)")

        if dry_run:
            df.at[idx, '_status'] = 'DRY_RUN'
            continue

        # Geocodifica
        result, status, full_addr, cap_google, comune_google = geocode_google(
            indirizzo, citta, cap, provincia
        )

        df.at[idx, '_status'] = status

        if status == 'OK' and result:
            df.at[idx, '_indirizzo_validato'] = result
            df.at[idx, '_indirizzo_google'] = full_addr or ''
            df.at[idx, '_cap_corretto'] = cap_google or correggi_cap(cap)

            if len(result) > MAX_INDIRIZZO_LEN:
                df.at[idx, '_note'] = f'LUNGO ({len(result)} char)'
                troppo_lungo_count += 1

            ok_count += 1
        else:
            # Fallback: usa indirizzo originale con CAP corretto
            df.at[idx, '_indirizzo_validato'] = str(indirizzo)
            df.at[idx, '_cap_corretto'] = correggi_cap(cap)
            df.at[idx, '_indirizzo_google'] = full_addr or ''
            df.at[idx, '_note'] = f'ERRORE: {status}'
            error_count += 1

        # Rate limiting
        time.sleep(1.0 / REQUESTS_PER_SECOND)

    # Statistiche
    print(f"\n--- Risultati ---")
    print(f"OK: {ok_count}")
    print(f"Errori: {error_count}")
    print(f"Saltati: {skip_count}")
    print(f"Ancora > {MAX_INDIRIZZO_LEN} char: {troppo_lungo_count}")

    if dry_run:
        print("\n[DRY RUN - nessun file salvato]")
        return df

    # Salva file output
    input_path = Path(input_file)
    output_file = input_path.parent / f"{input_path.stem}_VALIDATO{input_path.suffix}"

    # Sostituisci colonne originali con valori validati
    df[col_ind] = df['_indirizzo_validato']
    if col_cap:
        df[col_cap] = df['_cap_corretto']

    # Salva
    df.to_excel(output_file, index=False)
    print(f"\nFile salvato: {output_file}")

    # Salva report errori
    errori = df[df['_status'] != 'OK']
    if len(errori) > 0:
        report_file = input_path.parent / f"{input_path.stem}_REPORT_ERRORI.csv"
        cols_report = [col_ind, '_indirizzo_validato', '_status', '_note', '_indirizzo_google']
        if col_citta:
            cols_report.insert(1, col_citta)
        errori[cols_report].to_csv(report_file, index=False)
        print(f"Report errori: {report_file}")

    return df


def main():
    if len(sys.argv) < 2:
        # Se nessun argomento, processa tutti i file xlsx nella directory
        files = list(Path('.').glob('*.xlsx'))
        files = [f for f in files if '_VALIDATO' not in f.name and '_REPORT' not in f.name]

        if not files:
            print("Uso: python valida_indirizzi.py <file.xlsx> [--dry-run]")
            print("Oppure: esegui nella directory con i file xlsx")
            sys.exit(1)

        print(f"Trovati {len(files)} file da processare:")
        for f in files:
            print(f"  - {f.name}")

        dry_run = '--dry-run' in sys.argv

        for f in files:
            processa_file(str(f), dry_run=dry_run)
    else:
        input_file = sys.argv[1]
        dry_run = '--dry-run' in sys.argv
        processa_file(input_file, dry_run=dry_run)

    print("\n" + "="*60)
    print("Elaborazione completata!")
    print("="*60)


if __name__ == '__main__':
    main()
