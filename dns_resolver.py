"""
DNS Resolver - Bypass hosts file to avoid routing loops
类似 Envoy 的 DNS resolver
"""

import socket
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)

class DNSResolver:
    """
    Custom DNS resolver that bypasses hosts file

    When Router proxies requests, it needs to resolve real IPs
    to avoid routing back to itself via hosts file
    """

    def __init__(self):
        """Initialize DNS cache"""
        self._cache: Dict[str, str] = {}

        # Pre-populate with known IPs
        self._cache.update({
            "api.anthropic.com": "160.79.104.10",
            # Will query DNS for others
        })

    def resolve(self, hostname: str) -> Optional[str]:
        """
        Resolve hostname to IP address

        Args:
            hostname: Domain name to resolve

        Returns:
            IP address string, or None if resolution fails
        """
        # Check cache first
        if hostname in self._cache:
            logger.debug(f"DNS cache hit: {hostname} → {self._cache[hostname]}")
            return self._cache[hostname]

        # Try real DNS resolution (using public DNS 8.8.8.8)
        try:
            import dns.resolver

            resolver = dns.resolver.Resolver()
            resolver.nameservers = ['8.8.8.8', '8.8.4.4']  # Google DNS

            answers = resolver.resolve(hostname, 'A')
            ip = str(answers[0])

            # Cache it
            self._cache[hostname] = ip

            logger.info(f"DNS resolved: {hostname} → {ip}")
            return ip

        except ImportError:
            # Fallback: use socket.gethostbyname (may use hosts file)
            logger.warning("dnspython not installed, using socket.gethostbyname")
            try:
                ip = socket.gethostbyname(hostname)
                self._cache[hostname] = ip
                return ip
            except socket.gaierror as e:
                logger.error(f"DNS resolution failed for {hostname}: {e}")
                return None

        except Exception as e:
            logger.error(f"DNS resolution error for {hostname}: {e}")
            return None

    def get_cache(self) -> Dict[str, str]:
        """Get current DNS cache"""
        return self._cache.copy()


# Global instance
_resolver = DNSResolver()

def resolve_hostname(hostname: str) -> Optional[str]:
    """Convenience function to resolve hostname"""
    return _resolver.resolve(hostname)

def get_dns_cache() -> Dict[str, str]:
    """Get DNS cache"""
    return _resolver.get_cache()


if __name__ == "__main__":
    # Test DNS resolver
    import sys
    import io

    # Fix Windows console encoding
    if sys.platform == "win32":
        sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

    logging.basicConfig(level=logging.INFO)

    test_domains = [
        "api.anthropic.com",
        "api.openai.com",
        "claude.ai",
    ]

    print("=" * 60)
    print("DNS Resolver Test")
    print("=" * 60)

    for domain in test_domains:
        ip = resolve_hostname(domain)
        print(f"{domain:30} → {ip}")

    print()
    print("DNS Cache:")
    print("=" * 60)
    for domain, ip in get_dns_cache().items():
        print(f"{domain:30} → {ip}")
