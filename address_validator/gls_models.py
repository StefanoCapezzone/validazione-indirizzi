"""
Modelli dati per l'integrazione GLS Label Service API.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class GLSCredentials:
    """Credenziali per l'accesso all'API GLS."""

    sede: str
    codice_cliente: str
    password: str
    codice_contratto: str

    def is_valid(self) -> bool:
        """Verifica che tutte le credenziali siano presenti."""
        return all([self.sede, self.codice_cliente, self.password, self.codice_contratto])


@dataclass
class GLSParcel:
    """Dati di una spedizione GLS."""

    ragione_sociale: str
    indirizzo: str
    localita: str
    zipcode: str
    provincia: str
    colli: int = 1
    peso: float = 3.0
    note: str = ""
    email: str = ""
    cellulare: str = ""
    bda: str = ""  # Numero riferimento cliente

    # Campi opzionali aggiuntivi
    contrassegno: float = 0.0
    importo_assicurato: float = 0.0

    def __post_init__(self):
        """Valida e normalizza i dati."""
        # Tronca ragione sociale a 35 caratteri
        if len(self.ragione_sociale) > 35:
            self.ragione_sociale = self.ragione_sociale[:35]

        # Tronca indirizzo a 35 caratteri
        if len(self.indirizzo) > 35:
            self.indirizzo = self.indirizzo[:35]

        # Tronca note a 40 caratteri
        if len(self.note) > 40:
            self.note = self.note[:40]

        # Normalizza provincia a 2 caratteri
        if len(self.provincia) > 2:
            self.provincia = self.provincia[:2]
        self.provincia = self.provincia.upper()

        # Normalizza CAP
        self.zipcode = str(self.zipcode).strip().zfill(5)[:5]

    def to_dict(self) -> dict:
        """Converte in dizionario per la chiamata SOAP."""
        return {
            "RagioneSociale": self.ragione_sociale,
            "Indirizzo": self.indirizzo,
            "Localita": self.localita,
            "Zipcode": self.zipcode,
            "Provincia": self.provincia,
            "Colli": str(self.colli),
            "PesoReale": f"{self.peso:.2f}",
            "Note": self.note,
            "Email": self.email,
            "Cellulare": self.cellulare,
            "BDA": self.bda,
            "Contrassegno": f"{self.contrassegno:.2f}" if self.contrassegno > 0 else "",
            "ImportoAssicurato": f"{self.importo_assicurato:.2f}" if self.importo_assicurato > 0 else "",
        }


@dataclass
class GLSResponse:
    """Risposta dall'API GLS per una singola spedizione."""

    numero_spedizione: str = ""
    esito: str = ""  # OK, KO
    pdf_base64: str = ""
    error_message: str = ""
    bda: str = ""  # Riferimento originale

    @property
    def is_success(self) -> bool:
        """Verifica se la spedizione è stata creata con successo."""
        return self.esito.upper() == "OK" and bool(self.numero_spedizione)


@dataclass
class GLSUploadResult:
    """Risultato complessivo di un upload batch."""

    total: int = 0
    uploaded: int = 0
    skipped: int = 0
    failed: int = 0
    errors: list = field(default_factory=list)
    responses: list = field(default_factory=list)

    def add_success(self, response: GLSResponse):
        """Aggiunge una spedizione riuscita."""
        self.uploaded += 1
        self.responses.append(response)

    def add_skip(self, reason: str = ""):
        """Aggiunge una spedizione saltata."""
        self.skipped += 1
        if reason:
            self.errors.append(f"SKIP: {reason}")

    def add_failure(self, error: str, bda: str = ""):
        """Aggiunge una spedizione fallita."""
        self.failed += 1
        self.errors.append(f"ERRORE {bda}: {error}" if bda else f"ERRORE: {error}")

    @property
    def success_rate(self) -> float:
        """Percentuale di successo."""
        processed = self.uploaded + self.failed
        if processed == 0:
            return 0.0
        return (self.uploaded / processed) * 100

    def summary(self) -> str:
        """Genera un riepilogo testuale."""
        lines = [
            f"Totale righe: {self.total}",
            f"Caricate: {self.uploaded}",
            f"Saltate: {self.skipped}",
            f"Errori: {self.failed}",
        ]
        if self.uploaded + self.failed > 0:
            lines.append(f"Tasso successo: {self.success_rate:.1f}%")
        return "\n".join(lines)
