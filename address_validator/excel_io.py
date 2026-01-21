"""
Lettura e scrittura file Excel.
"""

from pathlib import Path
from typing import Optional

import pandas as pd

from .formats import FileFormat, detect_format, get_column_mapping
from .models import ValidationResult


def read_excel(file_path: str) -> tuple[pd.DataFrame, FileFormat, dict]:
    """
    Legge un file Excel con rilevamento automatico del formato.

    Args:
        file_path: Percorso del file Excel

    Returns:
        Tupla con (DataFrame, formato_rilevato, mapping_colonne)
    """
    # Rileva formato
    file_format, header_row, column_mapping = detect_format(file_path)

    # Leggi file con header corretto
    df = pd.read_excel(file_path, header=header_row)

    # Se mapping non trovato durante detect, prova di nuovo
    if not column_mapping:
        column_mapping = get_column_mapping(df, file_format)

    return df, file_format, column_mapping


def write_validated(
    df: pd.DataFrame,
    results: list[ValidationResult],
    column_mapping: dict,
    output_path: str,
):
    """
    Scrive il file validato.

    Per gli indirizzi validati: sostituisce con indirizzo validato
    Per gli indirizzi non validati: mantiene l'indirizzo ORIGINALE

    Args:
        df: DataFrame originale
        results: Lista risultati validazione
        column_mapping: Mapping colonne
        output_path: Percorso file output
    """
    # Crea copia del DataFrame
    df_output = df.copy()

    # Crea dizionario risultati per indice riga
    # L'indice del DataFrame corrisponde all'indice nella lista results
    results_by_idx = {}
    for result in results:
        # Trova l'indice nel DataFrame basandosi sui dati originali
        for idx, row in df.iterrows():
            indirizzo_col = column_mapping.get("indirizzo", "")
            if indirizzo_col and row.get(indirizzo_col) == result.address.original_row.get(indirizzo_col):
                # Verifica anche CAP per evitare duplicati
                cap_col = column_mapping.get("cap", "")
                if cap_col:
                    original_cap = str(row.get(cap_col, "")).replace(".0", "")
                    result_cap = str(result.address.original_row.get(cap_col, "")).replace(".0", "")
                    if original_cap == result_cap:
                        results_by_idx[idx] = result
                        break
                else:
                    results_by_idx[idx] = result
                    break

    # Applica modifiche solo per indirizzi validati
    indirizzo_col = column_mapping.get("indirizzo", "")
    cap_col = column_mapping.get("cap", "")

    for idx, result in results_by_idx.items():
        if result.is_valid:
            # Aggiorna indirizzo validato
            if indirizzo_col and result.validated_address:
                df_output.at[idx, indirizzo_col] = result.validated_address
            # Aggiorna CAP se diverso
            if cap_col and result.validated_cap:
                df_output.at[idx, cap_col] = result.validated_cap
        # Se non valido, l'indirizzo originale rimane invariato (già presente in df_output)

    # Scrivi file
    df_output.to_excel(output_path, index=False)


def write_errors(results: list[ValidationResult], output_path: str):
    """
    Scrive il file degli errori con dettagli e suggerimenti.

    Colonne:
    - Riga: numero riga nel file originale
    - Indirizzo Originale: indirizzo come inserito
    - Città: città/comune
    - CAP: codice postale
    - Provincia: sigla provincia
    - Errore: tipo di errore
    - Motivo: descrizione errore
    - Suggerimento: come correggere

    Args:
        results: Lista risultati (solo errori)
        output_path: Percorso file output
    """
    error_data = []

    for result in results:
        if not result.is_valid:
            error_data.append(
                {
                    "Riga": result.address.row_number,
                    "Indirizzo Originale": result.address.indirizzo,
                    "Città": result.address.citta,
                    "CAP": result.address.cap,
                    "Provincia": result.address.provincia,
                    "Errore": result.status,
                    "Motivo": result.error_reason or "",
                    "Suggerimento": result.suggestion or "",
                }
            )

    df_errors = pd.DataFrame(error_data)

    # Ordina per numero riga
    if not df_errors.empty:
        df_errors = df_errors.sort_values("Riga")

    # Scrivi con formattazione
    with pd.ExcelWriter(output_path, engine="openpyxl") as writer:
        df_errors.to_excel(writer, index=False, sheet_name="Errori")

        # Adatta larghezza colonne
        worksheet = writer.sheets["Errori"]
        for column in worksheet.columns:
            max_length = 0
            column_letter = column[0].column_letter
            for cell in column:
                try:
                    if len(str(cell.value)) > max_length:
                        max_length = len(str(cell.value))
                except:
                    pass
            adjusted_width = min(max_length + 2, 50)
            worksheet.column_dimensions[column_letter].width = adjusted_width


def find_excel_files(
    directory: str, exclude_validated: bool = True
) -> list[Path]:
    """
    Trova tutti i file Excel in una directory.

    Args:
        directory: Directory da cercare
        exclude_validated: Se True, esclude file già elaborati

    Returns:
        Lista di percorsi file
    """
    directory = Path(directory)
    files = list(directory.glob("*.xlsx"))

    if exclude_validated:
        files = [
            f
            for f in files
            if not f.stem.endswith("_VALIDATO")
            and not f.stem.endswith("_NON_VALIDATI")
        ]

    return sorted(files)
