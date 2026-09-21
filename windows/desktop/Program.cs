using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;
using System.Text.Json;
using Microsoft.Web.WebView2.Core;
using Microsoft.Web.WebView2.WinForms;

internal static class Program
{
    [STAThread]
    static void Main()
    {
        var customData=Environment.GetEnvironmentVariable("QWEN_STUDIO_DATA");
        var instance=customData==null?"":Convert.ToHexString(System.Security.Cryptography.SHA256.HashData(Encoding.UTF8.GetBytes(Path.GetFullPath(customData).ToUpperInvariant())))[..16];
        using var single = new Mutex(true, "Local\\QwenStudioWindowsDesktop"+instance, out bool first);
        if (!first) {
            foreach (var p in Process.GetProcessesByName("Qwen Studio"))
                if (p.Id != Environment.ProcessId && p.MainWindowHandle != IntPtr.Zero) { ShowWindow(p.MainWindowHandle, 9); SetForegroundWindow(p.MainWindowHandle); }
            return;
        }
        ApplicationConfiguration.Initialize();
        Application.Run(new StudioWindow());
    }
    [DllImport("user32.dll")] static extern bool SetForegroundWindow(IntPtr h);
    [DllImport("user32.dll")] static extern bool ShowWindow(IntPtr h, int n);
}

internal sealed class StudioWindow : Form
{
    readonly WebView2 web = new() { Dock = DockStyle.Fill, DefaultBackgroundColor = Color.White };
    readonly StudioTitleBar titlebar;
    readonly string root;
    readonly string data;
    readonly string token = Guid.NewGuid().ToString("N") + Guid.NewGuid().ToString("N");
    Process? backend;
    string origin = "";
    bool shuttingDown;
    readonly object logLock = new();

    public StudioWindow()
    {
        root = FindRoot();
        data = Environment.GetEnvironmentVariable("QWEN_STUDIO_DATA") ?? LocalSetting("data") ?? Path.Combine(Environment.GetFolderPath(Environment.SpecialFolder.LocalApplicationData),"QwenStudio");
        Directory.CreateDirectory(data);
        AutoScaleDimensions = new SizeF(96, 96);
        AutoScaleMode = AutoScaleMode.Dpi;
        Text = "Qwen Studio";
        Icon = Icon.ExtractAssociatedIcon(Environment.ProcessPath!);
        ClientSize = new Size(1220, 820);
        MinimumSize = new Size(860, 650);
        BackColor = Color.White;
        StartPosition = FormStartPosition.CenterScreen;
        FormBorderStyle = FormBorderStyle.Sizable;
        Padding = new Padding(4,0,4,4);
        DoubleBuffered = true;
        KeyPreview = true;
        titlebar = new StudioTitleBar(this, async () => await Script("window.studioAction?.('sidebar')"));
        Controls.Add(web); Controls.Add(titlebar);
        Resize += (_,_) => {
            var edge=(int)Math.Ceiling(4*DeviceDpi/96f);
            Padding=WindowState==FormWindowState.Maximized?Padding.Empty:new Padding(edge,0,edge,edge);
            titlebar.RefreshWindowState();
        };
        Activated += (_,_) => titlebar.SetActive(true);
        Deactivate += (_,_) => titlebar.SetActive(false);
        Shown += async (_,_) => await Initialize();
        FormClosing += OnStudioClosing;
    }

    string? LocalSetting(string key)
    {
        var file=Path.Combine(root,"settings.local.json");
        if(!File.Exists(file))return null;
        using var settings=JsonDocument.Parse(File.ReadAllText(file,Encoding.UTF8));
        return settings.RootElement.TryGetProperty(key,out var value)&&value.ValueKind==JsonValueKind.String ? value.GetString() : null;
    }

    static string FindRoot()
    {
        var directory = new DirectoryInfo(AppContext.BaseDirectory);
        while (directory != null) {
            if (File.Exists(Path.Combine(directory.FullName,"backend","server.py"))) return directory.FullName;
            directory=directory.Parent;
        }
        throw new DirectoryNotFoundException("找不到 Qwen Studio/backend/server.py，请保留应用目录结构。");
    }

    internal void ToggleMaximize() => WindowState=WindowState==FormWindowState.Maximized?FormWindowState.Normal:FormWindowState.Maximized;
    async Task Script(string script) { if(web.CoreWebView2!=null) await web.ExecuteScriptAsync(script); }

    void Log(string line)
    {
        lock(logLock) File.AppendAllText(Path.Combine(data,"desktop.log"),DateTime.Now.ToString("s")+" "+line+Environment.NewLine,Encoding.UTF8);
    }

