"""Durable Windows process evidence / Windows 进程持久凭据。No command endpoint."""
import hashlib
import json
import os
import re

from autonomy import inventory_maintenance as authority
from publisher_channel.install_maintenance import canonical


def digest(value):return hashlib.sha256(canonical(value).encode()).hexdigest()
def reject(reason):raise ValueError('STOP_AND_PRESERVE_PROCESS_'+reason)


class InstallProcessEvidence:
    def __init__(self,session,args,*,cwd=None):
        if (os.name!='nt' or not isinstance(args,(tuple,list)) or not args or
            not all(type(a) is str for a in args) or not os.path.isabs(args[0])):reject('ABSOLUTE_WINDOWS_COMMAND_REQUIRED')
        self.session=session
        self.context=canonical(session.context)
        self.command=digest(dict(args=list(args),cwd=str(cwd) if cwd else None))
        self.image=os.path.normcase(os.path.abspath(args[0]))
        self.key=authority.KEY+':process:'+hashlib.sha256(session.key.encode()).hexdigest()+':'

    def _records(self):
        rows=self.session.conn.execute('SELECT key,value FROM system_config WHERE substr(key,1,?)=? ORDER BY key',
                                       (len(self.key),self.key)).fetchall()
        records=[];previous=''
        for index,(key,raw) in enumerate(rows):
            row=json.loads(raw)
            if (key!=self.key+f'{index:06d}' or canonical(row)!=raw or type(row.get('sequence')) is not int or row.get('sequence')!=index or
                row.get('context')!=self.session.context or row.get('previous_sha256')!=previous or
                row.get('command_sha256')!=self.command or row.get('expected_image')!=self.image):reject('JOURNAL_BINDING')
            self._validate(row.get('event'))
            if row['event']['phase']!=('LAUNCH_INTENT' if index==0 else 'CONTAINED' if index==1 else 'STOPPED' if index==2 else ''):reject('JOURNAL_SEQUENCE')
            if index and row['event']['job_name']!=records[0]['event']['job_name']:reject('JOB_BINDING')
            if index==2 and {k:v for k,v in row['event'].items() if k not in ('phase','tree_empty','readers_closed','reconciled')}!={k:v for k,v in records[1]['event'].items() if k!='phase'}:reject('IDENTITY_CHANGED')
            records.append(row);previous=hashlib.sha256(raw.encode()).hexdigest()
        return records,previous

    def _validate(self,event):
        if type(event) is not dict:reject('EVENT')
        phase=event.get('phase')
        fields={'phase','job_name','command_sha256','supervisor_pid','supervisor_creation_filetime'} if phase=='LAUNCH_INTENT' else {'phase','job_name','pid','creation_filetime','image'}
        if phase=='STOPPED':fields|={'tree_empty','readers_closed'}
        if phase=='STOPPED' and 'reconciled' in event:fields|={'reconciled'}
        if phase not in ('LAUNCH_INTENT','CONTAINED','STOPPED') or set(event)!=fields or not re.fullmatch(r'Global\\RoktU1Install-[0-9a-f]{64}',event.get('job_name','')):reject('EVENT_SCHEMA')
        if phase=='LAUNCH_INTENT':
            if (event['command_sha256']!=self.command or type(event['supervisor_pid']) is not int or
                not 0<event['supervisor_pid']<2**32 or type(event['supervisor_creation_filetime']) is not int or
                event['supervisor_creation_filetime']<=0):reject('COMMAND_BINDING')
        else:
            if (type(event['pid']) is not int or not 0<event['pid']<2**32 or
                type(event['creation_filetime']) is not int or event['creation_filetime']<=0 or
                type(event['image']) is not str or os.path.normcase(event['image'])!=self.image):reject('INSTANCE_BINDING')
            if phase=='STOPPED' and (event['tree_empty'] is not True or event['readers_closed'] is not True or
                                    ('reconciled' in event and event['reconciled'] is not True)):reject('STOP_UNVERIFIED')

    def record(self,event):
        self._validate(event)
        conn=self.session.conn
        try:
            conn.execute('BEGIN IMMEDIATE')
            if canonical(self.session.context)!=self.context:reject('CONTEXT_CHANGED')
            authority.assert_held(conn,self.session.binding)
            sessions,_=self.session._records()
            allowed=('INSTALL_INTENT','UNKNOWN','FINAL_VERIFY_INTENT') if event['phase']=='STOPPED' else ('INSTALL_INTENT',)
            if not sessions or sessions[-1]['phase'] not in allowed:reject('SESSION_NOT_ACTIVE')
            rows,previous=self._records();index=len(rows)
            if event['phase']!=('LAUNCH_INTENT' if index==0 else 'CONTAINED' if index==1 else 'STOPPED' if index==2 else ''):reject('REPLAY_OR_SEQUENCE')
            if index and event['job_name']!=rows[0]['event']['job_name']:reject('JOB_BINDING')
            if index==2 and {k:v for k,v in event.items() if k not in ('phase','tree_empty','readers_closed','reconciled')}!={k:v for k,v in rows[1]['event'].items() if k!='phase'}:reject('IDENTITY_CHANGED')
            row=dict(sequence=index,previous_sha256=previous,context=self.session.context,
                     command_sha256=self.command,expected_image=self.image,event=dict(event))
            conn.execute("INSERT INTO system_config(key,value,updated_at) VALUES(?,?,datetime('now'))",
                         (self.key+f'{index:06d}',canonical(row)))
            conn.commit();return True
        except BaseException:
            conn.rollback();raise

    def confirm_stopped(self,session):
        if session is not self.session or canonical(session.context)!=self.context:reject('CONTEXT_CHANGED')
        authority.assert_held(session.conn,session.binding)
        rows,_=self._records()
        if len(rows)!=3:reject('TERMINATION_UNKNOWN')
        return dict(context=session.context,stopped=True,process_identity_sha256=digest(rows[1]['event']))

    def reconcile_stopped(self):
        """Explicit read-only OS reconciliation; never launch or terminate/replay."""
        rows,_=self._records()
        if len(rows)==3:return self.confirm_stopped(self.session)
        if len(rows)!=2:reject('INSTANCE_UNKNOWN')
        instance=rows[1]['event']
        _windows_stopped(instance,rows[0]['event'])
        # Readers belong to the original supervisor. An extant named job with
        # zero members is insufficient to prove that supervisor/readers are gone.
        # _windows_stopped requires the job object itself to be absent.
        self.record(dict(instance,phase='STOPPED',tree_empty=True,readers_closed=True,reconciled=True))
        return self.confirm_stopped(self.session)


