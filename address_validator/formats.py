"""
Rilevamento formato file Excel e mapping colonne.
"""

from enum import Enum
from typing import Optional
import pandas as pd


class FileFormat(Enum):
    """Formati file supportati."""

    OLD_LAYOUT = "old"
    NEW_LAYOUT = "new"
    AGENZIE = "agenzie"
    UNKNOWN = "unknown"


# Definizione colonne per ogni formato
COLUMN_MAPPINGS = {
    FileFormat.OLD_LAYOUT: {
        "indirizzo": "Indirizzo",
        "citta": "Località",
        "cap": "Cap",
        "provincia": "Provincia",
    },
    FileFormat.NEW_LAYOUT: {
        "indirizzo": "Indirizzo",
        "citta": "Comune",
        "cap": "CAP",
        "provincia": "Provincia",
    },
    FileFormat.AGENZIE: {
        "indirizzo": "Indirizzo",
        "citta": "Città",
        "cap": "CAP",
        "provincia": "Provincia",
    },
}

# Mapping colonne aggiuntive per upload GLS (per formato)
GLS_COLUMN_MAPPINGS = {
    FileFormat.OLD_LAYOUT: {
        "ragione_sociale": "Ragione sociale negozio",
        "progressivo": "Unnamed: 0",  # Prima colonna (numero riga)
        "telefono_fisso": "Telefono",
        "telefono_cell": "cellulare",
        "email": "E-Mail",
        "indicazioni": "Centro comm.le / Indicazioni",
    },
    FileFormat.NEW_LAYOUT: {
        "ragione_sociale": "RAGIONE SOCIALE",
        "progressivo": "PROGRESSIVO",
        "telefono_fisso": "TELEFONO",
        "telefono_cell": "CELLULARE",
        "email": "MAIL PEC",
        "indicazioni": "PRESSO CC",
    },
    FileFormat.AGENZIE: {
        "ragione_sociale": "RAGIONE SOCIALE",
        "progressivo": "Unnamed: 0",  # Prima colonna
        "telefono_fisso": "",  # Non presente
        "telefono_cell": "Cellulare",
        "email": "E-mail",
        "indicazioni": "NOTE X CONSEGNE",
    },
}


def detect_format(file_path: str) -> tuple[FileFormat, int, dict]:
    """
    Rileva il formato del file Excel.

    Args:
        file_path: Percorso del file Excel

    Returns:
        Tupla con (formato, header_row, mapping_colonne)
    """
    # Prova prima con header a riga 0
    df_row0 = pd.read_excel(file_path, header=0, nrows=5)
    columns_row0 = set(df_row0.columns.astype(str))

    # Prova con header a riga 1 (per formato AGENZIE)
    df_row1 = pd.read_excel(file_path, header=1, nrows=5)
    columns_row1 = set(df_row1.columns.astype(str))

    # Verifica formato AGENZIE (header riga 1)
    if _is_agenzie_format(columns_row1):
        mapping = _find_column_mapping(df_row1.columns.tolist(), FileFormat.AGENZIE)
        return FileFormat.AGENZIE, 1, mapping

    # Verifica formato OLD Layout (ha colonna "Layout")
    if _is_old_layout_format(columns_row0):
        mapping = _find_column_mapping(df_row0.columns.tolist(), FileFormat.OLD_LAYOUT)
        return FileFormat.OLD_LAYOUT, 0, mapping

    # Verifica formato NEW Layout (ha colonna "LOCATION NEGOZIO")
    if _is_new_layout_format(columns_row0):
        mapping = _find_column_mapping(df_row0.columns.tolist(), FileFormat.NEW_LAYOUT)
        return FileFormat.NEW_LAYOUT, 0, mapping

    # Se non riconosciuto, prova a inferire dal mapping colonne
    for fmt in [FileFormat.OLD_LAYOUT, FileFormat.NEW_LAYOUT]:
        mapping = _find_column_mapping(df_row0.columns.tolist(), fmt)
        if mapping:
            return fmt, 0, mapping

    return FileFormat.UNKNOWN, 0, {}


