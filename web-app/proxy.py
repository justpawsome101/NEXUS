import socket
import threading
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [proxy] %(message)s",
    datefmt="%H:%M:%S"
)
log = logging.getLogger(__name__)

LISTEN_HOST = "0.0.0.0"
LISTEN_PORT = 80
BACKEND_HOST = "127.0.0.1"
BACKEND_PORT = 8000


def parse_request(buf):
    if b"\r\n\r\n" not in buf:
        return None
    header_end = buf.index(b"\r\n\r\n") + 4
    header_part = buf[:header_end - 4]
    lines = header_part.split(b"\r\n")
    try:
        method, path, _ = lines[0].split(b" ", 2)
        method = method.decode()
        path = path.decode()
    except Exception:
        return None
    headers = {}
    for line in lines[1:]:
        if b":" in line:
            k, v = line.split(b":", 1)
            headers[k.strip().lower()] = v.strip()
    # MISCONFIGURATION M3: Transfer-Encoding completely ignored.
    # Proxy frames requests using Content-Length only.
    # Sending both headers causes desync — smuggled request bypasses ACL.
    content_length = int(headers.get(b"content-length", b"0"))
    body_end = header_end + content_length
    if len(buf) < body_end:
        return None
    raw = buf[:body_end]
    remaining = buf[body_end:]
    return raw, method, path, remaining


def forward_to_backend(data):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(10)
        s.connect((BACKEND_HOST, BACKEND_PORT))
        s.sendall(data)
        response = b""
        s.settimeout(3)
        try:
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                response += chunk
        except socket.timeout:
            pass
        s.close()
        return response
    except Exception as e:
        log.error("Backend error: %s", e)
        return b"HTTP/1.1 502 Bad Gateway\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"


def handle_client(client_sock, addr):
    buf = b""
    first_request = True
    try:
        client_sock.settimeout(30)
        while True:
            try:
                chunk = client_sock.recv(4096)
                if not chunk:
                    break
                buf += chunk
            except socket.timeout:
                break

            while True:
                result = parse_request(buf)
                if result is None:
                    break

                raw, method, path, buf = result
                log.info("%s %s %s", method, path,
                         "(direct)" if first_request else "(smuggled)")

                # ACL: blocks direct access to internal management paths.
                # VULNERABILITY: only applied to first request on connection.
                # Smuggled request arrives as leftover buffer bytes after
                # Content-Length consumed — first_request is False, ACL skipped.
                if first_request and path.startswith("/nx-internal/"):
                    log.warning("BLOCKED direct access to %s", path)
                    client_sock.sendall(
                        b"HTTP/1.1 403 Forbidden\r\n"
                        b"Content-Length: 9\r\n"
                        b"Connection: keep-alive\r\n"
                        b"\r\n"
                        b"Forbidden"
                    )
                    first_request = False
                    continue

                first_request = False
                response = forward_to_backend(raw)
                client_sock.sendall(response)

    except Exception as e:
        log.error("Client error: %s", e)
    finally:
        client_sock.close()


def main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((LISTEN_HOST, LISTEN_PORT))
    server.listen(128)
    log.info("Vulnerable proxy listening on 0.0.0.0:80")
    log.info("Forwarding to backend 127.0.0.1:8000")
    log.info("MISCONFIGURATION: Transfer-Encoding ignored, Content-Length only")

    while True:
        client_sock, addr = server.accept()
        t = threading.Thread(target=handle_client, args=(client_sock, addr))
        t.daemon = True
        t.start()


if __name__ == "__main__":
    main()