    async Task Initialize()
    {
        try {
            var environment=await CoreWebView2Environment.CreateAsync(null,Path.Combine(data,"WebView2"));
            await web.EnsureCoreWebView2Async(environment);
            web.CoreWebView2.Settings.AreDefaultContextMenusEnabled=false;
            web.CoreWebView2.Settings.IsStatusBarEnabled=false;
            web.CoreWebView2.Settings.AreBrowserAcceleratorKeysEnabled=false;
            web.CoreWebView2.Settings.IsZoomControlEnabled=false;
            web.CoreWebView2.NavigateToString("<html><body style='margin:0;background:white;color:#626262;font:14px Segoe UI;display:grid;place-items:center;height:100vh'>正在打开 Qwen Studio…</body></html>");
            if(!File.Exists(Path.Combine(root,".venv","Scripts","python.exe")))
                throw new FileNotFoundException("请先运行 setup.cmd 安装 Python 依赖，然后重新打开应用。 Run setup.cmd before opening Qwen Studio.");
            var start = new ProcessStartInfo(Path.Combine(root,".venv","Scripts","python.exe")) {
                WorkingDirectory=root,UseShellExecute=false,CreateNoWindow=true,RedirectStandardOutput=true,RedirectStandardError=true,StandardOutputEncoding=Encoding.UTF8,StandardErrorEncoding=Encoding.UTF8
            };
            start.ArgumentList.Add("-X");start.ArgumentList.Add("utf8");start.ArgumentList.Add(Path.Combine(root,"backend","server.py"));
            var model=Environment.GetEnvironmentVariable("QWEN_STUDIO_MODEL") ?? LocalSetting("model");
            if(!string.IsNullOrWhiteSpace(model))start.Environment["QWEN_STUDIO_MODEL"]=model;
            start.Environment["PYTHONUTF8"]="1";start.Environment["PYTHONUNBUFFERED"]="1";
            start.Environment["QWEN_STUDIO_DATA"]=data;start.Environment["QWEN_STUDIO_TOKEN"]=token;
            start.Environment["NO_PROXY"]="127.0.0.1,localhost";
            backend=new Process {StartInfo=start,EnableRaisingEvents=true};
            backend.ErrorDataReceived+=(_,e)=>{if(e.Data!=null)Log(e.Data);};
            backend.Start();backend.BeginErrorReadLine();
            var line=await backend.StandardOutput.ReadLineAsync().WaitAsync(TimeSpan.FromSeconds(30));
            if(line==null)throw new Exception("本地服务未能启动。请查看 desktop.log。");
            using(var info=JsonDocument.Parse(line)){origin="http://127.0.0.1:"+info.RootElement.GetProperty("port").GetInt32();}
            _ = Task.Run(async () => { while(await backend.StandardOutput.ReadLineAsync() is string output) Log(output); });
            File.WriteAllText(Path.Combine(data,"desktop-runtime.json"),JsonSerializer.Serialize(new {url=origin,pid=backend.Id,desktop_pid=Environment.ProcessId}),Encoding.UTF8);
            // Match the Swift WKScriptMessageHandler bridge, so the original web UI stays unchanged.
            await web.CoreWebView2.AddScriptToExecuteOnDocumentCreatedAsync("if(location.origin === "+JsonSerializer.Serialize(origin)+") {window.webkit={messageHandlers:{studio:{postMessage:p=>window.chrome.webview.postMessage(p)}}};}");
            web.CoreWebView2.WebMessageReceived+=Bridge;
            web.CoreWebView2.NavigationStarting+=(_,e)=>{if(e.Uri!="about:blank"&&!IsLocal(e.Uri)){e.Cancel=true;if(Uri.TryCreate(e.Uri,UriKind.Absolute,out var u)&&u.Scheme=="https")Process.Start(new ProcessStartInfo(e.Uri){UseShellExecute=true});}};
            web.CoreWebView2.NewWindowRequested+=(_,e)=>{e.Handled=true;if(Uri.TryCreate(e.Uri,UriKind.Absolute,out var u)&&u.Scheme=="https")Process.Start(new ProcessStartInfo(e.Uri){UseShellExecute=true});};
            web.CoreWebView2.NavigationCompleted+=async(_,e)=>{if(e.IsSuccess&&IsLocal(web.Source?.ToString()??"")){
                await Script("document.querySelectorAll('kbd').forEach(e=>e.textContent=e.textContent.replace('⌘','Ctrl'));document.querySelector('.composer-foot span').textContent='Ctrl ↵';document.querySelector('#reveal-data').lastChild.textContent='在文件资源管理器中打开';");
            }};
            web.Source=new Uri(origin);
        } catch(Exception error) {Log(error.ToString());MessageBox.Show(this,error.Message,"Qwen Studio 启动失败",MessageBoxButtons.OK,MessageBoxIcon.Error);Close();}
    }

    bool IsLocal(string value) => Uri.TryCreate(value,UriKind.Absolute,out var u)&&u.GetLeftPart(UriPartial.Authority)==origin;
    void Bridge(object? sender,CoreWebView2WebMessageReceivedEventArgs e)
    {
        if(!IsLocal(e.Source))return;
        try {
            using var payload=JsonDocument.Parse(e.WebMessageAsJson);var p=payload.RootElement;var action=p.GetProperty("action").GetString();
            if(action=="revealData")Process.Start(new ProcessStartInfo(data){UseShellExecute=true});
            if(action=="sidebarState")titlebar.SetSidebarCollapsed(p.GetProperty("collapsed").GetBoolean());
            if(action=="saveImage"){
                var name=p.GetProperty("name").GetString()??"";
                if(name!=Path.GetFileName(name)||!name.EndsWith(".png",StringComparison.OrdinalIgnoreCase))return;
                var source=Path.Combine(data,"images",name);if(!File.Exists(source))return;
                using var dialog=new SaveFileDialog {Filter="PNG 图片|*.png",FileName="Qwen-"+name[..Math.Min(8,name.Length)]+".png",OverwritePrompt=true};
                if(dialog.ShowDialog(this)==DialogResult.OK)File.Copy(source,dialog.FileName,true);
            }
        } catch(Exception error){Log(error.ToString());MessageBox.Show(this,error.Message,"Qwen Studio");}
    }

