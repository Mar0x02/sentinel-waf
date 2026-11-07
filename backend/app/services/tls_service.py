"""Validation for manually-uploaded TLS cert/key pairs (Sites page).

For the automated path (Let's Encrypt dns-01), see services/acme_service.py
- that flow writes an already-matching keypair it generated itself, so it
skips this module entirely. This one is for the manual-paste/upload path:
the operator's own PEM cert + key, which this module's only job is to
reject if garbage before it ever reaches render_service (which just writes
the bytes to files nginx reads via ssl_certificate/ssl_certificate_key -
see there for why no further escaping is needed, unlike a Site's
domain/upstream_url which get interpolated into config text).
"""

from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import serialization


class CertValidationError(ValueError):
    pass


def _parse_cert(pem: str) -> x509.Certificate:
    try:
        return x509.load_pem_x509_certificate(pem.encode())
    except Exception as exc:
        raise CertValidationError("Not a valid PEM certificate") from exc


def _parse_key(pem: str):
    try:
        return serialization.load_pem_private_key(pem.encode(), password=None)
    except Exception as exc:
        raise CertValidationError("Not a valid PEM private key (encrypted/passworded keys aren't supported)") from exc


def validate_cert_key_pair(cert_pem: str, key_pem: str) -> x509.Certificate:
    """Raises CertValidationError if either PEM is malformed, the key type
    isn't RSA/EC, or the cert's public key doesn't match the private key.
    Returns the parsed certificate (for pulling the expiry date) on success.
    """
    cert = _parse_cert(cert_pem)
    key = _parse_key(key_pem)

    try:
        cert_numbers = cert.public_key().public_numbers()
        key_numbers = key.public_key().public_numbers()
    except AttributeError as exc:
        raise CertValidationError("Only RSA and EC keys are supported") from exc

    if cert_numbers != key_numbers:
        raise CertValidationError("Certificate and private key do not match")

    return cert


def cert_expires_at(cert: x509.Certificate) -> datetime:
    return cert.not_valid_after_utc


def expiry_from_pem(cert_pem: str) -> datetime:
    """For API responses that only need the expiry date, not a full
    validate_cert_key_pair() round-trip (the pair was already validated
    once, at upload time)."""
    return cert_expires_at(_parse_cert(cert_pem))
