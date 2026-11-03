"""Independent read-only terminal checks / 独立只读终态核验。

The trusted publisher supplies exact approved payload hashes, a pinned Windows
observer and verified process-instance quiescence. No command/DB/path discovery,
installation, recovery, replay or release operation is provided by this module.
"""
import base64
import hashlib
import json
from pathlib import Path
import re
import secrets

from autonomy.host_file_transaction import ordinary, read, name, fingerprint

CODE=Path(r'C:\Program Files\RoktU1Bridge\v1')
STATE=Path(r'C:\ProgramData\RoktU1Bridge')
AUDIT=Path(r'C:\ProgramData\RoktU1InstallAudit')
SERVICE='RoktU1Bridge'
ACCOUNT=r'NT SERVICE\RoktU1Bridge'
RECEIPT='config/installation.json'
TRUSTED={'S-1-5-18','S-1-5-32-544'}


def reject(reason):raise ValueError('STOP_AND_PRESERVE_FINAL_'+reason)
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),allow_nan=False).encode()
def digest(raw):return hashlib.sha256(raw).hexdigest()
def sha(value):return type(value) is str and re.fullmatch('[0-9a-f]{64}',value) is not None


def pairs(values):
    result={}
    for key,value in values:
        if key in result:reject('DUPLICATE_JSON_KEY')
        result[key]=value
    return result


def parse(raw):
    return json.loads(raw,object_pairs_hook=pairs,
                      parse_constant=lambda _:reject('NONFINITE_JSON'))


def identity(path):
    path=ordinary(path)
    if not path.exists():return None
    if not path.is_dir():reject('DIRECTORY_TYPE')
    info=path.stat()
    return [info.st_dev,info.st_ino]


