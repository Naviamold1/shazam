import socket
import subprocess
import sys
from pathlib import Path

import uvicorn


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

CERT_DIR = ROOT / ".certs"
CERT_FILE = CERT_DIR / "shazam.local.pem"
KEY_FILE = CERT_DIR / "shazam.local-key.pem"
CERT_META_FILE = CERT_DIR / "shazam.local.meta"


def open_lan():
    domain = f"{local_hostname()}.local"
    lan_ip = get_lan_ip()

    ensure_certificate(domain, lan_ip)
    ssl_options = {
        "ssl_certfile": str(CERT_FILE),
        "ssl_keyfile": str(KEY_FILE),
    }

    print("Local:   https://127.0.0.1:8443")
    print(f"LAN IP:  https://{lan_ip}:8443")
    print(f"Domain:  https://{domain}:8443")

    uvicorn.run(
        "backend.web:app",
        host="0.0.0.0",
        port=8443,
        **ssl_options,  # ty:ignore[invalid-argument-type]
    )

    return f"https://{lan_ip}:8443"


def local_hostname():
    try:
        result = subprocess.run(
            ["scutil", "--get", "LocalHostName"],
            check=True,
            capture_output=True,
            text=True,
        )
        hostname = result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        hostname = socket.gethostname().split(".", 1)[0]

    return hostname


def get_lan_ip() -> str:
    for interface in ("en0", "en1"):
        try:
            result = subprocess.run(
                ["ipconfig", "getifaddr", interface],
                check=True,
                capture_output=True,
                text=True,
            )
            ip_address = result.stdout.strip()
        except (FileNotFoundError, subprocess.CalledProcessError):
            continue

        if ip_address:
            return ip_address

    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        try:
            sock.connect(("8.8.8.8", 80))
            return sock.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def ensure_certificate(domain: str, lan_ip: str) -> None:
    CERT_DIR.mkdir(exist_ok=True)
    cert_meta = f"{domain}\n{lan_ip}\n"
    if (
        CERT_FILE.exists()
        and KEY_FILE.exists()
        and CERT_META_FILE.exists()
        and CERT_META_FILE.read_text(encoding="utf-8") == cert_meta
    ):
        return

    openssl_config = CERT_DIR / "openssl.cnf"
    openssl_config.write_text(
        f"""
[req]
default_bits = 2048
prompt = no
distinguished_name = dn
x509_extensions = v3_req

[dn]
CN = {domain}

[v3_req]
subjectAltName = @alt_names

[alt_names]
DNS.1 = {domain}
DNS.2 = localhost
IP.1 = {lan_ip}
IP.2 = 127.0.0.1
""".lstrip(),
        encoding="utf-8",
    )

    try:
        subprocess.run(
            [
                "openssl",
                "req",
                "-x509",
                "-newkey",
                "rsa:2048",
                "-nodes",
                "-keyout",
                str(KEY_FILE),
                "-out",
                str(CERT_FILE),
                "-days",
                "365",
                "-config",
                str(openssl_config),
            ],
            check=True,
        )
        CERT_META_FILE.write_text(cert_meta, encoding="utf-8")
    except FileNotFoundError:
        sys.exit("openssl was not found. Install OpenSSL or run with --http.")
    except subprocess.CalledProcessError as exc:
        sys.exit(f"failed to generate HTTPS certificate: {exc}")


if __name__ == "__main__":
    open_lan()
