"""Authenticated mapping for the durable ledger; no dispatch or credential IO."""
from autonomy.host_preparation import EvidenceError


class LedgerEvidenceVerifier:
    def __init__(self, consumer, clock):
        self.consumer = consumer
        self.clock = clock

    def __call__(self, envelope):
        try:
            kind = envelope['payload']['kind']
            if kind not in ('authority', 'schedule', 'idle', 'receipt'):
                return None
            payload = self.consumer.verify(envelope, kind=kind, now=self.clock())
            # The mapped names cannot be supplied independently of their signed source.
            if any(k in payload for k in ('inventory', 'observed', 'expires')):
                return None
            if 'expires_at_epoch' not in payload:
                return None
            return dict(payload, inventory=payload['inventory_id'],
                        observed=payload['observed_at_epoch'],
                        expires=payload['expires_at_epoch'])
        except (EvidenceError, KeyError, TypeError):
            return None
