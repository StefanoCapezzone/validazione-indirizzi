"""
Servizio di geocodifica con Google Maps API.
"""

import re
import time
from typing import Optional

import requests

from .config import API_KEY, REQUESTS_PER_SECOND, SUGGERIMENTI_ERRORE
from .models import Address, ValidationResult


class GeocodingService:
    """Servizio per geocodifica indirizzi con Google Maps API."""

    GEOCODE_URL = "https://maps.googleapis.com/maps/api/geocode/json"

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or API_KEY
        if not self.api_key:
            raise ValueError(
                "API key Google Maps richiesta. "
                "Imposta GOOGLE_MAPS_API_KEY come variabile d'ambiente."
            )
        self._last_request_time = 0
        self._request_interval = 1.0 / REQUESTS_PER_SECOND

    def _rate_limit(self):
        """Applica rate limiting tra le richieste."""
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_interval:
            time.sleep(self._request_interval - elapsed)
        self._last_request_time = time.time()

    def geocode_address(self, address: Address) -> ValidationResult:
        """
        Geocodifica un indirizzo usando Google Maps API.

        Args:
            address: Oggetto Address da validare

        Returns:
            ValidationResult con esito validazione
        """
        self._rate_limit()

        full_address = address.to_full_address()

        try:
            response = requests.get(
                self.GEOCODE_URL,
                params={"address": full_address, "key": self.api_key, "language": "it"},
                timeout=10,
            )
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            return ValidationResult(
                address=address,
                is_valid=False,
                status="REQUEST_ERROR",
                error_reason=f"Errore richiesta API: {str(e)}",
                suggestion="Verificare connessione internet e riprovare",
            )

        status = data.get("status", "UNKNOWN_ERROR")

        if status != "OK":
            return self._handle_error_status(address, status, data)

        results = data.get("results", [])
        if not results:
            return ValidationResult(
                address=address,
                is_valid=False,
                status="ZERO_RESULTS",
                error_reason="Nessun risultato trovato",
                suggestion=SUGGERIMENTI_ERRORE.get("ZERO_RESULTS"),
                raw_response=data,
            )

        return self._process_geocode_result(address, results[0], data)

    def _handle_error_status(
        self, address: Address, status: str, data: dict
    ) -> ValidationResult:
        """Gestisce stati di errore dalla API."""
        error_messages = {
            "ZERO_RESULTS": "Nessun risultato trovato per l'indirizzo",
            "OVER_QUERY_LIMIT": "Limite query API superato",
            "REQUEST_DENIED": "Richiesta negata - verificare API key",
            "INVALID_REQUEST": "Richiesta non valida",
            "UNKNOWN_ERROR": "Errore sconosciuto dal server",
        }

        return ValidationResult(
            address=address,
            is_valid=False,
            status=status,
            error_reason=error_messages.get(status, f"Errore: {status}"),
            suggestion=SUGGERIMENTI_ERRORE.get(status),
            raw_response=data,
        )

    def _process_geocode_result(
        self, address: Address, result: dict, raw_data: dict
    ) -> ValidationResult:
        """Processa il risultato della geocodifica."""
        components = result.get("address_components", [])
        formatted_address = result.get("formatted_address", "")

        # Estrai componenti
        street_number = self._get_component(components, "street_number")
        route = self._get_component(components, "route")
        locality = self._get_component(components, "locality")
        admin_area_3 = self._get_component(
            components, "administrative_area_level_3"
        )  # Comune
        postal_code = self._get_component(components, "postal_code")
        province = self._get_component(components, "administrative_area_level_2")

        # Determina la città dal risultato
        result_city = locality or admin_area_3

        # Verifica corrispondenza comune
        if result_city and address.citta:
            if not self._cities_match(address.citta, result_city):
                return ValidationResult(
                    address=address,
                    is_valid=False,
                    status="COMUNE_DIVERSO",
                    error_reason=f"Comune diverso: atteso '{address.citta}', trovato '{result_city}'",
                    suggestion=SUGGERIMENTI_ERRORE.get("COMUNE_DIVERSO"),
                    validated_address=self._build_validated_address(
                        street_number, route
                    ),
                    validated_cap=postal_code,
                    validated_citta=result_city,
                    raw_response=raw_data,
                )

        # Verifica indirizzo specifico (non generico)
        validation_status = self._check_address_quality(
            address, route, street_number, result
        )
        if validation_status:
            return ValidationResult(
                address=address,
                is_valid=False,
                status=validation_status,
                error_reason=self._get_quality_error_message(validation_status),
                suggestion=SUGGERIMENTI_ERRORE.get(validation_status),
                validated_address=self._build_validated_address(street_number, route),
                validated_cap=postal_code,
                validated_citta=result_city,
                raw_response=raw_data,
            )

        # Indirizzo valido
        validated_addr = self._build_validated_address(street_number, route)

        return ValidationResult(
            address=address,
            is_valid=True,
            status="OK",
            validated_address=validated_addr,
            validated_cap=postal_code,
            validated_citta=result_city,
            raw_response=raw_data,
        )

    def _get_component(self, components: list, component_type: str) -> Optional[str]:
        """Estrae un componente dall'indirizzo."""
        for comp in components:
            if component_type in comp.get("types", []):
                return comp.get("long_name")
        return None

    def _cities_match(self, original: str, result: str) -> bool:
        """Verifica se due nomi di città corrispondono."""
        # Normalizza per confronto
        def normalize(s):
            s = s.lower().strip()
            # Rimuovi prefissi comuni
            for prefix in ["comune di ", "citta' di ", "città di "]:
                if s.startswith(prefix):
                    s = s[len(prefix) :]
            return s

        return normalize(original) == normalize(result)

    def _check_address_quality(
        self, address: Address, route: Optional[str], street_number: Optional[str], result: dict
    ) -> Optional[str]:
        """
        Verifica la qualità dell'indirizzo geocodificato.

        Returns:
            Codice errore se l'indirizzo ha problemi, None se OK
        """
        original = address.indirizzo.lower()
        location_type = result.get("geometry", {}).get("location_type", "")

        # Verifica se è una Contrada/Località senza via specifica
        if re.search(r"\b(contrada|c\.da|localita|loc\.)\b", original, re.IGNORECASE):
            if not route or location_type == "APPROXIMATE":
                return "CONTRADA"

        # Verifica Strada Statale/Provinciale generica
        if re.search(r"\b(strada\s+statale|s\.s\.|strada\s+provinciale|s\.p\.)\b", original, re.IGNORECASE):
            if not street_number:
                return "STRADA_STATALE"

        # Verifica SNC (senza numero civico)
        if re.search(r"\bsnc\b", original, re.IGNORECASE):
            return "SNC"

        # Verifica risultato troppo generico
        if location_type == "APPROXIMATE" and not route:
            return "NO_ROUTE"

        return None

    def _get_quality_error_message(self, status: str) -> str:
        """Restituisce messaggio di errore per problemi di qualità."""
        messages = {
            "CONTRADA": "Indirizzo Contrada/Località generico",
            "STRADA_STATALE": "Strada Statale/Provinciale senza riferimento specifico",
            "SNC": "Indirizzo senza numero civico (SNC)",
            "NO_ROUTE": "Indirizzo generico senza via specifica",
        }
        return messages.get(status, "Problema qualità indirizzo")

    def _build_validated_address(
        self, street_number: Optional[str], route: Optional[str]
    ) -> str:
        """Costruisce l'indirizzo validato."""
        if route and street_number:
            return f"{route}, {street_number}"
        elif route:
            return route
        return ""
