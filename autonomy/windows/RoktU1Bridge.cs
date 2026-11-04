// Minimal SCM candidate: local unsigned heartbeat only. No listener or dispatcher.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.ServiceProcess;
using System.Text;
using System.Threading;
using System.Runtime.InteropServices;
using System.Security.Cryptography;
using System.Web.Script.Serialization;

public sealed class RoktU1Bridge : ServiceBase {
    const string Inventory = "1784775229336";
    const string StateRoot = @"C:\ProgramData\RoktU1Bridge";
    readonly object gate = new object();
    Timer timer;
    bool stopping;
    ServiceChild child;
    readonly string instance = Guid.NewGuid().ToString("N");
    readonly string started = DateTime.UtcNow.ToString("o");
    public RoktU1Bridge() { ServiceName="RoktU1Bridge"; CanStop=true; AutoLog=false; }
    public static bool ValidateConfig(string text) {
        if (text==null || text.Length>4096) return false;
        try {
            var c=new JavaScriptSerializer().Deserialize<Dictionary<string,object>>(text);
            if(c==null || c.Count!=7) return false;
            object v;
            if(!c.TryGetValue("schema",out v) || !(v is string) || (string)v!="rokt.disabled-host-config.v1") return false;
            if(!c.TryGetValue("inventory_id",out v) || !(v is string) || (string)v!=Inventory) return false;
            if(!c.TryGetValue("service_name",out v) || !(v is string) || (string)v!="RoktU1Bridge") return false;
            foreach(string k in new[]{"allow_dispatch","allow_cancel_dispatch","smtp_enabled","scheduler_created"})
                if(!c.TryGetValue(k,out v) || !(v is bool) || (bool)v) return false;
            return true;
        } catch { return false; }
    }
    protected override void OnStart(string[] args) {
        if(args.Length!=0 || !Environment.Is64BitProcess) throw new InvalidOperationException("HOST_CONTEXT_REJECTED");
        string config=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","config","host.json");
        if(new FileInfo(config).Length>4096 || !ValidateConfig(File.ReadAllText(config,Encoding.UTF8)) || !Directory.Exists(StateRoot))
            throw new InvalidOperationException("HOST_CONFIG_REJECTED");
        string supervisor=Path.Combine(AppDomain.CurrentDomain.BaseDirectory,"..","config","supervisor.json");
        // Optional staged integration; absent config preserves disabled heartbeat candidate.
        if(File.Exists(supervisor)) child=ServiceChild.FromConfig(supervisor);
        try { WriteHeartbeat(); } catch { if(child!=null) child.Dispose(); throw; }
        timer=new Timer(delegate { try { lock(gate) { if(!stopping) { if(child!=null && child.HasExited) throw new InvalidOperationException("PYTHON_CHILD_EXITED"); WriteHeartbeat(); } } } catch { Environment.Exit(3); } },null,10000,10000);
    }
    void WriteHeartbeat() {
        var facts=new Dictionary<string,object> {
            {"schema","rokt.local-heartbeat.v1"},{"inventory_id",Inventory},
            {"instance_id",instance},{"process_id",Process.GetCurrentProcess().Id},
            {"started_utc",started},{"observed_utc",DateTime.UtcNow.ToString("o")},
            {"allow_dispatch",false},{"allow_cancel_dispatch",false},
            {"smtp_enabled",false},{"scheduler_created",false},
            {"signature","UNSIGNED_LOCAL_OBSERVATION"}
        };
        string target=Path.Combine(StateRoot,"heartbeat.json");
        string temp=Path.Combine(StateRoot,"heartbeat."+Guid.NewGuid().ToString("N")+".tmp");
        byte[] raw=Encoding.UTF8.GetBytes(new JavaScriptSerializer().Serialize(facts));
        using(var s=new FileStream(temp,FileMode.CreateNew,FileAccess.Write,FileShare.None,4096,FileOptions.WriteThrough)) {
            s.Write(raw,0,raw.Length);s.Flush(true);
        }
        if(File.Exists(target)) File.Replace(temp,target,null); else File.Move(temp,target);
    }
    protected override void OnStop() {
        lock(gate) { stopping=true;if(child!=null) { child.Dispose();child=null; } if(timer!=null) { timer.Dispose();timer=null; } }
    }
    public static int Main(string[] args) {
        if(args.Length==4 && args[0]=="--validate-runtime") {
            try { using(var pins=new ServiceChild()) { pins.PinRuntime(args[1],args[2],args[3]); }
                Console.WriteLine("VALID_PINNED_RUNTIME");return 0;
            } catch { Console.WriteLine("REJECTED_RUNTIME");return 2; }
        }
        if(args.Length==1 && args[0]=="--validate-config") {
            char[] input=new char[4097];int count=0,n;
            while(count<input.Length && (n=Console.In.Read(input,count,input.Length-count))>0) count+=n;
            bool ok=count<=4096 && ValidateConfig(new string(input,0,count));Console.WriteLine(ok?"VALID_DISABLED_CONFIG":"REJECTED");return ok?0:2;
        }
        if(args.Length!=0) return 2;
        ServiceBase.Run(new RoktU1Bridge());return 0;
    }
}

