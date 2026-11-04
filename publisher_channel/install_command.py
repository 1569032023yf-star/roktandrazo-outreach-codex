"""Fixed internal installer adapter / 固定内部安装命令适配。

Approval is trusted sealed publisher configuration, NEVER an HTTP request body.
Original authentication/seal admission must be wired before enabling this adapter.
"""
import ctypes
import re
import time
from pathlib import Path

from autonomy.disabled_host_package import RUNTIME_PATHS
from autonomy.process_job import run_tree
from publisher_channel.install_inputs import InstallInputPins,pin_package,reject
from publisher_channel.install_process import InstallProcessEvidence
from publisher_channel.install_verifier import InstallVerifier,parse,sha

RELEASES=Path(__file__).resolve().parent.parent/'releases'


def windows_root():
    api=ctypes.WinDLL('kernel32',use_last_error=True)
    api.GetWindowsDirectoryW.argtypes=[ctypes.c_wchar_p,ctypes.c_uint];api.GetWindowsDirectoryW.restype=ctypes.c_uint
    buffer=ctypes.create_unicode_buffer(32768);size=api.GetWindowsDirectoryW(buffer,len(buffer))
    if not 0<size<len(buffer):reject('WINDOWS_DIRECTORY')
    return Path(buffer.value)


class InstallCommand:
    def __init__(self,release_id,approval):
        required={'source_commit','manifest_sha256','runtime_plan_sha256','powershell_sha256','generated_files',
                  'previous_receipt_sha256','allow_install','full_chain_review_passed','allow_dispatch','allow_cancel_dispatch','smtp_enabled'}
        if (type(release_id) is not str or not re.fullmatch('[a-z0-9][a-z0-9._-]{0,63}',release_id) or
            release_id in ('.','..') or type(approval) is not dict or set(approval)!=required or
            not re.fullmatch('[0-9a-f]{40}',approval.get('source_commit','')) or
            any(not sha(approval[k]) for k in ('manifest_sha256','runtime_plan_sha256','powershell_sha256')) or
            (approval['previous_receipt_sha256'] is not None and not sha(approval['previous_receipt_sha256'])) or
            type(approval['generated_files']) is not dict or set(approval['generated_files'])!={'config/runtime.json','config/supervisor.json'} or
            any(not sha(v) for v in approval['generated_files'].values()) or
            any(type(approval[k]) is not bool for k in ('allow_install','full_chain_review_passed','allow_dispatch','allow_cancel_dispatch','smtp_enabled')) or
            any(approval[k] for k in ('allow_dispatch','allow_cancel_dispatch','smtp_enabled'))):reject('SEALED_INSTALL_APPROVAL')
        self.approval=dict(approval,generated_files=dict(approval['generated_files']))
        self.package=RELEASES/release_id/'payload'/'host'
        self.plan_path=RELEASES/release_id/'u1-runtime-plan.json'
        self.pins=None;self.used=False

    def __enter__(self):
        if self.used:reject('COMMAND_SINGLE_USE')
        self.used=True;self.pins=InstallInputPins();self.pins.__enter__()
        try:
            a=self.approval
            self.manifest=pin_package(self.pins,self.package,a['manifest_sha256'],a['source_commit'])
            self.windows=windows_root()
            self.shell=self.windows/'System32/WindowsPowerShell/v1.0/powershell.exe'
            self.pins.add_system_component(self.shell,a['powershell_sha256'])
            self.plan=parse(self.pins.add(self.plan_path,a['runtime_plan_sha256'],limit=1024*1024))
            keys={'schema','inventory_id','python','python_sha256','release_root','token_file','token_sha256','credential_expires_at','snapshot','snapshot_sha256'}
            p=self.plan
            if (type(p) is not dict or set(p) not in (keys,keys|{'event_runtime'},keys|{'original_owner_db'}) or p.get('schema')!='rokt.u1-provision-plan.v1' or
                p.get('inventory_id')!='1784775229336' or type(p.get('credential_expires_at')) is not int):reject('RUNTIME_PLAN')
            for key,digest in (('python','python_sha256'),('token_file','token_sha256'),('snapshot','snapshot_sha256')):
                self.pins.add(p[key],p[digest])
            if 'original_owner_db' in p:
                self.pins.add_mutable_reference(p['original_owner_db'])
            # Every ancestor of referenced runtime directories is also held;
            # reference directories are not supplied as installation targets.
            for key in ('release_root','event_runtime'):
                if key in p:
                    path=self.pins.path(p[key]);self.pins._parents(path/'fixed-reference')
            deps=parse(self.pins.add(self.package/'runtime/dependencies.json',next(r['sha256'] for r in self.manifest['files'] if r['path']=='runtime/dependencies.json')))
            if (deps.get('schema')!='rokt.disabled-host-runtime.v1' or deps.get('framework')!='.NET Framework 4 x64' or
                type(deps.get('files')) is not dict or set(deps['files'])!=set(RUNTIME_PATHS)):reject('RUNTIME_DEPENDENCIES')
            for key,path in RUNTIME_PATHS.items():
                row=deps['files'][key]
                if row.get('path')!=path:reject('RUNTIME_FIXED_PATH')
                self.pins.add_system_component(self.windows/path,row['sha256'])
            self.expected_files={row['path']:row['sha256'] for row in self.manifest['files']}
            self.expected_files.update(a['generated_files'])
            self.pins.revalidate();return self
        except BaseException:
            self.pins.__exit__(None,None,None);raise

    def command(self,session):
        if self.pins is None or not self.pins.active:reject('COMMAND_NOT_PINNED')
        a=self.approval
        if session.binding['source_commit']!=a['source_commit'] or session.binding['manifest_sha256']!=a['manifest_sha256']:reject('SESSION_BINDING')
        if session.context['action']=='upgrade' and a['previous_receipt_sha256'] is None:reject('UPGRADE_OWNERSHIP_REQUIRED')
        args=[str(self.shell),'-NoProfile','-NonInteractive','-File',str(self.package/'Publisher-InstallHost.ps1'),
              '-PackageRoot',str(self.package),'-ApprovedManifestSha256',a['manifest_sha256'],'-ApprovedSourceCommit',a['source_commit'],
              '-RuntimePlan',str(self.plan_path),'-ApprovedRuntimePlanSha256',a['runtime_plan_sha256'],
              '-OperationId',session.context['target_operation_id'],'-Action',session.context['action']]
        if a['previous_receipt_sha256'] is not None:args+=['-ApprovedPreviousReceiptSha256',a['previous_receipt_sha256']]
        return args

    def process(self,session):return InstallProcessEvidence(session,self.command(session),cwd=self.package)

    def __call__(self,session):
        # A hash, local mutex or caller-supplied session is not an install grant.
        if self.approval['allow_install'] is not True or self.approval['full_chain_review_passed'] is not True:reject('INSTALL_GATE_CLOSED')
        args=self.command(session);self.pins.revalidate()
        if session.context['action'] in ('install','upgrade') and self.plan['credential_expires_at']<=time.time():reject('CREDENTIAL_EXPIRED')
        live=session.process_guard()
        def check():
            if not self.pins.active:reject('PINS_NOT_ACTIVE')
            return live()
        result=run_tree(args,timeout=300,cwd=self.package,assert_live=check,
                        maintenance_handler=session.maintenance_handler(),lifecycle=self.process(session).record)
        self.pins.revalidate()
        if result.returncode!=0:reject('INSTALLER_RETURNED_FAILURE')
        return result

    def confirm_stopped(self,session):return self.process(session).confirm_stopped(session)
    def confirm_unstarted(self,session):return self.process(session).confirm_unstarted(session)
    def reconcile_stopped(self,session):return self.process(session).reconcile_stopped()

    def verifier(self,session):
        # Observation uses the same pinned script/image for its entire lifetime.
        # Its read-only process is separate from the recorded installer instance.
        self.command(session)
        def observe(operation,nonce):
            if operation!=session.context['target_operation_id'] or not sha(nonce):reject('OBSERVER_CONTEXT')
            def held():
                if not self.pins.active:reject('PINS_NOT_ACTIVE')
                return session.assert_held(operation,self.approval['source_commit'],self.approval['manifest_sha256'],session.context['action'])
            held();self.pins.revalidate()
            args=[str(self.shell),'-NoProfile','-NonInteractive','-File',str(self.package/'Observe-HostInstall.ps1'),
                  '-OperationId',operation,'-Nonce',nonce]
            result=run_tree(args,timeout=30,cwd=self.package,assert_live=held,
                            stdout_limit_bytes=1024*1024,stderr_limit_bytes=65536)
            self.pins.revalidate()
            if result.returncode!=0 or result.stderr.strip():reject('OBSERVER_RETURNED_FAILURE')
            value=parse(result.stdout)
            if type(value) is not dict or value.get('operation_id')!=operation or value.get('nonce')!=nonce:reject('OBSERVER_CONTEXT')
            return value
        return InstallVerifier(self.expected_files,previous_receipt_sha256=self.approval['previous_receipt_sha256'],
                               observe=observe,confirm_stopped=self.confirm_stopped)

    def __exit__(self,*args):return self.pins.__exit__(*args)
