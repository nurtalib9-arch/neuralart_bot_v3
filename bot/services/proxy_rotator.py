"""Proxy pool management."""
import os
from typing import Optional, List, Tuple
from dataclasses import dataclass

@dataclass
class Proxy:
    protocol: str
    host: str
    port: int
    username: Optional[str] = None
    password: Optional[str] = None
    usage_count: int = 0
    is_banned: bool = False
    fail_count: int = 0

    def to_telethon_tuple(self) -> Tuple:
        if self.username and self.password:
            return (self.protocol, self.host, self.port, True, self.username, self.password)
        return (self.protocol, self.host, self.port)

    def __str__(self):
        if self.username:
            return f"{self.protocol}://{self.username}:***@{self.host}:{self.port}"
        return f"{self.protocol}://{self.host}:{self.port}"

class ProxyRotator:
    def __init__(self, proxy_file: str = "data/proxies.txt", max_usage: int = 3, max_fails: int = 2):
        self.proxies: List[Proxy] = []
        self.max_usage = max_usage
        self.max_fails = max_fails
        self._load_proxies(proxy_file)

    def _load_proxies(self, filepath: str):
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
                        self.proxies.append(proxy)
                except Exception:
                    continue
        print(f"[+] Loaded {len(self.proxies)} proxies")

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
        available = [p for p in self.proxies if not p.is_banned and p.usage_count < self.max_usage and p.fail_count < self.max_fails]
        if not available:
            for p in self.proxies:
                p.usage_count = 0
            available = [p for p in self.proxies if not p.is_banned and p.fail_count < self.max_fails]
        if not available:
            return None
        proxy = min(available, key=lambda p: p.usage_count)
        proxy.usage_count += 1
        return proxy

    def mark_banned(self, proxy: Proxy):
        proxy.is_banned = True

    def mark_failed(self, proxy: Proxy):
        proxy.fail_count += 1
        if proxy.fail_count >= self.max_fails:
            self.mark_banned(proxy)

    def get_stats(self) -> dict:
        return {
            "total": len(self.proxies),
            "available": len([p for p in self.proxies if not p.is_banned]),
            "banned": len([p for p in self.proxies if p.is_banned]),
        }