// Suspended-create -> Job assignment -> resume. Parent death closes the job and
// kills descendants. Never launch a child outside this sequence as a fallback.
public sealed class ServiceChild : IDisposable {
    [StructLayout(LayoutKind.Sequential)] struct FileFacts {
        public uint attributes;public System.Runtime.InteropServices.ComTypes.FILETIME created,accessed,written;
        public uint volume,sizeHigh,sizeLow,links,indexHigh,indexLow;
    }
    [DllImport("kernel32",SetLastError=true)] static extern bool GetFileInformationByHandle(IntPtr handle,out FileFacts facts);
    [DllImport("kernel32",CharSet=CharSet.Unicode,SetLastError=true)] static extern IntPtr CreateFileW(string path,uint access,uint share,IntPtr security,uint disposition,uint flags,IntPtr template);
    readonly Dictionary<string,Microsoft.Win32.SafeHandles.SafeFileHandle> directoryPins=new Dictionary<string,Microsoft.Win32.SafeHandles.SafeFileHandle>(StringComparer.OrdinalIgnoreCase);
    [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] struct Startup {
        public int cb; public string reserved, desktop, title;
        public int x,y,xsize,ysize,xchars,ychars,fill,flags; public short show,reserved2;
        public IntPtr reservedPtr,input,output,error;
    }
    [StructLayout(LayoutKind.Sequential)] struct ProcessInfo { public IntPtr process,thread; public int pid,tid; }
    [StructLayout(LayoutKind.Sequential)] struct Basic {
        public long processTime,jobTime; public uint flags; public UIntPtr min,max;
        public uint active; public UIntPtr affinity; public uint priority,scheduling;
    }
    [StructLayout(LayoutKind.Sequential)] struct Io { public ulong a,b,c,d,e,f; }
    [StructLayout(LayoutKind.Sequential)] struct Extended { public Basic basic;public Io io;public UIntPtr processMemory,jobMemory,peakProcess,peakJob; }
    [DllImport("kernel32",SetLastError=true)] static extern IntPtr CreateJobObject(IntPtr sa,string name);
    [DllImport("kernel32",SetLastError=true)] static extern bool SetInformationJobObject(IntPtr job,int kind,ref Extended limits,int length);
    [DllImport("kernel32",CharSet=CharSet.Unicode,SetLastError=true)] static extern bool CreateProcess(string app,StringBuilder cmd,IntPtr pa,IntPtr ta,bool inherit,uint flags,IntPtr env,string cwd,ref Startup startup,out ProcessInfo info);
    [DllImport("kernel32",SetLastError=true)] static extern bool AssignProcessToJobObject(IntPtr job,IntPtr process);
    [DllImport("kernel32",SetLastError=true)] static extern uint ResumeThread(IntPtr thread);
    [DllImport("kernel32")] static extern bool TerminateProcess(IntPtr process,uint code);
    [DllImport("kernel32")] static extern bool TerminateJobObject(IntPtr job,uint code);
    [DllImport("kernel32")] static extern uint WaitForSingleObject(IntPtr handle,uint ms);
    [DllImport("kernel32")] static extern bool CloseHandle(IntPtr handle);
    [StructLayout(LayoutKind.Sequential)] struct Accounting { public long a,b,c,d;public uint faults,total,active,terminated; }
    [DllImport("kernel32",SetLastError=true)] static extern bool QueryInformationJobObject(IntPtr job,int kind,out Accounting info,int length,IntPtr returned);
    IntPtr job,process;
    readonly List<FileStream> pins=new List<FileStream>();
    public bool HasExited { get { return process==IntPtr.Zero || WaitForSingleObject(process,0)!=258; } }
    static string Quoted(string path) {
        if(!Path.IsPathRooted(path) || path.IndexOfAny(new[]{'"','\r','\n'})>=0 || path.EndsWith("\\")) throw new InvalidOperationException("UNSAFE_CHILD_PATH");
        return "\""+path+"\"";
    }
    void Pin(string path,string expected) {
        Quoted(path);
        if(expected==null || !System.Text.RegularExpressions.Regex.IsMatch(expected,"^[0-9a-f]{64}$")) throw new InvalidOperationException("INVALID_CHILD_HASH");
        var ancestors=new Stack<string>();
        for(string parent=Path.GetDirectoryName(Path.GetFullPath(path));parent!=null;parent=Path.GetDirectoryName(parent)) ancestors.Push(parent);
        while(ancestors.Count>0) {
            string directory=ancestors.Pop();if(directoryPins.ContainsKey(directory)) continue;
            IntPtr handle=CreateFileW(directory,0x80,3,IntPtr.Zero,3,0x02200000,IntPtr.Zero);
            if(handle==new IntPtr(-1)) throw new InvalidOperationException("CHILD_DIRECTORY_PIN_FAILED");
            var pin=new Microsoft.Win32.SafeHandles.SafeFileHandle(handle,true);FileFacts observed;
            if(!GetFileInformationByHandle(handle,out observed) || (observed.attributes&0x400)!=0 || (observed.attributes&0x10)==0) {
                pin.Dispose();throw new InvalidOperationException("CHILD_DIRECTORY_IDENTITY_REJECTED");
            }
            directoryPins.Add(directory,pin);
        }
        for(string cursor=Path.GetFullPath(path);cursor!=null;cursor=Path.GetDirectoryName(cursor))
            if((File.GetAttributes(cursor)&FileAttributes.ReparsePoint)!=0) throw new InvalidOperationException("CHILD_REPARSE_PATH");
        IntPtr file=CreateFileW(path,0x80000000,1,IntPtr.Zero,3,0x00200000,IntPtr.Zero);
        if(file==new IntPtr(-1)) throw new InvalidOperationException("CHILD_FILE_PIN_FAILED");
        var owned=new Microsoft.Win32.SafeHandles.SafeFileHandle(file,true);
        FileFacts facts;
        if(!GetFileInformationByHandle(file,out facts) || facts.links!=1 || (facts.attributes&0x410)!=0) {
            owned.Dispose();
            throw new InvalidOperationException("CHILD_FILE_IDENTITY_REJECTED");
        }
        FileStream f;
        try { f=new FileStream(owned,FileAccess.Read); } catch { owned.Dispose();throw; }
        pins.Add(f);
        using(var hash=SHA256.Create()) if(BitConverter.ToString(hash.ComputeHash(f)).Replace("-","").ToLowerInvariant()!=expected) throw new InvalidOperationException("CHILD_HASH_MISMATCH");
    }
    public void PinRuntime(string manifestPath,string expected,string python) {
        Quoted(python);Quoted(manifestPath);
        string root=Path.GetFullPath(Path.GetDirectoryName(python));
        if(Path.GetFullPath(manifestPath)!=Path.Combine(root,"U1_RUNTIME_CONTENT.json") || new FileInfo(manifestPath).Length>2097152)
            throw new InvalidOperationException("RUNTIME_MANIFEST_PATH");
        Pin(manifestPath,expected);
        var serializer=new JavaScriptSerializer();serializer.MaxJsonLength=2097152;
        var m=serializer.Deserialize<Dictionary<string,object>>(File.ReadAllText(manifestPath,Encoding.UTF8));
        if(m==null || m.Count!=3 || !m.ContainsKey("schema") || (string)m["schema"]!="rokt.u1-runtime-content.v1" ||
           !m.ContainsKey("python") || (string)m["python"]!="python.exe" || !m.ContainsKey("files") ||
           !String.Equals(Path.GetFullPath(python),Path.Combine(root,"python.exe"),StringComparison.OrdinalIgnoreCase))
            throw new InvalidOperationException("RUNTIME_MANIFEST_SCHEMA");
        var files=m["files"] as Dictionary<string,object>;
        if(files==null || files.Count<1 || files.Count>8192 || !files.ContainsKey("python.exe"))
            throw new InvalidOperationException("RUNTIME_MANIFEST_FILES");
        var seen=new HashSet<string>(StringComparer.OrdinalIgnoreCase);long total=0;
        foreach(var row in files) {
            string relative=row.Key;
            if(!System.Text.RegularExpressions.Regex.IsMatch(relative,"^[A-Za-z0-9_./+-]+$") || relative.StartsWith("/") ||
               !seen.Add(relative) || relative.Equals("U1_RUNTIME_CONTENT.json",StringComparison.OrdinalIgnoreCase))
                throw new InvalidOperationException("RUNTIME_MANIFEST_ENTRY");
            foreach(string part in relative.Split('/'))
                if(part.Length==0 || part=="." || part==".." || part.EndsWith(".") ||
                   System.Text.RegularExpressions.Regex.IsMatch(part.Split('.')[0],"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])$",System.Text.RegularExpressions.RegexOptions.IgnoreCase))
                    throw new InvalidOperationException("RUNTIME_MANIFEST_ENTRY");
            string path=Path.Combine(root,relative.Replace('/',Path.DirectorySeparatorChar));
            long size=new FileInfo(path).Length;total+=size;
            if(size>268435456 || total>1073741824) throw new InvalidOperationException("RUNTIME_CONTENT_LIMIT");
            Pin(path,row.Value as string);
        }
        // Walk one directory at a time, rejecting reparse points before recursion.
        var directories=new Stack<string>();directories.Push(root);int count=0;
        while(directories.Count>0) foreach(string path in Directory.GetFileSystemEntries(directories.Pop())) {
            var attributes=File.GetAttributes(path);
            if((attributes&FileAttributes.ReparsePoint)!=0) throw new InvalidOperationException("RUNTIME_REPARSE_PATH");
            if((attributes&FileAttributes.Directory)!=0) {directories.Push(path);continue;}
            string relative=path.Substring(root.Length+1).Replace(Path.DirectorySeparatorChar,'/');
            if(!relative.Equals("U1_RUNTIME_CONTENT.json",StringComparison.OrdinalIgnoreCase)) {
                if(!seen.Contains(relative)) throw new InvalidOperationException("RUNTIME_UNMANAGED_FILE");count++;
            }
        }
        if(count!=files.Count) throw new InvalidOperationException("RUNTIME_CONTENT_CHANGED");
    }
    public static ServiceChild FromConfig(string path) {
        if(new FileInfo(path).Length>8192) throw new InvalidOperationException("CHILD_CONFIG_LIMIT");
        var c=new JavaScriptSerializer().Deserialize<Dictionary<string,string>>(File.ReadAllText(path,Encoding.UTF8));
        bool complete=c!=null && c.ContainsKey("schema") && c["schema"]=="rokt.u1-supervisor.v2";
        if(c==null || c.Count!=(complete?10:8) || (!complete && c["schema"]!="rokt.u1-supervisor.v1") || c["inventory_id"]!="1784775229336") throw new InvalidOperationException("CHILD_CONFIG_REJECTED");
        var child=new ServiceChild();ProcessInfo pi=new ProcessInfo();
        try {
            if(complete) child.PinRuntime(c["python_runtime_manifest"],c["python_runtime_manifest_sha256"],c["python"]);
            child.Pin(c["python"],c["python_sha256"]);child.Pin(c["bootstrap"],c["bootstrap_sha256"]);child.Pin(c["runtime_config"],c["runtime_config_sha256"]);
            child.job=CreateJobObject(IntPtr.Zero,null);if(child.job==IntPtr.Zero) throw new InvalidOperationException("JOB_CREATE_FAILED");
            Extended limits=new Extended();limits.basic.flags=0x2000;
            if(!SetInformationJobObject(child.job,9,ref limits,Marshal.SizeOf(limits))) throw new InvalidOperationException("JOB_LIMIT_FAILED");
            Startup si=new Startup();si.cb=Marshal.SizeOf(si);
            string command=Quoted(c["python"])+" -I -B "+Quoted(c["bootstrap"])+" "+Quoted(c["runtime_config"]);
            if(!CreateProcess(c["python"],new StringBuilder(command),IntPtr.Zero,IntPtr.Zero,false,0x08000004,IntPtr.Zero,Path.GetDirectoryName(c["bootstrap"]),ref si,out pi)) throw new InvalidOperationException("CHILD_CREATE_FAILED");
            child.process=pi.process;
            if(!AssignProcessToJobObject(child.job,pi.process)) throw new InvalidOperationException("JOB_ASSIGN_FAILED");
            if(ResumeThread(pi.thread)==0xFFFFFFFF) throw new InvalidOperationException("CHILD_RESUME_FAILED");
            return child;
        } catch { if(pi.process!=IntPtr.Zero) TerminateProcess(pi.process,125);child.Dispose();throw; }
        finally { if(pi.thread!=IntPtr.Zero) CloseHandle(pi.thread); }
    }
    public void Dispose() {
        bool verified=true;
        if(job!=IntPtr.Zero) {
            verified=TerminateJobObject(job,125);
            var deadline=Stopwatch.StartNew();Accounting info;
            while(verified) {
                verified=QueryInformationJobObject(job,1,out info,Marshal.SizeOf(typeof(Accounting)),IntPtr.Zero);
                if(!verified || info.active==0) break;
                if(deadline.ElapsedMilliseconds>=10000) { verified=false;break; }
                Thread.Sleep(10);
            }
            CloseHandle(job);job=IntPtr.Zero;
        }
        if(process!=IntPtr.Zero) { verified=WaitForSingleObject(process,10000)==0 && verified;CloseHandle(process);process=IntPtr.Zero; }
        foreach(var f in pins) f.Dispose();pins.Clear();
        foreach(var directory in directoryPins.Values) directory.Dispose();directoryPins.Clear();
        if(!verified) throw new InvalidOperationException("CHILD_CLEANUP_UNVERIFIED");
    }
}