    async void OnStudioClosing(object? sender,FormClosingEventArgs e)
    {
        if(shuttingDown)return;
        e.Cancel=true;shuttingDown=true;
        Enabled=false;
        try {
            if(backend is {HasExited:false}){
                using var client=new HttpClient(new HttpClientHandler{UseProxy=false}){Timeout=TimeSpan.FromSeconds(3)};
                client.DefaultRequestHeaders.Add("X-Studio-Token",token);
                try{await client.PostAsync(origin+"/api/shutdown",new StringContent("{}",Encoding.UTF8,"application/json"));await backend.WaitForExitAsync().WaitAsync(TimeSpan.FromSeconds(12));}catch{if(!backend.HasExited)backend.Kill(true);}
            }
        } finally {
            web.Dispose();BeginInvoke(Close);
        }
    }

    protected override bool ProcessCmdKey(ref Message msg,Keys keyData)
    {
        if(keyData==(Keys.Control|Keys.N)){_=Script("window.studioAction?.('new')");return true;}
        if(keyData==(Keys.Control|Keys.Oemcomma)){_=Script("window.studioAction?.('settings')");return true;}
        return base.ProcessCmdKey(ref msg,keyData);
    }
    protected override void WndProc(ref Message m)
    {
        // Retain the real resizable Windows frame, but paint its titlebar ourselves.
        // This preserves DWM shadows, rounded corners and taskbar-aware maximization.
        if(m.Msg==0x83 && m.WParam!=IntPtr.Zero){m.Result=IntPtr.Zero;return;}
        if(m.Msg==0x24){
            base.WndProc(ref m);
            var monitor=MonitorFromWindow(Handle,2);
            var info=new MonitorInfo{size=Marshal.SizeOf<MonitorInfo>()};
            if(GetMonitorInfo(monitor,ref info)){
                var size=Marshal.PtrToStructure<MinMaxInfo>(m.LParam);
                size.maxPosition=new Point(info.work.Left-info.monitor.Left,info.work.Top-info.monitor.Top);
                size.maxSize=new Point(info.work.Right-info.work.Left,info.work.Bottom-info.work.Top);
                Marshal.StructureToPtr(size,m.LParam,false);
            }
            return;
        }
        const int WM_NCHITTEST=0x84;
        if(m.Msg==WM_NCHITTEST&&WindowState==FormWindowState.Normal){
            var point=PointToClient(new Point((short)((long)m.LParam&0xffff),(short)(((long)m.LParam>>16)&0xffff)));
            int edge=(int)Math.Ceiling(6*DeviceDpi/96f);bool left=point.X<edge,right=point.X>=ClientSize.Width-edge,top=point.Y<edge,bottom=point.Y>=ClientSize.Height-edge;
            if(top||bottom||left||right){m.Result=(IntPtr)(top?(left?13:right?14:12):bottom?(left?16:right?17:15):left?10:11);return;}
        }
        if(m.Msg==WM_NCHITTEST){
            var point=PointToClient(new Point((short)((long)m.LParam&0xffff),(short)(((long)m.LParam>>16)&0xffff)));
            if(point.Y>=0 && point.Y<(int)Math.Round(48*DeviceDpi/96f)){m.Result=(IntPtr)2;return;}
        }
        base.WndProc(ref m);
    }
    protected override void OnHandleCreated(EventArgs e)
    {
        base.OnHandleCreated(e);
        if(OperatingSystem.IsWindowsVersionAtLeast(10,0,22000)){
            int rounded=2,border=0x00E7E7E7;
            DwmSetWindowAttribute(Handle,33,ref rounded,4);
            DwmSetWindowAttribute(Handle,34,ref border,4);
        }
    }
    [StructLayout(LayoutKind.Sequential)] struct NativeRect{public int Left,Top,Right,Bottom;}
    [StructLayout(LayoutKind.Sequential)] struct MonitorInfo{public int size;public NativeRect monitor,work;public uint flags;}
    [StructLayout(LayoutKind.Sequential)] struct MinMaxInfo{public Point reserved,maxSize,maxPosition,minTrackSize,maxTrackSize;}
    [DllImport("user32.dll")] static extern IntPtr MonitorFromWindow(IntPtr h,uint flags);
    [DllImport("user32.dll",CharSet=CharSet.Auto)] static extern bool GetMonitorInfo(IntPtr h,ref MonitorInfo info);
    [DllImport("dwmapi.dll")] static extern int DwmSetWindowAttribute(IntPtr h,int attribute,ref int value,int size);
}
