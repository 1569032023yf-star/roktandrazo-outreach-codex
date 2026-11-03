"""Original authenticated publisher admission / 原认证发布器安装接线。

No HTTP-supplied approvals, arbitrary paths, DB discovery or automatic replay.
The existing bridge authenticates before calling the original executor.
"""
from contextlib import closing
import re
import secrets

from autonomy import inventory_maintenance as authority
from publisher_channel.install_command import InstallCommand,RELEASES
from publisher_channel.install_inputs import InstallInputPins
from publisher_channel.install_maintenance import InstallMaintenance
from publisher_channel.install_verifier import parse,sha,digest


def reject(reason):raise ValueError('STOP_AND_PRESERVE_ADMISSION_'+reason)


def request(value):
    base={'release_id','invocation_id','action'}
    if type(value) is not dict:reject('REQUEST')
    action=value.get('action')
    if action in ('install','upgrade','rollback'):keys=base|{'target_operation_id'}
    elif action in ('status','reconcile'):keys=base|{'recovery_path'}
    elif action=='compensate':keys=base|{'recovery_path','recovery_id'}
    else:reject('ACTION')
    if (set(value)!=keys or not sha(value.get('invocation_id')) or type(value.get('release_id')) is not str or
            not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',value['release_id'])):reject('REQUEST')
    if action in ('install','upgrade','rollback') and not sha(value['target_operation_id']):reject('TARGET')
    if action=='compensate' and not sha(value['recovery_id']):reject('RECOVERY')
    if 'recovery_path' in value and (type(value['recovery_path']) is not list or len(value['recovery_path'])>8 or
            any(not sha(x) for x in value['recovery_path'])):reject('RECOVERY_PATH')
    if action=='compensate' and len(value['recovery_path'])==8:reject('RECOVERY_DEPTH')
    return dict(value)


class SealedChannel:
    """Hold the existing configuration/scope/seal bytes for the whole operation."""
    def __init__(self,cfg,registry):self.cfg=cfg;self.registry=registry;self.pins=None

    def __enter__(self):
        self.pins=InstallInputPins();self.pins.__enter__()
        try:
            from pathlib import Path
            root=Path(self.cfg['_paths']['releases'])
            if root!=RELEASES:reject('FIXED_RELEASE_ROOT')
            files=(root/'channel_config.json',self.registry.scope_path(self.cfg),self.registry.seal_path(self.cfg))
            raw=[]
            for path in files:
                # These hashes freeze bytes, not approve them. The existing seal
                # must independently match and the loaded configuration must match.
                raw.append(self.pins.add(path,digest(path.read_bytes()),limit=4*1024*1024))
            if parse(raw[0])!={k:v for k,v in self.cfg.items() if not k.startswith('_')}:reject('LOADED_CONFIG_CHANGED')
            parse(raw[1]);parse(raw[2])
            result=self.registry.verify_seal(self.cfg)
            if result.get('sealed') is not True or result.get('tampered') is not False:reject('VALID_SEAL_REQUIRED')
            if self.cfg.get('lock',{}).get('key_prefix')!=authority.PREFIX:reject('ORIGINAL_INVENTORY_LOCK')
            policy=self.cfg.get('u1_install')
            if (type(policy) is not dict or set(policy)!={'inventory_id','approvals'} or
                    policy['inventory_id']!='1784775229336' or type(policy['approvals']) is not dict):reject('SEALED_POLICY_REQUIRED')
            self.approvals=policy['approvals'];self.pins.revalidate();return self
        except BaseException:
            self.pins.__exit__(None,None,None);raise

    def __exit__(self,*args):return self.pins.__exit__(*args)


def reopen(conn,invocation,approval):
    row=conn.execute('SELECT value FROM system_config WHERE key=?',(authority.KEY+':'+invocation,)).fetchone()
    if row is None:return None
    binding=parse(row[0]);authority.binding_bytes(binding)
    if (binding['operation_id']!=invocation or binding['source_commit']!=approval['source_commit'] or
            binding['manifest_sha256']!=approval['manifest_sha256']):reject('RECORDED_BINDING')
    first=conn.execute('SELECT value FROM system_config WHERE key=?',
        (authority.KEY+':session:'+invocation+':000000',)).fetchone()
    if first is None:reject('RECORDED_SESSION_MISSING')
    context=parse(first[0])['context']
    session=InstallMaintenance(conn,binding,target_operation_id=context['target_operation_id'],action=context['action'])
    session._records()  # Verify every chained receipt, not only the first row.
    return session


def status(session):
    rows,_=session._records()
    if not rows:reject('RECORDED_SESSION_MISSING')
    return dict(operation='u1_install',state=rows[-1]['phase'],context=session.context,
                evidence='JOURNAL_ONLY',installer_replayed=False)


def dispatch(cfg,value,executor,registry):
    req=request(value)
    with SealedChannel(cfg,registry) as sealed:
        approval=sealed.approvals.get(req['release_id'])
        if approval is None:reject('RELEASE_NOT_APPROVED')
        adapter=InstallCommand(req['release_id'],approval)
        action=req['action']
        if action!='status' and (approval['allow_install'] is not True or approval['full_chain_review_passed'] is not True):reject('INSTALL_GATE_CLOSED')
        connector=executor.ro_conn if action=='status' else executor.rw_existing_conn
        with closing(connector(cfg['production']['db_path'])) as conn:
            session=reopen(conn,req['invocation_id'],approval)
            if action in ('install','upgrade','rollback'):
                if session is not None:
                    if session.context['action']!=action or session.context['target_operation_id']!=req['target_operation_id']:reject('INVOCATION_CONTEXT_CHANGED')
                    return status(session)  # Duplicate is observation, never replay.
                binding=dict(inventory_id='1784775229336',operation_id=req['invocation_id'],
                    source_commit=approval['source_commit'],manifest_sha256=approval['manifest_sha256'],lease_nonce=secrets.token_hex(32))
                session=InstallMaintenance(conn,binding,target_operation_id=req['target_operation_id'],action=action)
            else:
                if session is None:reject('UNKNOWN_INVOCATION')
                for recovery_id in req['recovery_path']:session=session.compensation_session(recovery_id)
                if action=='status':return status(session)
            with adapter:
                if action in ('install','upgrade','rollback'):proof=session.execute(adapter,adapter.verifier(session))
                elif action=='reconcile':
                    adapter.reconcile_stopped(session)
                    proof=session.reconcile(adapter.verifier(session))
                else:
                    adapter.reconcile_stopped(session)
                    child=session._compensation_child(req['recovery_id'])
                    proof=session.compensate(req['recovery_id'],adapter,adapter.verifier(child),confirm_stopped=adapter.confirm_stopped)
                sealed.pins.revalidate()
                return dict(operation='u1_install',state=proof['outcome'],proof=proof,installer_replayed=False)