def _windows_stopped(instance,supervisor):
    import ctypes as c
    from ctypes import wintypes as w
    k=c.WinDLL('kernel32',use_last_error=True)
    k.OpenJobObjectW.argtypes=[w.DWORD,w.BOOL,w.LPCWSTR];k.OpenJobObjectW.restype=w.HANDLE
    k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
    k.GetProcessTimes.argtypes=[w.HANDLE,*([c.POINTER(w.FILETIME)]*4)];k.GetProcessTimes.restype=w.BOOL
    k.WaitForSingleObject.argtypes=[w.HANDLE,w.DWORD];k.WaitForSingleObject.restype=w.DWORD
    k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
    def dead(pid,creation):
        c.set_last_error(0);process=k.OpenProcess(0x100000|0x1000,False,pid)
        if not process:
            if c.get_last_error()==87:return True
            reject('PID_OBSERVATION_UNKNOWN')
        try:
            times=[w.FILETIME() for _ in range(4)]
            if not k.GetProcessTimes(process,*(c.byref(t) for t in times)):reject('PID_IDENTITY_UNKNOWN')
            created=(times[0].dwHighDateTime<<32)|times[0].dwLowDateTime
            if created!=creation:return True
            if k.WaitForSingleObject(process,0)!=0:reject('INSTANCE_STILL_LIVE')
            return True
        finally:
            if not k.CloseHandle(process):reject('OBSERVATION_HANDLE_CLOSE_FAILED')
    job=None
    try:
        dead(supervisor['supervisor_pid'],supervisor['supervisor_creation_filetime'])
        c.set_last_error(0);job=k.OpenJobObjectW(4,False,instance['job_name'])
        if job:reject('SUPERVISOR_OR_JOB_STILL_PRESENT')
        if c.get_last_error()!=2:reject('JOB_OBSERVATION_UNKNOWN')
        return dead(instance['pid'],instance['creation_filetime'])
    finally:
        if job and not k.CloseHandle(job):reject('OBSERVATION_HANDLE_CLOSE_FAILED')
