"""Scoped local-ledger identity guard; not a substitute for the Inventory lock."""
from contextvars import ContextVar


CURRENT = ContextVar('u1_local_ledger_binding', default=None)


class LedgerBindingError(RuntimeError):
    pass


def binding_for(ledger, kind):
    binding = CURRENT.get()
    if binding is not None:
        binding.check(ledger=ledger, kind=kind)
    return binding
