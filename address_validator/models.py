"""
Modelli dati per il validatore di indirizzi.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class Address:
    """Rappresenta un indirizzo da validare."""

    row_number: int  # Riga nel file originale (1-based, include header)
    indirizzo: str
    citta: str
    cap: str
    provincia: str
    original_row: dict = field(default_factory=dict)  # Dati originali completi

    def to_full_address(self) -> str:
        """Restituisce l'indirizzo completo per la geocodifica."""
        parts = [self.indirizzo, self.cap, self.citta, self.provincia, "Italia"]
        return ", ".join(p for p in parts if p and str(p).strip())

    def __str__(self) -> str:
        return f"{self.indirizzo}, {self.cap} {self.citta} ({self.provincia})"


@dataclass
class ValidationResult:
    """Risultato della validazione di un indirizzo."""

    address: Address
    is_valid: bool
    validated_address: Optional[str] = None
    validated_cap: Optional[str] = None
    validated_citta: Optional[str] = None
    status: str = "PENDING"  # OK, NO_ROUTE, ZERO_RESULTS, COMUNE_DIVERSO, etc.
    error_reason: Optional[str] = None
    suggestion: Optional[str] = None
    raw_response: Optional[dict] = None  # Risposta grezza API per debug

    @property
    def row_number(self) -> int:
        """Numero riga nel file originale."""
        return self.address.row_number

    def __str__(self) -> str:
        if self.is_valid:
            return f"[OK] Riga {self.row_number}: {self.validated_address}"
        return f"[{self.status}] Riga {self.row_number}: {self.error_reason}"
