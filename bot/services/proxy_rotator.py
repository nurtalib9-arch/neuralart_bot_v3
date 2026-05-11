"""Single proxy management."""
import os
from typing import Optional, Tuple
from dataclasses import dataclass

@dataclass
class Proxy:
    protocol: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None

    def to_telethon_tuple(self) -> Tuple:
        if self.username and self.password:
            return (self.protocol, self.host, self.port, True, self.username, self.password)
        return (self.protocol, self.host, self.port)

    def __str__(self):
        if self.username:
            return f"{self.protocol}://{self.username}:***@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

class ProxyRotator:
    def __init__(self, proxy_file: str = "data/proxies.txt"):
        self.proxy: Optional[Proxy] = None
        self._load_proxy(proxy_file)

    def _load_proxy(self, filepath: str):
        if not os.path.exists(filepath):
            print(f"[!] Proxy file not found: {filepath}")
            return
        with open(filepath, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                try:
                    proxy = self._parse_proxy_line(line)
                    if proxy:
                        self.proxy = proxy
                        print(f"[+] Proxy loaded: {proxy}")
                        return
                except Exception as e:
                    print(f"[!] Failed to parse proxy line: {line} — {e}")
                    continue
        print("[!] No valid proxy found in file")

    def _parse_proxy_line(self, line: str) -> Optional[Proxy]:
        if '://' not in line:
            line = f"socks5://{line}"
        protocol, rest = line.split('://', 1)
        if '@' in rest:
            auth, hostport = rest.split('@', 1)
            username, password = auth.split(':', 1) if ':' in auth else (auth, None)
        else:
            username = password = None
            hostport = rest
        if ':' not in hostport:
            return None
        host, port_str = hostport.rsplit(':', 1)
        return Proxy(protocol=protocol, host=host, port=int(port_str), username=username, password=password)

    def get_proxy(self) -> Optional[Proxy]:
        return self.proxy

    def mark_banned(self, proxy: Proxy):
        """Stub — single proxy, no banning logic."""
        pass

    def mark_failed(self, proxy: Proxy):
        """Stub — single proxy, no fail tracking."""
        pass

    def get_stats(self) -> dict:
        return {
            "total": 1 if self.proxy else 0,
            "available": 1 if self.proxy else 0,
            "banned": 0,
        }