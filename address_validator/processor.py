"""
Orchestratore elaborazione file Excel.
"""

import os
from pathlib import Path
from typing import Optional

from tqdm import tqdm

from .abbreviator import abbreviate, needs_abbreviation
from .config import MAX_INDIRIZZO_LEN, SUGGERIMENTI_ERRORE
from .excel_io import read_excel, write_errors, write_validated
from .formats import FileFormat, format_name
from .geocoding import GeocodingService
from .models import Address, ValidationResult


class AddressProcessor:
    """Processore principale per validazione indirizzi."""

    def __init__(self, api_key: Optional[str] = None, verbose: bool = False):
        """
        Inizializza il processore.

        Args:
            api_key: API key Google Maps (opzionale, usa env var se non fornita)
            verbose: Se True, stampa informazioni dettagliate
        """
        self._api_key = api_key
        self._geocoding = None
        self.verbose = verbose

    @property
    def geocoding(self) -> GeocodingService:
        """Lazy initialization del servizio di geocoding."""
        if self._geocoding is None:
            self._geocoding = GeocodingService(self._api_key)
        return self._geocoding

    def process_file(
        self, file_path: str, output_dir: Optional[str] = None, dry_run: bool = False
    ) -> dict:
        """
        Elabora un file Excel completo.

        Args:
            file_path: Percorso del file da elaborare
            output_dir: Directory per i file di output (default: stessa del file)
            dry_run: Se True, non scrive i file di output

        Returns:
            Dizionario con statistiche elaborazione
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File non trovato: {file_path}")

        if output_dir:
            output_dir = Path(output_dir)
        else:
            output_dir = file_path.parent

        # Leggi file
        print(f"\n{'='*60}")
        print(f"Elaborazione: {file_path.name}")
        print(f"{'='*60}")

        df, file_format, column_mapping = read_excel(str(file_path))

        if file_format == FileFormat.UNKNOWN:
            raise ValueError(f"Formato file non riconosciuto: {file_path.name}")

        print(f"Formato rilevato: {format_name(file_format)}")
        print(f"Righe da elaborare: {len(df)}")
        print(f"Mapping colonne: {column_mapping}")

        # Estrai indirizzi
        addresses = self._extract_addresses(df, column_mapping, file_format)
        print(f"Indirizzi estratti: {len(addresses)}")

        if dry_run:
            print("\n[DRY RUN] Nessun file scritto")
            return {
                "file": str(file_path),
                "format": format_name(file_format),
                "total_rows": len(df),
                "addresses_extracted": len(addresses),
                "dry_run": True,
            }

        # Valida indirizzi
        results = self._validate_addresses(addresses)

        # Genera statistiche
        stats = self._compute_stats(results)
        self._print_stats(stats)

        # Scrivi output
        base_name = file_path.stem
        validated_path = output_dir / f"{base_name}_VALIDATO.xlsx"
        errors_path = output_dir / f"{base_name}_NON_VALIDATI.xlsx"

        write_validated(df, results, column_mapping, str(validated_path))
        print(f"\nFile validato: {validated_path.name}")

        error_results = [r for r in results if not r.is_valid]
        if error_results:
            write_errors(error_results, str(errors_path))
            print(f"File errori: {errors_path.name}")

        stats["output_validated"] = str(validated_path)
        stats["output_errors"] = str(errors_path) if error_results else None

        return stats

    def _extract_addresses(
        self, df, column_mapping: dict, file_format: FileFormat
    ) -> list[Address]:
        """Estrae oggetti Address dal DataFrame."""
        addresses = []

        # Determina offset per il numero riga (include header)
        header_offset = 2 if file_format == FileFormat.AGENZIE else 1

        for idx, row in df.iterrows():
            # Numero riga nel file originale (1-based, dopo header)
            row_number = idx + header_offset + 1

            # Estrai valori colonne
            indirizzo = str(row.get(column_mapping.get("indirizzo", ""), "") or "").strip()
            citta = str(row.get(column_mapping.get("citta", ""), "") or "").strip()
            cap = str(row.get(column_mapping.get("cap", ""), "") or "").strip()
            provincia = str(row.get(column_mapping.get("provincia", ""), "") or "").strip()

            # Normalizza CAP (rimuovi .0 se presente)
            if cap and "." in cap:
                cap = cap.split(".")[0]
            cap = cap.zfill(5) if cap.isdigit() else cap

            # Salta righe senza indirizzo
            if not indirizzo:
                continue

            addresses.append(
                Address(
                    row_number=row_number,
                    indirizzo=indirizzo,
                    citta=citta,
                    cap=cap,
                    provincia=provincia,
                    original_row=row.to_dict(),
                )
            )

        return addresses

    def _validate_addresses(self, addresses: list[Address]) -> list[ValidationResult]:
        """Valida tutti gli indirizzi con progress bar."""
        results = []

        with tqdm(total=len(addresses), desc="Validazione", unit="ind") as pbar:
            for address in addresses:
                result = self.geocoding.geocode_address(address)

                # Se valido, applica abbreviazione se necessario
                if result.is_valid and result.validated_address:
                    if needs_abbreviation(result.validated_address):
                        result.validated_address = abbreviate(result.validated_address)
                        if self.verbose:
                            print(f"  Abbreviato: {result.validated_address}")

                # Genera suggerimento per errori
                if not result.is_valid and not result.suggestion:
                    result.suggestion = self._generate_suggestion(
                        result.status, address
                    )

                results.append(result)
                pbar.update(1)

                if self.verbose:
                    status_icon = "✓" if result.is_valid else "✗"
                    tqdm.write(f"  {status_icon} Riga {address.row_number}: {result.status}")

        return results

    def _generate_suggestion(self, status: str, address: Address) -> str:
        """Genera suggerimento per un errore specifico."""
        # Usa suggerimenti predefiniti
        if status in SUGGERIMENTI_ERRORE:
            return SUGGERIMENTI_ERRORE[status]

        # Suggerimenti basati sul contenuto dell'indirizzo
        indirizzo_lower = address.indirizzo.lower()

        if "contrada" in indirizzo_lower or "c.da" in indirizzo_lower:
            return "Verificare indirizzo catastale o aggiungere riferimento via"

        if "localita" in indirizzo_lower or "loc." in indirizzo_lower:
            return "Aggiungere via e numero civico se disponibili"

        if "snc" in indirizzo_lower:
            return "Verificare se esiste numero civico"

        if "km" in indirizzo_lower:
            return "Verificare riferimento chilometrico o aggiungere via specifica"

        return "Verificare correttezza indirizzo"

    def _compute_stats(self, results: list[ValidationResult]) -> dict:
        """Calcola statistiche elaborazione."""
        total = len(results)
        valid = sum(1 for r in results if r.is_valid)
        invalid = total - valid

        # Raggruppa errori per status
        error_by_status = {}
        for r in results:
            if not r.is_valid:
                status = r.status
                error_by_status[status] = error_by_status.get(status, 0) + 1

        return {
            "total": total,
            "valid": valid,
            "invalid": invalid,
            "valid_percent": (valid / total * 100) if total > 0 else 0,
            "errors_by_status": error_by_status,
        }

    def _print_stats(self, stats: dict):
        """Stampa statistiche a console."""
        print(f"\n{'─'*40}")
        print("RIEPILOGO")
        print(f"{'─'*40}")
        print(f"Totale indirizzi:  {stats['total']}")
        print(f"Validati:          {stats['valid']} ({stats['valid_percent']:.1f}%)")
        print(f"Non validati:      {stats['invalid']}")

        if stats["errors_by_status"]:
            print(f"\nErrori per tipo:")
            for status, count in sorted(
                stats["errors_by_status"].items(), key=lambda x: -x[1]
            ):
                print(f"  {status}: {count}")


def process_directory(
    directory: str,
    pattern: str = "*.xlsx",
    output_dir: Optional[str] = None,
    api_key: Optional[str] = None,
    verbose: bool = False,
) -> list[dict]:
    """
    Elabora tutti i file Excel in una directory.

    Args:
        directory: Directory da elaborare
        pattern: Pattern glob per i file (default: *.xlsx)
        output_dir: Directory per output (default: stessa dei file)
        api_key: API key Google Maps
        verbose: Modalità verbosa

    Returns:
        Lista di statistiche per ogni file elaborato
    """
    directory = Path(directory)
    files = list(directory.glob(pattern))

    # Escludi file già elaborati
    files = [
        f
        for f in files
        if not f.stem.endswith("_VALIDATO") and not f.stem.endswith("_NON_VALIDATI")
    ]

    if not files:
        print(f"Nessun file trovato in {directory} con pattern {pattern}")
        return []

    print(f"Trovati {len(files)} file da elaborare")

    processor = AddressProcessor(api_key=api_key, verbose=verbose)
    all_stats = []

    for file_path in files:
        try:
            stats = processor.process_file(str(file_path), output_dir)
            all_stats.append(stats)
        except Exception as e:
            print(f"\nERRORE elaborando {file_path.name}: {e}")
            all_stats.append({"file": str(file_path), "error": str(e)})

    return all_stats