class InstallVerifier:
    def __init__(self, expected_files, *, previous_receipt_sha256=None, observe, confirm_stopped):
        # Internal trusted inputs; roots cannot be overridden by an API request.
        if (type(expected_files) is not dict or not 0<len(expected_files)<512 or
            RECEIPT in expected_files or any(not sha(v) for v in expected_files.values()) or
            (previous_receipt_sha256 is not None and not sha(previous_receipt_sha256)) or
            not callable(observe) or not callable(confirm_stopped)):
            reject('EXPECTED_RELEASE')
        folded=[]
        for path in expected_files:
            lower=name(path).casefold()
            if any(lower==p or lower.startswith(p+'/') or p.startswith(lower+'/') for p in folded):reject('PATH_COLLISION')
            folded.append(lower)
        self.files=dict(expected_files)
        self.previous=previous_receipt_sha256
        self.observe=observe
        self.confirm_stopped=confirm_stopped

    def _stopped(self,session):
        proof=self.confirm_stopped(session)
        if (type(proof) is not dict or set(proof)!={'context','stopped','process_identity_sha256'} or
            proof['context']!=session.context or proof['stopped'] is not True or not sha(proof['process_identity_sha256'])):
            reject('PROCESS_NOT_QUIESCENT')
        return proof

    def _snapshot(self,operation):
        nonce=secrets.token_hex(32)
        result=self.observe(operation,nonce)
        if (type(result) is not dict or set(result)!={'schema','operation_id','nonce','audit_trusted','journals','roots','service','service_sid'} or
            result['schema']!='rokt.u1-install-observation.v1' or result['operation_id']!=operation or
            result['nonce']!=nonce or result['audit_trusted'] is not True or
            type(result['journals']) is not dict or set(result['journals'])!={'install','files','acl','state_create'} or
            any(v is not None and not sha(v) for v in result['journals'].values()) or
            type(result['roots']) is not dict or set(result['roots'])!={'code','state'}):reject('OBSERVER_BINDING')
        return result

    def _journals(self,operation,snapshot):
        result={}
        for key,relative in dict(install=f'install-{operation}.jsonl',files=f'files-{operation}.jsonl',
                                 acl=f'acl-{operation}.jsonl',state_create=f'acl-{operation}.jsonl.state-create.jsonl').items():
            raw=read(AUDIT/relative)
            if (None if raw is None else digest(raw))!=snapshot['journals'][key]:reject('JOURNAL_CHANGED')
            if raw is None:result[key]=[];continue
            if len(raw)>64*1024*1024 or not raw.endswith(b'\n'):reject('TORN_OR_OVERSIZE_JOURNAL')
            rows=[parse(line) for line in raw.splitlines()]
            if not rows or any(type(r) is not dict for r in rows):reject('JOURNAL_ROWS')
            if key=='files':
                for index,row in enumerate(rows):
                    if type(row.get('sequence')) is not int or row['sequence']!=index or row.get('previous')!=(digest(canonical(rows[index-1])) if index else None):reject('FILE_JOURNAL_CHAIN')
            result[key]=rows
        return result

    def _receipt(self,raw,session,current):
        if raw is None:reject('RECEIPT_ABSENT')
        r=parse(raw)
        image='"'+str(CODE)+r'\service\RoktU1Bridge.exe"'
        if (type(r) is not dict or r.get('schema')!='rokt.disabled-host-install-receipt.v2' or
            r.get('service_name')!=SERVICE or r.get('account')!=ACCOUNT or r.get('image')!=image or
            type(r.get('files')) is not dict or RECEIPT in r['files'] or not 0<len(r['files'])<512 or
            any(not sha(v) for v in r['files'].values())):reject('OWNERSHIP_RECEIPT')
        for path in r['files']:name(path)
        if current and (r.get('source_commit')!=session.binding['source_commit'] or
            r.get('manifest_sha256')!=session.binding['manifest_sha256'] or
            r.get('operation_id')!=session.context['target_operation_id'] or r.get('installer_version')!='1.1.1' or
            r['files']!=self.files or r.get('wrapper_sha256')!=self.files.get('service/RoktU1Bridge.exe') or
            r.get('state_preserved') is not True):reject('CURRENT_RECEIPT_BINDING')
        return r['files']

    def _files(self,rows,session,outcome,upgrade):
        if not rows:
            if outcome=='COMMITTED':reject('FILE_PLAN_ABSENT')
            if upgrade:
                raw=read(CODE/RECEIPT)
                if fingerprint(raw)!=self.previous:reject('PREVIOUS_RECEIPT')
                old=self._receipt(raw,session,False)
                for path,expected in old.items():
                    if fingerprint(read(CODE/path))!=expected:reject('OLD_FILE_CHANGED')
            return {}
        header=rows[0]
        if (header.get('phase')!='PREPARED' or header.get('root')!=str(CODE) or
            header.get('manifest_sha256')!=session.binding['manifest_sha256'] or
            type(header.get('root_created')) is not bool or header['root_created']==upgrade or
            header.get('previous_receipt_sha256')!=self.previous or type(header.get('plan')) is not list):reject('FILE_PLAN_BINDING')
        plan=header['plan'];scope={};folded=[]
        for item in plan:
            path=name(item['path']);lower=path.casefold()
            if any(lower==p or lower.startswith(p+'/') or p.startswith(lower+'/') for p in folded):reject('PLAN_PATH_COLLISION')
            folded.append(lower);scope[path]=item
            for field,blob in (('before','backup'),('after','content')):
                raw=None if item[blob] is None else base64.b64decode(item[blob],validate=True)
                if fingerprint(raw)!=item[field]:reject('PLAN_CONTENT_HASH')
        if RECEIPT not in scope:reject('PLAN_RECEIPT')
        old={}
        if upgrade:
            raw=base64.b64decode(scope[RECEIPT]['backup'],validate=True)
            if digest(raw)!=self.previous:reject('PREVIOUS_RECEIPT')
            old=self._receipt(raw,session,False);old[RECEIPT]=self.previous
        current=dict(self.files)
        raw=base64.b64decode(scope[RECEIPT]['content'],validate=True)
        self._receipt(raw,session,True);current[RECEIPT]=digest(raw)
        if set(scope)!=set(old)|set(current):reject('EXACT_FILE_SCOPE')
        observed={}
        for path,item in scope.items():
            if item['before']!=old.get(path,'ABSENT') or item['after']!=current.get(path,'ABSENT'):reject('PLAN_OWNERSHIP')
            actual=fingerprint(read(CODE/path));observed[path]=actual
            if actual!=item['after' if outcome=='COMMITTED' else 'before']:reject('ACTUAL_FILE_CHANGED')
            if read((CODE/path).with_name(Path(path).name+'.u1-new')) is not None:reject('STAGING_ARTIFACT')
        phase=rows[-1].get('phase')
        if outcome=='COMMITTED':
            if phase!='FILES_APPLIED' or identity(CODE)!=header['root_identity']:reject('FILES_NOT_COMMITTED')
            if not upgrade and (header.get('state_root')!=str(STATE) or identity(STATE)!=header['state_identity']):reject('STATE_IDENTITY')
        elif phase!=('DIRECTORIES_PRUNED' if upgrade else 'ROOT_REMOVED'):reject('FILES_NOT_ROLLED_BACK')
        if outcome=='ROLLED_BACK' and upgrade:
            if identity(CODE)!=header['root_identity']:reject('OLD_CODE_IDENTITY')
            for relative,before in header['directories'].items():
                # Exact plan-derived ancestors only; never follow an arbitrary
                # journal path outside the code root.
                allowed={str(p.relative_to(CODE)).replace('\\','/') for path in scope for p in (CODE/path).parents if p!=CODE and CODE in p.parents}
                if relative not in allowed:reject('DIRECTORY_SCOPE')
                if before=='ABSENT' and ordinary(CODE/relative).exists():reject('CREATED_DIRECTORY_REMAINS')
        return observed

    def _system(self,snapshot,rows,header,outcome,upgrade):
        service=snapshot['service'];roots=snapshot['roots']
        image='"'+str(CODE)+r'\service\RoktU1Bridge.exe"'
        if outcome=='ROLLED_BACK' and not upgrade:
            if service is not None or any(v is not None for v in roots.values()) or identity(CODE) is not None or identity(STATE) is not None:reject('ABSENT_NOT_RESTORED')
            return
        if service!={'name':SERVICE,'start_mode':'Disabled','state':'Stopped','account':ACCOUNT,'image':image}:reject('SERVICE_NOT_DISABLED_STOPPED')
        for key,path in (('code',CODE),('state',STATE)):
            if roots[key] is None or identity(path) is None:reject('ROOT_MISSING')
            if upgrade and identity(path)!=header['roots_before'][key]:reject('ROOT_IDENTITY_CHANGED')
        if rows:
            acl=rows[0]
            if acl.get('kind')!='PREPARED' or acl.get('schema')!='rokt.acl-transaction.v1' or acl.get('manifest')!=header['manifest'] or len(acl.get('targets',[]))!=2:reject('ACL_BINDING')
            for index,key in enumerate(('code','state')):
                target=acl['targets'][index]
                if target['path']!=str(CODE if key=='code' else STATE):reject('ACL_PATH_BINDING')
                if upgrade and target['before']!=header['acl_before'][key]:reject('ACL_BEFORE_BINDING')
        if outcome=='ROLLED_BACK':
            if any(roots[k]['sddl']!=header['acl_before'][k] for k in ('code','state')):reject('OLD_ACL_NOT_RESTORED')
            if rows and rows[-1].get('kind')!='ABORTED':reject('ACL_NOT_ROLLED_BACK')
            return
        sid=snapshot['service_sid']
        if type(sid) is not str or not re.fullmatch(r'S-1-5-80-(\d+-){4}\d+',sid):reject('SERVICE_SID')
        if roots['code']['protected'] is not False or roots['state']['protected'] is not True:reject('ACL_INHERITANCE')
        def required(ace,identity,rights):
            return (ace.get('sid')==identity and ace.get('type')=='Allow' and type(ace.get('rights')) is int and
                    ace['rights']&rights==rights and ace.get('inheritance')==3 and ace.get('propagation')==0)
        if not any(required(a,sid,131241) for a in roots['code']['aces']):reject('CODE_SERVICE_RX')
        aces=roots['state']['aces']
        if len(aces)!=3 or any(not any(required(a,i,r) and a['rights']&~(r|1048576)==0 for i,r in [(sid,197055),('S-1-5-18',2032127),('S-1-5-32-544',2032127)]) for a in aces):reject('STATE_ACL_POLICY')
        if {a['sid'] for a in aces}!=TRUSTED|{sid}:reject('STATE_ACL_IDENTITIES')
        if not rows or rows[0].get('kind')!='PREPARED' or rows[-1].get('kind')!='COMMITTED':reject('ACL_TERMINAL')
        acl=rows[0]
        if acl.get('schema')!='rokt.acl-transaction.v1' or acl.get('manifest')!=header['manifest'] or len(acl.get('targets',[]))!=2:reject('ACL_BINDING')
        for index,key in enumerate(('code','state')):
            target=acl['targets'][index]
            if target['path']!=str(CODE if key=='code' else STATE) or target['after']!=roots[key]['sddl']:reject('ACL_ACTUAL_CHANGED')
            if upgrade and target['before']!=header['acl_before'][key]:reject('ACL_BEFORE_BINDING')

    def __call__(self,session,_installer_output):
        stopped=self._stopped(session)
        operation=session.context['target_operation_id']
        session.assert_held(operation,session.binding['source_commit'],session.binding['manifest_sha256'],session.context['action'])
        first=self._snapshot(operation);journals=self._journals(operation,first)
        host=journals['install']
        if not host or any(r.get('operation_id')!=operation or r.get('manifest')!=session.binding['manifest_sha256'] for r in host):reject('HOST_BINDING')
        header=host[0];outcome=host[-1].get('phase');upgrade=self.previous is not None
        if (header.get('phase')!='PREPARED' or type(header.get('extra')) is not dict or
            type(header['extra'].get('upgrade')) is not bool or header['extra']['upgrade']!=upgrade or
            header['extra'].get('previous_receipt_sha256') not in ([self.previous] if upgrade else [None,'']) or
            header['extra'].get('image')!='"'+str(CODE)+r'\service\RoktU1Bridge.exe"' or
            set(header['extra'].get('roots_before',{}))!={'code','state'} or
            outcome not in ('COMMITTED','ROLLED_BACK') or
            (session.context['action'] in ('recover','rollback') and outcome!='ROLLED_BACK')):reject('HOST_TERMINAL')
        before=header['extra']
        if not upgrade and (any(v is not None for v in before['roots_before'].values()) or before.get('acl_before') is not None):reject('ABSENT_PRECONDITION')
        if upgrade and (any(v is None for v in before['roots_before'].values()) or type(before.get('acl_before')) is not dict or set(before['acl_before'])!={'code','state'}):reject('UPGRADE_PRECONDITION')
        files=self._files(journals['files'],session,outcome,upgrade)
        self._system(first,journals['acl'],dict(before,manifest=header['manifest']),outcome,upgrade)
        second=self._snapshot(operation)
        if {k:v for k,v in first.items() if k!='nonce'}!={k:v for k,v in second.items() if k!='nonce'}:reject('UNSTABLE_OBSERVATION')
        if self._stopped(session)!=stopped:reject('PROCESS_IDENTITY_CHANGED')
        # Detect writes after the initial read without trusting installer stdout.
        if self._files(journals['files'],session,outcome,upgrade)!=files:reject('UNSTABLE_FILES')
        self._journals(operation,second)
        evidence=dict(context=session.context,outcome=outcome,observation=second,files=files,process=stopped)
        # Evidence is durable under the same maintenance session before release.
        session._transition('FINAL_VERIFY_INTENT',dict(terminal_evidence=evidence))
        return dict(context=session.context,outcome=outcome,evidence_sha256=digest(canonical(evidence)))
