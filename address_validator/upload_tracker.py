"""
Tracciamento upload GLS per evitare duplicati.
Salva lo stato in un file JSON nella stessa cartella dei file Excel.
"""

import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional


class UploadTracker:
    """Tiene traccia delle righe già caricate su GLS."""

    TRACKER_FILENAME = ".gls_uploads.json"

    def __init__(self, base_path: Optional[str] = None):
        """
        Inizializza il tracker.

        Args:
            base_path: Cartella dove salvare il file di tracking.
                      Se None, usa la directory corrente.
        """
        if base_path:
            self.base_path = Path(base_path)
        else:
            self.base_path = Path.cwd()

        self.tracker_file = self.base_path / self.TRACKER_FILENAME
        self._data = self._load()

    def _load(self) -> dict:
        """Carica i dati dal file JSON."""
        if self.tracker_file.exists():
            try:
                with open(self.tracker_file, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {"uploads": {}, "history": []}
        return {"uploads": {}, "history": []}

    def _save(self):
        """Salva i dati nel file JSON."""
        try:
            with open(self.tracker_file, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except IOError as e:
            raise RuntimeError(f"Impossibile salvare tracker: {e}")

    def _generate_row_key(self, file_path: str, row_index: int, row_data: dict) -> str:
        """
        Genera una chiave univoca per una riga.

        La chiave è basata su:
        - Nome del file
        - Indice della riga
        - Hash dei dati principali (ragione sociale, indirizzo)

        Args:
            file_path: Percorso del file
            row_index: Indice della riga (0-based)
            row_data: Dati della riga

        Returns:
            Chiave univoca
        """
        file_name = Path(file_path).stem

        # Crea hash dei dati identificativi
        key_parts = [
            str(row_data.get("ragione_sociale", "")),
            str(row_data.get("indirizzo", "")),
            str(row_data.get("cap", "")),
        ]
        data_str = "|".join(key_parts).lower()
        data_hash = hashlib.md5(data_str.encode()).hexdigest()[:8]

        return f"{file_name}:{row_index}:{data_hash}"

    def is_uploaded(self, file_path: str, row_index: int, row_data: dict) -> bool:
        """
        Verifica se una riga è già stata caricata.

        Args:
            file_path: Percorso del file
            row_index: Indice della riga
            row_data: Dati della riga

        Returns:
            True se già caricata
        """
        key = self._generate_row_key(file_path, row_index, row_data)
        return key in self._data.get("uploads", {})

    def mark_uploaded(
        self,
        file_path: str,
        row_index: int,
        row_data: dict,
        shipment_id: str,
        response_data: Optional[dict] = None,
    ):
        """
        Segna una riga come caricata.

        Args:
            file_path: Percorso del file
            row_index: Indice della riga
            row_data: Dati della riga
            shipment_id: ID spedizione GLS
            response_data: Dati aggiuntivi dalla risposta
        """
        key = self._generate_row_key(file_path, row_index, row_data)

        upload_record = {
            "file": Path(file_path).name,
            "row": row_index,
            "shipment_id": shipment_id,
            "ragione_sociale": row_data.get("ragione_sociale", ""),
            "uploaded_at": datetime.now().isoformat(),
        }

        if response_data:
            upload_record["response"] = response_data

        self._data["uploads"][key] = upload_record

        # Aggiungi alla history
        self._data["history"].append({
            "key": key,
            "action": "upload",
            "timestamp": datetime.now().isoformat(),
            "shipment_id": shipment_id,
        })

        self._save()

    def get_upload_info(self, file_path: str, row_index: int, row_data: dict) -> Optional[dict]:
        """
        Ottiene le informazioni di upload per una riga.

        Args:
            file_path: Percorso del file
            row_index: Indice della riga
            row_data: Dati della riga

        Returns:
            Dict con info upload o None
        """
        key = self._generate_row_key(file_path, row_index, row_data)
        return self._data.get("uploads", {}).get(key)

    def get_file_uploads(self, file_path: str) -> list[dict]:
        """
        Ottiene tutte le righe caricate per un file.

        Args:
            file_path: Percorso del file

        Returns:
            Lista di record di upload
        """
        file_name = Path(file_path).stem
        results = []

        for key, record in self._data.get("uploads", {}).items():
            if key.startswith(f"{file_name}:"):
                results.append(record)

        return results

    def get_upload_history(self, limit: int = 100) -> list[dict]:
        """
        Ottiene la storia recente degli upload.

        Args:
            limit: Numero massimo di record

        Returns:
            Lista di record storici (più recenti prima)
        """
        history = self._data.get("history", [])
        return list(reversed(history[-limit:]))

    def count_uploaded(self, file_path: str) -> int:
        """
        Conta le righe già caricate per un file.

        Args:
            file_path: Percorso del file

        Returns:
            Numero di righe caricate
        """
        return len(self.get_file_uploads(file_path))

    def clear_file_uploads(self, file_path: str):
        """
        Rimuove i record di upload per un file.

        Args:
            file_path: Percorso del file
        """
        file_name = Path(file_path).stem
        keys_to_remove = [
            key for key in self._data.get("uploads", {})
            if key.startswith(f"{file_name}:")
        ]

        for key in keys_to_remove:
            del self._data["uploads"][key]

        # Aggiungi alla history
        if keys_to_remove:
            self._data["history"].append({
                "action": "clear_file",
                "file": file_name,
                "count": len(keys_to_remove),
                "timestamp": datetime.now().isoformat(),
            })

        self._save()

    def clear_all(self):
        """Rimuove tutti i record di upload."""
        count = len(self._data.get("uploads", {}))
        self._data = {"uploads": {}, "history": []}

        self._data["history"].append({
            "action": "clear_all",
            "count": count,
            "timestamp": datetime.now().isoformat(),
        })

        self._save()

    def get_stats(self) -> dict:
        """
        Ottiene statistiche globali.

        Returns:
            Dict con statistiche
        """
        uploads = self._data.get("uploads", {})

        # Conta per file
        files = {}
        for key, record in uploads.items():
            file_name = record.get("file", "unknown")
            files[file_name] = files.get(file_name, 0) + 1

        return {
            "total_uploads": len(uploads),
            "files": files,
            "history_entries": len(self._data.get("history", [])),
        }
