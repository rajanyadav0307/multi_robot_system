# common/utils.py
import time
import uuid

def get_timestamp() -> int:
    """Return UNIX timestamp (seconds)."""
    return int(time.time())


def _try_netifaces_mac():
    try:
        import netifaces
    except Exception:
        return None
    for iface in ("eth0", "wlan0", "en0"):
        if iface in netifaces.interfaces():
            addrs = netifaces.ifaddresses(iface)
            if netifaces.AF_LINK in addrs:
                link = addrs[netifaces.AF_LINK]
                if isinstance(link, list) and len(link) > 0:
                    mac = link[0].get("addr")
                    if mac:
                        return mac
    return None


def get_mac_address() -> str:
    """
    Try to obtain MAC address in a cross-platform way.
    Fallback to uuid.getnode() if netifaces not available.
    Returns mac string like 'aa:bb:cc:dd:ee:ff'
    """
    mac = _try_netifaces_mac()
    if mac:
        return mac.lower()
    # fallback
    mac_int = uuid.getnode()
    mac = ":".join(f"{(mac_int >> ele) & 0xff:02x}" for ele in range(40, -1, -8))
    return mac.lower()


def get_robot_id() -> str:
    """Return a stable robot id derived from MAC address."""
    mac = get_mac_address().replace(":", "")
    return f"robot_{mac}"
