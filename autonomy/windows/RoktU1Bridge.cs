// Minimal SCM candidate: local unsigned heartbeat only. No listener or dispatcher.
using System;
using System.Collections.Generic;
using System.Diagnostics;
using System.IO;
using System.ServiceProcess;
using System.Text;
using System.Threading;
using System.Web.Script.Serialization;

public sealed class RoktU1Bridge : ServiceBase {
    const string Inventory = "1784775229336";
    const string StateRoot = @"C:\ProgramData\RoktU1Bridge";
    readonly object gate = new object();
    Timer timer;
    bool stopping;
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
        WriteHeartbeat();
        timer=new Timer(delegate { try { lock(gate) { if(!stopping) WriteHeartbeat(); } } catch { Environment.Exit(3); } },null,10000,10000);
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
        lock(gate) { stopping=true;if(timer!=null) { timer.Dispose();timer=null; } }
    }
    public static int Main(string[] args) {
        if(args.Length==1 && args[0]=="--validate-config") {
            char[] input=new char[4097];int count=0,n;
            while(count<input.Length && (n=Console.In.Read(input,count,input.Length-count))>0) count+=n;
            bool ok=count<=4096 && ValidateConfig(new string(input,0,count));Console.WriteLine(ok?"VALID_DISABLED_CONFIG":"REJECTED");return ok?0:2;
        }
        if(args.Length!=0) return 2;
        ServiceBase.Run(new RoktU1Bridge());return 0;
    }
}
