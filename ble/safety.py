"""Read-only access to a BLE device.

``ReadOnlySession`` owns the underlying ``BleakClient`` so no other code ever
holds a reference that can write. The object it yields exposes only GATT
enumeration and reads; anything else raises ``ReadOnlyViolation``.

Deliberately not exposed:
  * write_gatt_char / write_gatt_descriptor  - direct writes
  * start_notify / stop_notify               - these WRITE the CCCD descriptor
  * pair / unpair                            - change bonding state on both ends
"""

from __future__ import annotations

from bleak import BleakClient
from bleak.backends.device import BLEDevice

FORBIDDEN_METHODS = (
    "write_gatt_char",
    "write_gatt_descriptor",
    "start_notify",
    "stop_notify",
    "pair",
    "unpair",
)


class ReadOnlyViolation(RuntimeError):
    """Raised when code tries to use a BLE operation that is not a read."""


class ReadOnlyClient:
    __slots__ = ("_client",)

    def __init__(self, client: BleakClient) -> None:
        object.__setattr__(self, "_client", client)

    @property
    def address(self) -> str:
        return self._client.address

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    @property
    def mtu_size(self) -> int:
        return self._client.mtu_size

    @property
    def services(self):
        return self._client.services

    async def read_gatt_char(self, char) -> bytearray:
        return await self._client.read_gatt_char(char)

    async def read_gatt_descriptor(self, desc) -> bytearray:
        return await self._client.read_gatt_descriptor(desc)

    def __getattr__(self, name: str):
        raise ReadOnlyViolation(
            f"'{name}' is not available: this project only performs read-only BLE operations"
        )

    def __setattr__(self, name: str, value) -> None:
        raise ReadOnlyViolation("ReadOnlyClient is immutable")


class ReadOnlySession:
    """``async with ReadOnlySession(device) as client:`` -> ReadOnlyClient."""

    def __init__(self, device: BLEDevice | str, timeout: float = 20.0) -> None:
        # pair=False: never initiate bonding. Encrypted characteristics will
        # simply fail to read, which is recorded rather than worked around.
        self._client = BleakClient(device, timeout=timeout, pair=False)

    async def __aenter__(self) -> ReadOnlyClient:
        await self._client.connect()
        return ReadOnlyClient(self._client)

    async def __aexit__(self, *exc) -> None:
        await self._client.disconnect()