def _is_agenzie_format(columns: set) -> bool:
    """Verifica se è formato AGENZIE (ha colonne Area e N° Point serviti)."""
    columns_lower = {str(c).lower() for c in columns}
    markers = {"area", "n° point serviti"}
    return bool(markers & columns_lower)


def _is_old_layout_format(columns: set) -> bool:
    """Verifica se è formato OLD Layout (ha colonna Layout)."""
    columns_lower = {str(c).lower() for c in columns}
    return "layout" in columns_lower


def _is_new_layout_format(columns: set) -> bool:
    """Verifica se è formato NEW Layout (ha colonna LOCATION NEGOZIO)."""
    columns_lower = {str(c).lower() for c in columns}
    return "location negozio" in columns_lower


def _find_column_mapping(columns: list, format_type: FileFormat) -> dict:
    """
    Trova il mapping tra colonne logiche e colonne reali nel file.

    Args:
        columns: Lista colonne del DataFrame
        format_type: Tipo di formato

    Returns:
        Dizionario con mapping {nome_logico: nome_colonna_reale}
    """
    if format_type not in COLUMN_MAPPINGS:
        return {}

    expected = COLUMN_MAPPINGS[format_type]
    mapping = {}
    columns_lower = {str(c).lower(): c for c in columns}

    for logical_name, expected_col in expected.items():
        # Cerca corrispondenza esatta (case insensitive)
        if expected_col.lower() in columns_lower:
            mapping[logical_name] = columns_lower[expected_col.lower()]
        else:
            # Cerca corrispondenza parziale
            for col_lower, col_real in columns_lower.items():
                if expected_col.lower() in col_lower or col_lower in expected_col.lower():
                    mapping[logical_name] = col_real
                    break

    # Verifica che abbiamo trovato tutte le colonne necessarie
    if set(mapping.keys()) == set(expected.keys()):
        return mapping

    return {}


def get_column_mapping(df: pd.DataFrame, format_type: FileFormat) -> dict:
    """
    Ottiene il mapping colonne per un DataFrame già caricato.

    Args:
        df: DataFrame caricato
        format_type: Tipo di formato

    Returns:
        Dizionario con mapping colonne
    """
    return _find_column_mapping(df.columns.tolist(), format_type)


def format_name(fmt: FileFormat) -> str:
    """Restituisce nome leggibile del formato."""
    names = {
        FileFormat.OLD_LAYOUT: "OLD Layout",
        FileFormat.NEW_LAYOUT: "NEW Layout",
        FileFormat.AGENZIE: "AGENZIE",
        FileFormat.UNKNOWN: "Sconosciuto",
    }
    return names.get(fmt, "Sconosciuto")


def get_gls_column_mapping(df: pd.DataFrame, format_type: FileFormat) -> dict:
    """
    Ottiene il mapping colonne GLS per un DataFrame già caricato.

    Args:
        df: DataFrame caricato
        format_type: Tipo di formato

    Returns:
        Dizionario con mapping colonne GLS {nome_logico: nome_colonna_reale}
    """
    if format_type not in GLS_COLUMN_MAPPINGS:
        return {}

    expected = GLS_COLUMN_MAPPINGS[format_type]
    mapping = {}
    columns_lower = {str(c).lower(): c for c in df.columns}

    for logical_name, expected_col in expected.items():
        if not expected_col:  # Campo non previsto per questo formato
            mapping[logical_name] = None
            continue

        # Cerca corrispondenza esatta (case insensitive)
        if expected_col.lower() in columns_lower:
            mapping[logical_name] = columns_lower[expected_col.lower()]
        else:
            # Cerca corrispondenza parziale
            found = False
            for col_lower, col_real in columns_lower.items():
                if expected_col.lower() in col_lower or col_lower in expected_col.lower():
                    mapping[logical_name] = col_real
                    found = True
                    break
            if not found:
                mapping[logical_name] = None

    return mapping
