"""Offline fault-contract driver for an injected installation adapter.

No Windows adapter, lease issuer, elevation, service command or production entry
point is provided. An adapter's offline marker is a scope declaration, not a
security boundary or proof of authorization.
"""
import hashlib
import json
from typing import Protocol

from autonomy.install_journal import InstallJournal, STEPS, inspect_install


class OfflineInstallAdapter(Protocol):
    offline_only: bool

    def apply(self, step: str, binding: dict) -> None:
        """Apply one isolated test effect; never retry inside the adapter."""

    def readback(self, step: str, binding: dict) -> dict:
        """Return the independently observed exact binding and result."""


def exercise_install_contract(audit_root, operation_id, manifest_sha256,
                              lease_binding, adapter: OfflineInstallAdapter,
                              continue_offline):
    """Persist intent before each effect; any uncertainty stops without rollback.

    continue_offline is an injected test condition, NOT a formal lease verifier.
    Reentering this function with the same operation ID fails at CREATE_NEW,
    before invoking the adapter. Recovery is inspect_install only.
    """
    if adapter.offline_only is not True or continue_offline() is not True:
        raise ValueError('OFFLINE_CONTRACT_ONLY')
    binding = dict(operation_id=operation_id, manifest_sha256=manifest_sha256,
                   lease_binding=lease_binding)
    journal = InstallJournal(audit_root, operation_id, manifest_sha256, lease_binding)
    try:
        for step in STEPS:
            if continue_offline() is not True:
                raise ValueError('OFFLINE_CONDITION_LOST')
            journal.intent(step)
            # A condition may be lost while the intent is flushed. Preserve the
            # pending intent even when no effect was invoked.
            if continue_offline() is not True:
                raise ValueError('OFFLINE_CONDITION_LOST')
            adapter.apply(step, dict(binding))
            observation = adapter.readback(step, dict(binding))
            expected = dict(binding, step=step, outcome='OBSERVED_IN_SANDBOX')
            if type(observation) is not dict or observation != expected:
                raise ValueError('READBACK_BINDING_MISMATCH')
            if continue_offline() is not True:
                raise ValueError('OFFLINE_CONDITION_LOST')
            digest = hashlib.sha256(json.dumps(observation, sort_keys=True,
                                              separators=(',', ':')).encode()).hexdigest()
            journal.receipt(step, digest)
    finally:
        journal.close()
    return inspect_install(journal.path)
