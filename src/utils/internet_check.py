"""
HabteX Adder - Internet Check
Two-probe check (DNS + HTTP) for reliability on Android.
"""

import socket


def check_internet(timeout: int = 5) -> bool:
    probes = [
        ("8.8.8.8", 53),
        ("1.1.1.1", 53),
    ]
    for host, port in probes:
        try:
            socket.create_connection((host, port), timeout=timeout)
            return True
        except OSError:
            continue
    return False
