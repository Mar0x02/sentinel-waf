"""Automated Let's Encrypt (ACME v2, dns-01) issuance for a Site's TLS cert.

Flow (see api/sites.py's two endpoints):
1. start_order(): generates a cert keypair + CSR, opens an ACME order, picks
   the dns-01 challenge, and hands back the TXT record name/value for the
   operator to paste into their DNS provider.
2. check_and_finalize(): called on every frontend poll. Does a live DNS
   lookup for that TXT record; once it resolves, answers the challenge and
   finalizes the order, then writes the issued cert straight into
   Site.tls_cert/tls_key - same fields a manual paste would fill in.

dns-01 (not http-01) specifically because it needs no change to request
routing/nginx config to serve a challenge file - the WAF already proxies
all of :80 traffic per-site, and carving out an exception for
/.well-known/acme-challenge/ ahead of that routing isn't worth it when the
DNS TXT approach needs nothing from waf-engine at all.
"""

import logging

import httpx
import josepy as jose
from acme import challenges, client, crypto_util, errors, messages
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from sqlalchemy.orm import Session

from app.config import Settings
from app.models import AppSecret, CertOrder, CertOrderStatus, Site

logger = logging.getLogger(__name__)

ACME_ACCOUNT_KEY_NAME = "acme_account_key"
USER_AGENT = "sentinel-waf-acme"

# DNS-over-HTTPS, not plain UDP/TCP dns.resolver - confirmed by testing that
# a regular DNS query can sit on a stale cached answer for a domain whose NS
# just changed (a resolver/transparent-proxy somewhere on the network path
# keeps serving the old delegation until its TTL - up to 24h for an NS
# record - fully expires), while the two CAs' own DoH endpoints, queried
# fresh over HTTPS, reflected the real current record immediately. Querying
# two independent providers rather than one, since a single resolver -
# DoH or not - can still be the one with the stale view.
_DOH_ENDPOINTS = ["https://dns.google/resolve", "https://cloudflare-dns.com/dns-query"]

# In-memory only, this process's lifetime - see CertOrder's docstring in
# models.py for why the CSR key and the live acme-python order/challenge
# objects never touch Postgres.
_PENDING: dict[int, dict] = {}


class AcmeOrderError(RuntimeError):
    pass


def _generate_rsa_pem() -> bytes:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )


def _get_or_create_account_key(db: Session) -> jose.JWKRSA:
    row = db.get(AppSecret, ACME_ACCOUNT_KEY_NAME)
    if row is None:
        row = AppSecret(key=ACME_ACCOUNT_KEY_NAME, value=_generate_rsa_pem().decode())
        db.add(row)
        db.commit()
    loaded = serialization.load_pem_private_key(row.value.encode(), password=None)
    return jose.JWKRSA(key=loaded)


def _build_client(db: Session, settings: Settings) -> client.ClientV2:
    acc_key = _get_or_create_account_key(db)
    net = client.ClientNetwork(acc_key, user_agent=USER_AGENT)
    directory = messages.Directory.from_json(net.get(settings.acme_directory_url).json())
    acme_client = client.ClientV2(directory, net=net)
    # The ACME account key is reused for every order (get_or_create above),
    # so after the first successful order this *always* hits the
    # already-registered case. python-acme's own new_account() signals that
    # by raising ConflictError(location) rather than returning normally
    # (see its docstring: ":raises .ConflictError: in case the account
    # already exists") - this is expected steady-state behavior, not a
    # failure. Net.account must still end up set either way: every
    # post-registration request (new_order, etc.) needs to be signed with
    # `kid` (the account URL) instead of a raw `jwk`, which ClientNetwork
    # only does once net.account is populated.
    try:
        acme_client.new_account(
            messages.NewRegistration.from_data(email=settings.acme_contact_email, terms_of_service_agreed=True)
        )
    except errors.ConflictError as exc:
        acme_client.net.account = messages.RegistrationResource(uri=exc.location, body=messages.Registration())
    return acme_client


def start_order(db: Session, settings: Settings, site: Site) -> CertOrder:
    try:
        acme_client = _build_client(db, settings)
        cert_key_pem = _generate_rsa_pem()
        csr_pem = crypto_util.make_csr(cert_key_pem, [site.domain])
        order = acme_client.new_order(csr_pem)
    except Exception as exc:
        # str(exc) can come back empty for some exception types (e.g. a bare
        # socket timeout) - the full traceback only ever shows up in the
        # container logs, not the toast the operator sees, so log it here.
        logger.exception("ACME new_order failed for site %s (%s)", site.id, site.domain)
        raise AcmeOrderError(f"Could not open ACME order: {exc!r}") from exc

    dns_challenge = next(
        (
            challb
            for authz in order.authorizations
            for challb in authz.body.challenges
            if isinstance(challb.chall, challenges.DNS01)
        ),
        None,
    )
    if dns_challenge is None:
        raise AcmeOrderError("CA did not offer a dns-01 challenge for this domain")

    validation = dns_challenge.chall.validation(acme_client.net.key)

    _PENDING[site.id] = {
        "client": acme_client,
        "order": order,
        "challb": dns_challenge,
        "cert_key_pem": cert_key_pem.decode(),
    }

    row = db.get(CertOrder, site.id)
    if row is None:
        row = CertOrder(site_id=site.id)
        db.add(row)
    row.status = CertOrderStatus.pending_dns
    row.dns_name = f"_acme-challenge.{site.domain}"
    row.dns_value = validation
    row.error_message = None
    db.commit()
    db.refresh(row)
    return row


def _dns_txt_has_value(name: str, value: str) -> bool:
    for url in _DOH_ENDPOINTS:
        try:
            resp = httpx.get(
                url, params={"name": name, "type": "TXT"}, headers={"accept": "application/dns-json"}, timeout=10.0
            )
            resp.raise_for_status()
            for answer in resp.json().get("Answer", []):
                # Cloudflare's DoH wraps TXT data in literal double quotes
                # (RFC 1035 presentation format); Google's doesn't - strip()
                # handles both without caring which provider answered.
                if str(answer.get("data", "")).strip('"') == value:
                    return True
        except Exception:
            continue  # try the next provider rather than failing outright
    return False


def check_and_finalize(db: Session, site: Site) -> CertOrder:
    row = db.get(CertOrder, site.id)
    if row is None:
        raise AcmeOrderError("No cert order for this site yet - click Generate first")
    if row.status != CertOrderStatus.pending_dns:
        return row

    pending = _PENDING.get(site.id)
    if pending is None:
        row.status = CertOrderStatus.failed
        row.error_message = "Order state was lost (backend restarted) - click Generate to start over"
        db.commit()
        db.refresh(row)
        return row

    if not _dns_txt_has_value(row.dns_name, row.dns_value):
        return row  # still waiting on DNS propagation, nothing to do yet

    acme_client: client.ClientV2 = pending["client"]
    challb = pending["challb"]
    try:
        acme_client.answer_challenge(challb, challb.chall.response(acme_client.net.key))
        finalized = acme_client.poll_and_finalize(pending["order"])
    except Exception as exc:
        logger.exception("ACME finalize failed for site %s (%s)", site.id, site.domain)
        row.status = CertOrderStatus.failed
        row.error_message = repr(exc)
        db.commit()
        db.refresh(row)
        _PENDING.pop(site.id, None)
        return row

    site.tls_cert = finalized.fullchain_pem
    site.tls_key = pending["cert_key_pem"]
    site.tls_enabled = True
    row.status = CertOrderStatus.issued
    row.error_message = None
    db.commit()
    db.refresh(row)
    _PENDING.pop(site.id, None)
    return row
