"""The only module that can WRITE to the watch. Dry-run by default; sending needs K1 + explicit consent.

A plan (list of bridge.Step) is turned into packets by ``build_packets`` (offline, testable). ``run_plan``
either prints them (dry-run) or, only when ``live=True`` AND a K1 is loaded AND ``consent=True``, connects
with bleak and writes them to the command characteristic.

Hard guard rails:
  * Default is dry-run. Going live requires three independent things, any missing => refuse.
  * Only commands in ``commands.ALLOWED`` are ever built; a blocked/destructive command raises.
  * Firmware, the factory shell and factory reset are never touched. No pairing is initiated here
    (``pair=False``), matching the project's rule against pair/unpair.
  * This is a PROTOTYPE: the byte protocol is from Gadgetbridge and unverified on this watch, so live mode
    is intended for a test only after the owner has confirmed compatibility and a recovery path.
"""

from __future__ import annotations

from dataclasses import dataclass

from companion import auth, commands, protocol
from companion.bridge import Step

# Command channel (Gadgetbridge: UUID_SERVICE_CMF_CMD / write FFF2).
CMD_WRITE_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"
CMD_NOTIFY_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"


class RefusedToSend(RuntimeError):
    pass


def _check_allowed(step: Step) -> None:
    if step.cmd.name not in commands.ALLOWED:
        raise RefusedToSend(f"command {step.cmd.name} is not in the allowed set")


@dataclass
class BuiltStep:
    describe: str
    packets: list[bytes]


def build_packets(plan: list[Step], session_key: bytes | None, mtu: int = 247) -> list[BuiltStep]:
    """Turn a plan into on-wire packets (offline). ``session_key`` None builds encrypted-shaped frames only
    if given; for a pure dry-run without a key we build plaintext frames so the layout is still visible."""
    out = []
    for s in plan:
        _check_allowed(s)
        key = session_key if (s.cmd.encrypted and session_key is not None) else None
        out.append(BuiltStep(s.describe, protocol.encode(s.cmd.cmd1, s.cmd.cmd2, s.payload, key=key, mtu=mtu)))
    return out


def dry_run(plan: list[Step], session_key: bytes | None = None) -> list[str]:
    """Return human-readable lines describing what WOULD be sent. Sends nothing."""
    lines = []
    for b in build_packets(plan, session_key):
        total = sum(len(p) for p in b.packets)
        lines.append(f"[dry-run] {b.describe}: {len(b.packets)} packet(s), {total} bytes")
        for p in b.packets:
            lines.append(f"            {p.hex()}")
    return lines


async def run_plan(plan: list[Step], *, live: bool = False, consent: bool = False, address: str | None = None,
                   log=print) -> int:
    """Dry-run unless live+consent+K1 are all present. Returns 0 on success, non-zero on refusal/failure."""
    if not live:
        for line in dry_run(plan, auth.load_k1() and b"\x00" * 16 or None):
            log(line)
        log("[dry-run] nothing was sent. Use --live (with K1 and --yes-i-confirm) to send for real.")
        return 0

    k1 = auth.load_k1()
    if k1 is None:
        raise RefusedToSend("live mode needs your K1 (data/companion/k1.key or $CMF_K1); see companion/auth.py")
    if not consent:
        raise RefusedToSend("live mode needs explicit per-run consent (pass consent=True / --yes-i-confirm)")
    if not address:
        raise RefusedToSend("live mode needs the watch address")

    # Imported here so a dry-run never even needs bleak, and the read-only packages never import this one.
    from bleak import BleakClient, BleakScanner

    for s in plan:
        _check_allowed(s)

    device = await BleakScanner.find_device_by_address(address, timeout=10.0)
    if device is None:
        raise RefusedToSend(f"{address} is not advertising; wake the watch and disconnect the phone app")

    async with BleakClient(device, pair=False) as client:  # never initiates pairing
        nonce = await _handshake(client, log)
        key = auth.session_key(nonce, k1)
        for b in build_packets(plan, key, mtu=getattr(client, "mtu_size", 247)):
            log(f"[live] {b.describe}")
            for pkt in b.packets:
                await client.write_gatt_char(CMD_WRITE_UUID, pkt, response=False)
    log("[live] done")
    return 0


async def _handshake(client, log) -> bytes:
    """Placeholder for the documented auth handshake (AUTH_PHONE_NAME -> MAC -> nonce -> confirm).

    Not implemented in this prototype: it must be built and checked against a real capture first, because
    the exact payloads are unverified. Live mode therefore stops here until the handshake is implemented
    and the owner has confirmed a recovery path.
    """
    raise RefusedToSend("the authenticated handshake is not implemented yet; live sending is disabled until "
                        "it is built and verified against a capture (see companion/README.md)")
