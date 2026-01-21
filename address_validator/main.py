"""
Entry point CLI per il validatore di indirizzi.
"""

import argparse
import os
import sys
from pathlib import Path

from . import __version__
from .config import API_KEY
from .excel_io import find_excel_files
from .processor import AddressProcessor, process_directory


def main():
    """Entry point principale."""
    parser = argparse.ArgumentParser(
        description="Validatore indirizzi da file Excel con Google Maps API",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  %(prog)s file.xlsx                    Valida un singolo file
  %(prog)s                              Valida tutti i file .xlsx nella directory corrente
  %(prog)s --dry-run file.xlsx          Simula elaborazione senza scrivere output
  %(prog)s -v file.xlsx                 Modalità verbosa
  %(prog)s --list                       Elenca file da elaborare

Formati supportati:
  - OLD Layout: header riga 0, colonna "Layout" presente
  - NEW Layout: header riga 0, colonna "LOCATION NEGOZIO" presente
  - AGENZIE: header riga 1, colonne "Area" e "N° Point serviti" presenti

Output:
  - {nome}_VALIDATO.xlsx      File con indirizzi validati (errori invariati)
  - {nome}_NON_VALIDATI.xlsx  Dettaglio errori con suggerimenti
        """,
    )

    parser.add_argument(
        "file",
        nargs="?",
        help="File Excel da elaborare (se omesso, elabora tutti i .xlsx)",
    )

    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simula elaborazione senza scrivere file di output",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Mostra informazioni dettagliate durante l'elaborazione",
    )

    parser.add_argument(
        "--api-key",
        help="API key Google Maps (default: variabile GOOGLE_MAPS_API_KEY)",
    )

    parser.add_argument(
        "--output-dir", "-o",
        help="Directory per i file di output (default: stessa del file input)",
    )

    parser.add_argument(
        "--list",
        action="store_true",
        help="Elenca i file che verrebbero elaborati senza eseguire",
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    args = parser.parse_args()

    # Verifica API key
    api_key = args.api_key or API_KEY
    if not api_key and not args.list and not args.dry_run:
        print("ERRORE: API key Google Maps richiesta.")
        print("Imposta la variabile d'ambiente GOOGLE_MAPS_API_KEY oppure usa --api-key")
        sys.exit(1)

    # Modalità lista
    if args.list:
        files = find_excel_files(".")
        if files:
            print(f"File da elaborare ({len(files)}):")
            for f in files:
                print(f"  - {f.name}")
        else:
            print("Nessun file Excel trovato nella directory corrente")
        sys.exit(0)

    # Elaborazione singolo file
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERRORE: File non trovato: {args.file}")
            sys.exit(1)

        try:
            processor = AddressProcessor(api_key=api_key, verbose=args.verbose)
            stats = processor.process_file(
                str(file_path),
                output_dir=args.output_dir,
                dry_run=args.dry_run,
            )

            if not args.dry_run:
                print(f"\nElaborazione completata!")
                if stats.get("output_validated"):
                    print(f"  Output: {Path(stats['output_validated']).name}")
                if stats.get("output_errors"):
                    print(f"  Errori: {Path(stats['output_errors']).name}")

        except Exception as e:
            print(f"ERRORE: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)

    # Elaborazione tutti i file
    else:
        files = find_excel_files(".")
        if not files:
            print("Nessun file Excel trovato nella directory corrente")
            print("Usa: python -m address_validator file.xlsx")
            sys.exit(0)

        print(f"Trovati {len(files)} file da elaborare")

        if args.dry_run:
            print("\n[DRY RUN] Simulazione elaborazione:")
            for f in files:
                print(f"  - {f.name}")
            sys.exit(0)

        try:
            all_stats = process_directory(
                ".",
                output_dir=args.output_dir,
                api_key=api_key,
                verbose=args.verbose,
            )

            # Riepilogo finale
            print(f"\n{'='*60}")
            print("RIEPILOGO FINALE")
            print(f"{'='*60}")

            total_valid = 0
            total_invalid = 0
            for stats in all_stats:
                if "error" not in stats:
                    total_valid += stats.get("valid", 0)
                    total_invalid += stats.get("invalid", 0)
                    print(f"  {Path(stats['file']).name}: {stats.get('valid', 0)} OK, {stats.get('invalid', 0)} errori")
                else:
                    print(f"  {Path(stats['file']).name}: ERRORE - {stats['error']}")

            print(f"\nTotale: {total_valid} validati, {total_invalid} errori")

        except Exception as e:
            print(f"ERRORE: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            sys.exit(1)


if __name__ == "__main__":
    main()
