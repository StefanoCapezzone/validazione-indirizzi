"""
Client SOAP per GLS Label Service API.
"""

import time
import logging
from typing import Optional

from zeep import Client
from zeep.exceptions import Fault, TransportError
from lxml import etree

from .config import (
    GLS_ENDPOINT,
    GLS_RETRY_ATTEMPTS,
    GLS_RETRY_DELAY,
    GLS_MAX_PARCELS_PER_BATCH,
)
from .gls_models import GLSCredentials, GLSParcel, GLSResponse

logger = logging.getLogger(__name__)


class GLSClientError(Exception):
    """Errore del client GLS."""
    pass


class GLSClient:
    """Client per interagire con GLS Label Service API via SOAP."""

    def __init__(self, credentials: GLSCredentials):
        """
        Inizializza il client GLS.

        Args:
            credentials: Credenziali GLS
        """
        if not credentials.is_valid():
            raise GLSClientError("Credenziali GLS incomplete")

        self.credentials = credentials
        self._client: Optional[Client] = None

    def _get_client(self) -> Client:
        """Ottiene o crea il client SOAP."""
        if self._client is None:
            try:
                self._client = Client(GLS_ENDPOINT)
            except Exception as e:
                raise GLSClientError(f"Impossibile connettersi a GLS: {e}")
        return self._client

    def _execute_with_retry(self, operation: str, *args, **kwargs):
        """
        Esegue un'operazione con retry e exponential backoff.

        Args:
            operation: Nome del metodo SOAP da chiamare
            *args: Argomenti posizionali
            **kwargs: Argomenti keyword

        Returns:
            Risultato della chiamata SOAP
        """
        client = self._get_client()
        last_error = None

        for attempt in range(GLS_RETRY_ATTEMPTS):
            try:
                method = getattr(client.service, operation)
                return method(*args, **kwargs)
            except (Fault, TransportError) as e:
                last_error = e
                if attempt < GLS_RETRY_ATTEMPTS - 1:
                    delay = GLS_RETRY_DELAY * (2 ** attempt)
                    logger.warning(f"Tentativo {attempt + 1} fallito, riprovo tra {delay}s: {e}")
                    time.sleep(delay)
            except Exception as e:
                raise GLSClientError(f"Errore imprevisto: {e}")

        raise GLSClientError(f"Fallito dopo {GLS_RETRY_ATTEMPTS} tentativi: {last_error}")

    def add_parcel(self, parcel: GLSParcel, generate_pdf: bool = False) -> GLSResponse:
        """
        Aggiunge una singola spedizione.

        Args:
            parcel: Dati della spedizione
            generate_pdf: Se generare l'etichetta PDF

        Returns:
            GLSResponse con l'esito
        """
        return self.add_parcels([parcel], generate_pdf)[0]

    def add_parcels(self, parcels: list[GLSParcel], generate_pdf: bool = False) -> list[GLSResponse]:
        """
        Aggiunge un batch di spedizioni.

        Args:
            parcels: Lista di spedizioni (max 400)
            generate_pdf: Se generare le etichette PDF

        Returns:
            Lista di GLSResponse
        """
        if len(parcels) > GLS_MAX_PARCELS_PER_BATCH:
            raise GLSClientError(f"Massimo {GLS_MAX_PARCELS_PER_BATCH} spedizioni per batch")

        if not parcels:
            return []

        # Costruisce XML delle spedizioni
        xml_data = self._build_parcels_xml(parcels)

        # Chiama il metodo AddParcel
        result = self._execute_with_retry(
            "AddParcel",
            self.credentials.sede,
            self.credentials.codice_cliente,
            self.credentials.password,
            self.credentials.codice_contratto,
            xml_data,
            "1" if generate_pdf else "0",
        )

        return self._parse_add_parcel_response(result, parcels)

    def _build_parcels_xml(self, parcels: list[GLSParcel]) -> str:
        """
        Costruisce l'XML per l'invio delle spedizioni.

        Args:
            parcels: Lista di spedizioni

        Returns:
            Stringa XML
        """
        root = etree.Element("Info")

        for parcel in parcels:
            parcel_elem = etree.SubElement(root, "Parcel")
            data = parcel.to_dict()

            for key, value in data.items():
                if value:  # Solo campi non vuoti
                    elem = etree.SubElement(parcel_elem, key)
                    elem.text = str(value)

        return etree.tostring(root, encoding="unicode")

    def _parse_add_parcel_response(
        self, result: str, parcels: list[GLSParcel]
    ) -> list[GLSResponse]:
        """
        Parsea la risposta XML di AddParcel.

        Args:
            result: XML di risposta
            parcels: Lista originale delle spedizioni (per BDA)

        Returns:
            Lista di GLSResponse
        """
        responses = []

        try:
            root = etree.fromstring(result.encode() if isinstance(result, str) else result)

            # Cerca i risultati delle spedizioni
            parcel_results = root.findall(".//Parcel") or root.findall(".//parcel")

            for i, parcel_result in enumerate(parcel_results):
                response = GLSResponse()

                # Recupera BDA originale se disponibile
                if i < len(parcels):
                    response.bda = parcels[i].bda

                # Parse dei campi risposta
                for child in parcel_result:
                    tag = child.tag.lower()
                    text = child.text or ""

                    if tag in ("numerospedizione", "parcelid", "sped"):
                        response.numero_spedizione = text
                    elif tag in ("esito", "result"):
                        response.esito = text
                    elif tag in ("errore", "error", "errormessage"):
                        response.error_message = text
                    elif tag in ("pdf", "pdfbase64", "label"):
                        response.pdf_base64 = text
                    elif tag == "bda":
                        response.bda = text

                responses.append(response)

            # Se non ci sono risultati parsati, crea risposta di errore
            if not responses:
                error_text = root.text or etree.tostring(root, encoding="unicode")
                for parcel in parcels:
                    responses.append(GLSResponse(
                        bda=parcel.bda,
                        esito="KO",
                        error_message=f"Risposta non parsabile: {error_text[:100]}"
                    ))

        except etree.XMLSyntaxError as e:
            logger.error(f"Errore parsing XML risposta: {e}")
            for parcel in parcels:
                responses.append(GLSResponse(
                    bda=parcel.bda,
                    esito="KO",
                    error_message=f"XML non valido: {e}"
                ))

        return responses

    def close_work_day(self) -> dict:
        """
        Chiude la giornata lavorativa (CloseWorkDay).
        Conferma tutte le spedizioni inserite.

        Returns:
            Dict con esito e eventuali errori
        """
        result = self._execute_with_retry(
            "CloseWorkDay",
            self.credentials.sede,
            self.credentials.codice_cliente,
            self.credentials.password,
        )

        return self._parse_close_work_day_response(result)

    def _parse_close_work_day_response(self, result: str) -> dict:
        """Parsea la risposta di CloseWorkDay."""
        try:
            root = etree.fromstring(result.encode() if isinstance(result, str) else result)

            esito = root.findtext(".//Esito") or root.findtext(".//esito") or ""
            errore = root.findtext(".//Errore") or root.findtext(".//errore") or ""

            return {
                "success": esito.upper() == "OK",
                "esito": esito,
                "error": errore,
            }
        except Exception as e:
            return {
                "success": False,
                "esito": "KO",
                "error": f"Errore parsing risposta: {e}",
            }

    def list_shipments(self, date_from: str = "", date_to: str = "") -> list[dict]:
        """
        Elenca le spedizioni (ListSped).

        Args:
            date_from: Data inizio (YYYYMMDD)
            date_to: Data fine (YYYYMMDD)

        Returns:
            Lista di dizionari con dati spedizioni
        """
        result = self._execute_with_retry(
            "ListSped",
            self.credentials.sede,
            self.credentials.codice_cliente,
            self.credentials.password,
            date_from,
            date_to,
        )

        return self._parse_list_shipments_response(result)

    def _parse_list_shipments_response(self, result: str) -> list[dict]:
        """Parsea la risposta di ListSped."""
        shipments = []

        try:
            root = etree.fromstring(result.encode() if isinstance(result, str) else result)

            for sped in root.findall(".//Spedizione") or root.findall(".//spedizione"):
                shipment = {}
                for child in sped:
                    shipment[child.tag] = child.text or ""
                shipments.append(shipment)

        except Exception as e:
            logger.error(f"Errore parsing lista spedizioni: {e}")

        return shipments

    def delete_shipment(self, shipment_id: str) -> dict:
        """
        Elimina una spedizione (DeleteSped).

        Args:
            shipment_id: ID della spedizione da eliminare

        Returns:
            Dict con esito
        """
        result = self._execute_with_retry(
            "DeleteSped",
            self.credentials.sede,
            self.credentials.codice_cliente,
            self.credentials.password,
            shipment_id,
        )

        try:
            root = etree.fromstring(result.encode() if isinstance(result, str) else result)
            esito = root.findtext(".//Esito") or root.findtext(".//esito") or ""
            errore = root.findtext(".//Errore") or root.findtext(".//errore") or ""

            return {
                "success": esito.upper() == "OK",
                "esito": esito,
                "error": errore,
            }
        except Exception as e:
            return {
                "success": False,
                "esito": "KO",
                "error": f"Errore: {e}",
            }

    def test_connection(self) -> bool:
        """
        Testa la connessione e le credenziali.

        Returns:
            True se la connessione è valida
        """
        try:
            # Usa ListSped con range vuoto come test
            self.list_shipments()
            return True
        except GLSClientError:
            return False
