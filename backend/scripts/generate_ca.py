"""
GhostWire Certificate Authority — pure Python, no deprecation warnings.
Uses timezone-aware datetime throughout (required by cryptography >= 42).
"""
import ipaddress
from datetime import datetime, timezone, timedelta
from pathlib import Path

from cryptography import x509
from cryptography.x509.oid import NameOID, ExtendedKeyUsageOID
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.backends import default_backend


def _now() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class CertificateAuthority:
    def __init__(self, brand: str, hostname: str, public_ip: str,
                 certs_dir: str, output_dir: str):
        self.brand      = brand
        self.hostname   = hostname
        self.public_ip  = public_ip
        self.certs_dir  = Path(certs_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Output paths
        self.ca_key_path   = self.output_dir / "ca.key"
        self.ca_cert_path  = self.output_dir / "ca.crt"
        self.srv_key_path  = self.output_dir / "server.key"
        self.srv_cert_path = self.output_dir / "server.crt"

        # strongSwan paths (swanctl native layout)
        self.ss_cacerts = self.certs_dir / "x509ca"
        self.ss_certs   = self.certs_dir / "x509"
        self.ss_private = self.certs_dir / "private"
        for d in [self.ss_cacerts, self.ss_certs, self.ss_private]:
            d.mkdir(parents=True, exist_ok=True)

    def _gen_key(self) -> rsa.RSAPrivateKey:
        return rsa.generate_private_key(
            public_exponent=65537, key_size=2048, backend=default_backend()
        )

    def _save_key(self, key, path: Path) -> None:
        pem = key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.TraditionalOpenSSL,
            encryption_algorithm=serialization.NoEncryption(),
        )
        path.write_bytes(pem)
        path.chmod(0o600)

    # ── CA generation ──────────────────────────────────────────────────────────

    def generate_ca(self):
        ca_key = self._gen_key()
        subject = issuer = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, f"{self.brand} VPN"),
            x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, "Certificate Authority"),
            x509.NameAttribute(NameOID.COMMON_NAME, f"{self.brand} Root CA"),
        ])
        ca_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(issuer)
            .public_key(ca_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(_now())
            .not_valid_after(_now() + timedelta(days=3650))  # 10 years
            .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=False, key_cert_sign=True, crl_sign=True,
                    content_commitment=False, key_encipherment=False,
                    data_encipherment=False, key_agreement=False,
                    encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.SubjectKeyIdentifier.from_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256(), default_backend())
        )

        self._save_key(ca_key, self.ca_key_path)
        ca_pem = ca_cert.public_bytes(serialization.Encoding.PEM)
        self.ca_cert_path.write_bytes(ca_pem)
        (self.ss_cacerts / "ca.crt").write_bytes(ca_pem)

        print(f"[CA] Root CA generated — valid until {(_now() + timedelta(days=3650)).date()}")
        return ca_key, ca_cert

    # ── Server cert ────────────────────────────────────────────────────────────

    def generate_server_cert(self, ca_key, ca_cert) -> None:
        srv_key = self._gen_key()
        subject = x509.Name([
            x509.NameAttribute(NameOID.COUNTRY_NAME, "US"),
            x509.NameAttribute(NameOID.ORGANIZATION_NAME, f"{self.brand} VPN"),
            x509.NameAttribute(NameOID.COMMON_NAME, self.hostname),
        ])

        # Build SAN list — IP-type SAN when hostname is a raw IP, DNS SAN for real hostnames.
        # iOS validates the server cert SAN strictly against RemoteIdentifier in the profile.
        # IMPORTANT: Do NOT add placeholder/bogus DNS SANs (e.g. "ghostwire.home") —
        # they have no effect and some iOS versions flag extra unrecognised SANs.
        san: list = []
        try:
            ipaddress.ip_address(self.hostname)
            # hostname IS an IP address — add as IP SAN only
            san.append(x509.IPAddress(ipaddress.ip_address(self.hostname)))
        except ValueError:
            # hostname is a real DNS name — add as DNS SAN
            san.append(x509.DNSName(self.hostname))
        # Always add public_ip as IP SAN so IP-only deployments work without DDNS
        try:
            ip_obj = ipaddress.ip_address(self.public_ip)
            ip_san = x509.IPAddress(ip_obj)
            if ip_san not in san:
                san.append(ip_san)
        except ValueError:
            pass

        srv_cert = (
            x509.CertificateBuilder()
            .subject_name(subject)
            .issuer_name(ca_cert.subject)
            .public_key(srv_key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(_now())
            .not_valid_after(_now() + timedelta(days=825))  # ~2.25 years
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.SubjectAlternativeName(san), critical=False)
            .add_extension(
                x509.KeyUsage(
                    digital_signature=True, key_encipherment=True,
                    content_commitment=False, data_encipherment=False,
                    key_agreement=False, key_cert_sign=False,
                    crl_sign=False, encipher_only=False, decipher_only=False,
                ),
                critical=True,
            )
            .add_extension(
                x509.ExtendedKeyUsage([
                    ExtendedKeyUsageOID.SERVER_AUTH,
                    x509.ObjectIdentifier("1.3.6.1.5.5.8.2.2"),  # iKEIntermediate
                ]),
                critical=False,
            )
            .add_extension(
                x509.AuthorityKeyIdentifier.from_issuer_public_key(ca_key.public_key()),
                critical=False,
            )
            .sign(ca_key, hashes.SHA256(), default_backend())
        )

        self._save_key(srv_key, self.srv_key_path)
        srv_pem = srv_cert.public_bytes(serialization.Encoding.PEM)
        self.srv_cert_path.write_bytes(srv_pem)

        # Install into strongSwan directories
        (self.ss_certs / "server.crt").write_bytes(srv_pem)
        srv_key_pem = srv_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.TraditionalOpenSSL,
            serialization.NoEncryption(),
        )
        key_dest = self.ss_private / "server.key"
        key_dest.write_bytes(srv_key_pem)
        key_dest.chmod(0o600)

        san_str = ", ".join(str(s.value) for s in san)
        print(f"[CA] Server cert generated — SAN: [{san_str}]")

    # ── Exports ────────────────────────────────────────────────────────────────

    def export_ca_der(self) -> bytes:
        """Export CA cert as DER (for Windows cert installer and Android)."""
        cert = x509.load_pem_x509_certificate(
            self.ca_cert_path.read_bytes(), default_backend()
        )
        der = cert.public_bytes(serialization.Encoding.DER)
        (self.output_dir / "ca.der").write_bytes(der)
        return der

    def get_ca_pem(self) -> str:
        return self.ca_cert_path.read_text()

    def get_server_cert_pem(self) -> str:
        return self.srv_cert_path.read_text()

    # ── Regenerate server cert (no-DDNS IP change) ────────────────────────────

    def regenerate_server_cert(self, new_ip: str = None, new_hostname: str = None) -> None:
        if new_ip:       self.public_ip = new_ip
        if new_hostname: self.hostname  = new_hostname
        from cryptography.hazmat.primitives.serialization import load_pem_private_key
        ca_key  = load_pem_private_key(
            self.ca_key_path.read_bytes(), password=None, backend=default_backend()
        )
        ca_cert = x509.load_pem_x509_certificate(
            self.ca_cert_path.read_bytes(), default_backend()
        )
        self.generate_server_cert(ca_key, ca_cert)

    # ── Full generation ────────────────────────────────────────────────────────

    def generate_all(self) -> dict:
        print(f"[CA] Starting certificate generation for '{self.brand}' / {self.hostname}")
        ca_key, ca_cert = self.generate_ca()
        self.generate_server_cert(ca_key, ca_cert)
        self.export_ca_der()
        print(f"[CA] Done — certificates in {self.output_dir}")
        return {
            "ca_pem":     self.ca_cert_path.read_text(),
            "server_pem": self.srv_cert_path.read_text(),
        }


if __name__ == "__main__":
    import argparse
    p = argparse.ArgumentParser(description="GhostWire Certificate Authority")
    p.add_argument("--hostname",   required=True, help="Server hostname or IP")
    p.add_argument("--public-ip",  required=True, help="Current public IP")
    p.add_argument("--brand",      default="GhostWire", help="Brand name")
    p.add_argument("--certs-dir",  default="/etc/swanctl")
    p.add_argument("--output-dir", default="/opt/ghostwire/data/certs")
    a = p.parse_args()
    CertificateAuthority(
        brand=a.brand, hostname=a.hostname, public_ip=a.public_ip,
        certs_dir=a.certs_dir, output_dir=a.output_dir,
    ).generate_all()
