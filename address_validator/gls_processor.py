"""
Orchestratore per l'upload delle spedizioni su GLS.
"""

import logging
from pathlib import Path
from typing import Callable, Optional

import pandas as pd

from .config import GLS_MAX_PARCELS_PER_BATCH
from .formats import FileFormat, detect_format, get_gls_column_mapping, get_column_mapping
from .gls_client import GLSClient, GLSClientError
from .gls_models import GLSCredentials, GLSParcel, GLSUploadResult
from .upload_tracker import UploadTracker

logger = logging.getLogger(__name__)


class GLSProcessor:
    """Processa file Excel validati e carica le spedizioni su GLS."""

    def __init__(
        self,
        credentials: GLSCredentials,
        skip_uploaded: bool = True,
        progress_callback: Optional[Callable[[int, int, str], None]] = None,
    ):
        """
        Inizializza il processore GLS.

        Args:
            credentials: Credenziali GLS
            skip_uploaded: Se saltare le righe già caricate
            progress_callback: Callback per aggiornare il progresso (current, total, message)
        """
        self.client = GLSClient(credentials)
        self.skip_uploaded = skip_uploaded
        self.progress_callback = progress_callback
        self._tracker: Optional[UploadTracker] = None

    def _get_tracker(self, file_path: str) -> UploadTracker:
        """Ottiene il tracker per la cartella del file."""
        folder = Path(file_path).parent
        if self._tracker is None or self._tracker.base_path != folder:
            self._tracker = UploadTracker(str(folder))
        return self._tracker

    def _report_progress(self, current: int, total: int, message: str):
        """Riporta il progresso se c'è un callback."""
        if self.progress_callback:
            self.progress_callback(current, total, message)

    def detect_file_format(self, file_path: str) -> tuple[FileFormat, int]:
        """
        Rileva il formato di un file validato.

        Args:
            file_path: Percorso del file

        Returns:
            Tupla (formato, header_row)
        """
        fmt, header_row, _ = detect_format(file_path)
        return fmt, header_row

    def get_default_parcel_config(self, file_path: str) -> dict:
        """
        Determina configurazione colli/peso default basata sul nome file.

        Args:
            file_path: Percorso del file

        Returns:
            Dict con colli e peso
        """
        file_name = Path(file_path).stem.upper()

        if "OLD" in file_name:
            return {"colli": 1, "peso": 3.0}
        elif "NEW" in file_name:
            return {"colli": 2, "peso": 3.0}
        else:
            # AGENZIE o altro - richiede input utente
            return {"colli": None, "peso": None}

    def process_file(
        self,
        file_path: str,
        colli: int = 1,
        peso: float = 3.0,
        generate_pdf: bool = False,
        close_workday: bool = False,
    ) -> GLSUploadResult:
        """
        Processa un file validato e carica le spedizioni su GLS.

        Args:
            file_path: Percorso del file _VALIDATO.xlsx
            colli: Numero colli per spedizione
            peso: Peso per spedizione (kg)
            generate_pdf: Se generare le etichette PDF
            close_workday: Se chiamare CloseWorkDay alla fine

        Returns:
            GLSUploadResult con statistiche
        """
        result = GLSUploadResult()
        tracker = self._get_tracker(file_path)

        # Rileva formato e carica file
        fmt, header_row, col_mapping = detect_format(file_path)
        if fmt == FileFormat.UNKNOWN:
            result.add_failure("Formato file non riconosciuto")
            return result

        df = pd.read_excel(file_path, header=header_row)
        result.total = len(df)

        # Ottieni mapping colonne
        address_mapping = get_column_mapping(df, fmt)
        gls_mapping = get_gls_column_mapping(df, fmt)

        self._report_progress(0, result.total, f"Elaborazione {Path(file_path).name}")

        # Prepara le spedizioni
        parcels_to_upload = []
        row_indices = []

        for idx, row in df.iterrows():
            row_data = self._extract_row_data(row, address_mapping, gls_mapping, fmt)

            # Verifica se già caricata
            if self.skip_uploaded and tracker.is_uploaded(file_path, idx, row_data):
                result.add_skip(f"Riga {idx} già caricata")
                continue

            # Crea il parcel
            parcel = self._create_parcel(row_data, colli, peso, fmt)
            if parcel:
                parcels_to_upload.append(parcel)
                row_indices.append((idx, row_data))
            else:
                result.add_failure("Dati insufficienti", str(idx))

        # Upload in batch
        if parcels_to_upload:
            self._upload_batches(
                parcels_to_upload,
                row_indices,
                file_path,
                result,
                tracker,
                generate_pdf,
            )

        # Close workday se richiesto
        if close_workday and result.uploaded > 0:
            self._report_progress(result.total, result.total, "Chiusura giornata...")
            try:
                close_result = self.client.close_work_day()
                if not close_result.get("success"):
                    result.errors.append(f"CloseWorkDay: {close_result.get('error')}")
            except GLSClientError as e:
                result.errors.append(f"CloseWorkDay fallito: {e}")

        self._report_progress(result.total, result.total, "Completato")
        return result

    def _extract_row_data(
        self,
        row: pd.Series,
        address_mapping: dict,
        gls_mapping: dict,
        fmt: FileFormat,
    ) -> dict:
        """Estrae i dati rilevanti da una riga."""
        data = {}

        # Dati indirizzo (dai file validati, le colonne sono standardizzate)
        data["indirizzo"] = self._get_value(row, "Indirizzo Validato") or self._get_value(
            row, address_mapping.get("indirizzo")
        )
        data["cap"] = self._get_value(row, "CAP Validato") or self._get_value(
            row, address_mapping.get("cap")
        )
        data["citta"] = self._get_value(row, "Città Validata") or self._get_value(
            row, address_mapping.get("citta")
        )
        data["provincia"] = self._get_value(row, address_mapping.get("provincia"))

        # Dati GLS specifici
        data["ragione_sociale"] = self._get_value(row, gls_mapping.get("ragione_sociale"))
        data["progressivo"] = self._get_value(row, gls_mapping.get("progressivo"))
        data["telefono_fisso"] = self._get_value(row, gls_mapping.get("telefono_fisso"))
        data["telefono_cell"] = self._get_value(row, gls_mapping.get("telefono_cell"))
        data["email"] = self._get_value(row, gls_mapping.get("email"))
        data["indicazioni"] = self._get_value(row, gls_mapping.get("indicazioni"))

        return data

    def _get_value(self, row: pd.Series, col_name: Optional[str]) -> str:
        """Estrae un valore da una riga, gestendo None e NaN."""
        if col_name is None:
            return ""
        try:
            value = row.get(col_name, "")
            if pd.isna(value):
                return ""
            return str(value).strip()
        except (KeyError, TypeError):
            return ""

    def _create_parcel(
        self, row_data: dict, colli: int, peso: float, fmt: FileFormat
    ) -> Optional[GLSParcel]:
        """Crea un GLSParcel dai dati estratti."""
        # Verifica dati minimi
        if not row_data.get("ragione_sociale") or not row_data.get("indirizzo"):
            return None

        # Costruisci le note
        note = self._build_note(row_data, fmt)

        # Telefono: preferisci cellulare
        cellulare = row_data.get("telefono_cell") or row_data.get("telefono_fisso") or ""

        # BDA (riferimento): usa il progressivo
        bda = str(row_data.get("progressivo", ""))

        return GLSParcel(
            ragione_sociale=row_data["ragione_sociale"],
            indirizzo=row_data["indirizzo"],
            localita=row_data.get("citta", ""),
            zipcode=row_data.get("cap", ""),
            provincia=row_data.get("provincia", ""),
            colli=colli,
            peso=peso,
            note=note,
            email=row_data.get("email", ""),
            cellulare=cellulare,
            bda=bda,
        )

    def _build_note(self, row_data: dict, fmt: FileFormat) -> str:
        """
        Costruisce il campo Note (max 40 caratteri).

        Formato: "progressivo - telefono - indicazioni"
        """
        parts = []

        # Progressivo
        progressivo = str(row_data.get("progressivo", "")).strip()
        if progressivo:
            parts.append(progressivo)

        # Telefono (preferisci cellulare)
        telefono = row_data.get("telefono_cell") or row_data.get("telefono_fisso") or ""
        if telefono:
            # Rimuovi prefisso internazionale e spazi
            telefono = telefono.replace("+39", "").replace(" ", "").strip()
            if telefono:
                parts.append(telefono)

        # Indicazioni
        indicazioni = str(row_data.get("indicazioni", "")).strip()
        if indicazioni:
            parts.append(indicazioni)

        note = " - ".join(parts)

        # Tronca a 40 caratteri
        if len(note) > 40:
            note = note[:40]

        return note

    def _upload_batches(
        self,
        parcels: list[GLSParcel],
        row_indices: list[tuple],
        file_path: str,
        result: GLSUploadResult,
        tracker: UploadTracker,
        generate_pdf: bool,
    ):
        """Carica le spedizioni in batch."""
        total_parcels = len(parcels)
        processed = 0

        for batch_start in range(0, total_parcels, GLS_MAX_PARCELS_PER_BATCH):
            batch_end = min(batch_start + GLS_MAX_PARCELS_PER_BATCH, total_parcels)
            batch = parcels[batch_start:batch_end]
            batch_indices = row_indices[batch_start:batch_end]

            self._report_progress(
                processed + result.skipped,
                result.total,
                f"Upload batch {batch_start // GLS_MAX_PARCELS_PER_BATCH + 1}...",
            )

            try:
                responses = self.client.add_parcels(batch, generate_pdf)

                for i, response in enumerate(responses):
                    idx, row_data = batch_indices[i]

                    if response.is_success:
                        result.add_success(response)
                        tracker.mark_uploaded(
                            file_path,
                            idx,
                            row_data,
                            response.numero_spedizione,
                            {"esito": response.esito},
                        )
                    else:
                        result.add_failure(
                            response.error_message or "Errore sconosciuto",
                            response.bda,
                        )

                processed += len(batch)

            except GLSClientError as e:
                logger.error(f"Errore batch upload: {e}")
                for idx, row_data in batch_indices:
                    result.add_failure(str(e), str(idx))
                processed += len(batch)

    def test_credentials(self) -> tuple[bool, str]:
        """
        Testa le credenziali GLS.

        Returns:
            Tupla (successo, messaggio)
        """
        try:
            if self.client.test_connection():
                return True, "Connessione riuscita"
            else:
                return False, "Connessione fallita"
        except GLSClientError as e:
            return False, str(e)

    def count_pending_uploads(self, file_path: str) -> tuple[int, int]:
        """
        Conta le righe da caricare e quelle già caricate.

        Args:
            file_path: Percorso del file

        Returns:
            Tupla (pending, already_uploaded)
        """
        tracker = self._get_tracker(file_path)
        fmt, header_row, _ = detect_format(file_path)

        if fmt == FileFormat.UNKNOWN:
            return 0, 0

        df = pd.read_excel(file_path, header=header_row)
        address_mapping = get_column_mapping(df, fmt)
        gls_mapping = get_gls_column_mapping(df, fmt)

        pending = 0
        uploaded = 0

        for idx, row in df.iterrows():
            row_data = self._extract_row_data(row, address_mapping, gls_mapping, fmt)
            if tracker.is_uploaded(file_path, idx, row_data):
                uploaded += 1
            else:
                pending += 1

        return pending, uploaded
