"""Offline independent-install design gate. No filesystem or service mutations."""
import re

SCHEMA = 'rokt.independent-disabled-install-plan.v1'
STATES = ('PREPARED', 'STAGED', 'PUBLISHED', 'REGISTERED_DISABLED', 'VERIFIED')


def plan_install(*, manifest_sha256, original_inventory, target_absent,
                 state_root_absent):
    if type(manifest_sha256) is not str or not re.fullmatch('[0-9a-f]{64}', manifest_sha256):
        raise ValueError('EXACT_MANIFEST_REQUIRED')
    if original_inventory != '1784775229336':
        raise ValueError('ORIGINAL_INVENTORY_REQUIRED')
    if target_absent is not True or state_root_absent is not True:
        raise ValueError('FIRST_INSTALL_ONLY_NO_OVERWRITE')
    return dict(schema=SCHEMA, manifest_sha256=manifest_sha256,
                inventory_id=original_inventory, before='ABSENT', states=list(STATES),
                rollback='UNREGISTER_DISABLED_SERVICE_RETAIN_CODE_AND_STATE',
                allow_install=False, allow_dispatch=False, production_execution=False)


def recovery_action(state, *, receipt_matches, stopped, inventory_lease_valid):
    """An observation cannot authorize a retry or deletion, even at VERIFIED."""
    if state not in STATES:
        raise ValueError('UNKNOWN_OPERATION_STATE')
    trusted = receipt_matches is True and stopped is True and inventory_lease_valid is True
    return dict(action='REVIEW_REGISTRATION_ONLY_ROLLBACK' if trusted else 'STOP_AND_PRESERVE',
                preserve_code=True, preserve_state=True, allow_replay=False,
                allow_delete=False, allow_install=False, allow_dispatch=False)
