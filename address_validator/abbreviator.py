"""
Abbreviazione indirizzi per rispettare limite caratteri.
"""

import re
from typing import Optional

from .config import ABBREVIAZIONI, MAX_INDIRIZZO_LEN


def abbreviate(indirizzo: str, max_len: Optional[int] = None) -> str:
    """
    Abbrevia un indirizzo se supera la lunghezza massima.

    Applica abbreviazioni standard italiane per ridurre la lunghezza.

    Args:
        indirizzo: Indirizzo da abbreviare
        max_len: Lunghezza massima (default: MAX_INDIRIZZO_LEN)

    Returns:
        Indirizzo abbreviato se necessario, altrimenti originale
    """
    if max_len is None:
        max_len = MAX_INDIRIZZO_LEN

    if not indirizzo or len(indirizzo) <= max_len:
        return indirizzo

    result = indirizzo

    # Applica abbreviazioni in ordine di lunghezza decrescente
    # per evitare conflitti (es. "Strada Statale" prima di "Strada")
    sorted_abbrev = sorted(ABBREVIAZIONI.items(), key=lambda x: len(x[0]), reverse=True)

    for original, abbrev in sorted_abbrev:
        if len(result) <= max_len:
            break

        # Cerca e sostituisce (case insensitive, mantiene case originale)
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        result = pattern.sub(abbrev, result)

    # Se ancora troppo lungo, prova abbreviazioni aggiuntive
    if len(result) > max_len:
        result = _apply_additional_abbreviations(result)

    # Se ancora troppo lungo, tronca con indicatore
    if len(result) > max_len:
        result = result[: max_len - 1] + "."

    return result


def _apply_additional_abbreviations(indirizzo: str) -> str:
    """
    Applica abbreviazioni aggiuntive per casi particolari.

    Args:
        indirizzo: Indirizzo già parzialmente abbreviato

    Returns:
        Indirizzo con ulteriori abbreviazioni
    """
    result = indirizzo

    # Abbreviazioni numeri ordinali
    ordinal_map = {
        "Primo": "1°",
        "Prima": "1ª",
        "Secondo": "2°",
        "Seconda": "2ª",
        "Terzo": "3°",
        "Terza": "3ª",
        "Quarto": "4°",
        "Quarta": "4ª",
        "Quinto": "5°",
        "Quinta": "5ª",
    }

    for original, abbrev in ordinal_map.items():
        pattern = re.compile(re.escape(original), re.IGNORECASE)
        result = pattern.sub(abbrev, result)

    # Rimuovi articoli se non essenziali
    articles = [" del ", " della ", " dei ", " delle ", " degli ", " dello "]
    for article in articles:
        result = result.replace(article, " ")
        result = result.replace(article.title(), " ")

    # Riduci spazi multipli
    result = re.sub(r"\s+", " ", result).strip()

    return result


def needs_abbreviation(indirizzo: str, max_len: Optional[int] = None) -> bool:
    """
    Verifica se un indirizzo necessita di abbreviazione.

    Args:
        indirizzo: Indirizzo da verificare
        max_len: Lunghezza massima (default: MAX_INDIRIZZO_LEN)

    Returns:
        True se l'indirizzo supera la lunghezza massima
    """
    if max_len is None:
        max_len = MAX_INDIRIZZO_LEN

    return bool(indirizzo and len(indirizzo) > max_len)


def get_abbreviation_info(indirizzo: str, max_len: Optional[int] = None) -> dict:
    """
    Fornisce informazioni sull'abbreviazione applicata.

    Args:
        indirizzo: Indirizzo originale
        max_len: Lunghezza massima

    Returns:
        Dizionario con info sull'abbreviazione
    """
    if max_len is None:
        max_len = MAX_INDIRIZZO_LEN

    abbreviated = abbreviate(indirizzo, max_len)

    return {
        "originale": indirizzo,
        "abbreviato": abbreviated,
        "lunghezza_originale": len(indirizzo) if indirizzo else 0,
        "lunghezza_abbreviata": len(abbreviated) if abbreviated else 0,
        "abbreviato_applicato": indirizzo != abbreviated,
        "rispetta_limite": len(abbreviated) <= max_len if abbreviated else True,
    }
