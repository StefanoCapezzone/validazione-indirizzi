"""
Address Validator - Validazione indirizzi da Excel con Google Maps Geocoding API
"""

__version__ = "1.0.0"
__author__ = "Address Validator"

from .models import Address, ValidationResult
from .processor import AddressProcessor

__all__ = ["Address", "ValidationResult", "AddressProcessor", "__version__"]
