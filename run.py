#!/usr/bin/env python3
"""
Script di avvio rapido per il validatore di indirizzi.

Uso:
    python run.py file.xlsx              # Valida singolo file
    python run.py                        # Valida tutti i .xlsx
    python run.py --dry-run file.xlsx    # Simula senza scrivere
    python run.py --help                 # Mostra aiuto
"""

import sys

from address_validator.main import main

if __name__ == "__main__":
    main()
