import Cocoa
import WebKit

final class AppDelegate: NSObject, NSApplicationDelegate, WKNavigationDelegate, WKUIDelegate, WKScriptMessageHandler, NSToolbarDelegate {
    var window: NSWindow!
    var web: WKWebView!
    var backend: Process?
    var backendPort: Int = 0
    var sidebarButton: NSButton!
    let dataURL = ProcessInfo.processInfo.environment["QWEN_STUDIO_DATA"].map { URL(fileURLWithPath: $0) } ?? FileManager.default.homeDirectoryForCurrentUser.appendingPathComponent("Library/Application Support/Qwen Studio")
    func applicationDidFinishLaunching(_ notification: Notification) {
        NSApp.setActivationPolicy(.regular)
        if let iconURL = Bundle.main.url(forResource: "AppIcon", withExtension: "icns"),
           let icon = NSImage(contentsOf: iconURL) {
            NSApp.applicationIconImage = icon
        }
        buildMenu()
        let config = WKWebViewConfiguration()
        config.userContentController.add(self, name: "studio")
        web = WKWebView(frame: .zero, configuration: config)
        web.navigationDelegate = self; web.uiDelegate = self
        web.focusRingType = .none
        web.setValue(false, forKey: "drawsBackground")
        window = NSWindow(contentRect: NSRect(x: 0, y: 0, width: 1220, height: 820), styleMask: [.titled, .closable, .miniaturizable, .resizable], backing: .buffered, defer: false)
        window.minSize = NSSize(width: 860, height: 650)
        window.title = "Qwen Studio"
        window.titleVisibility = .hidden
        window.titlebarAppearsTransparent = true
        window.backgroundColor = .white
        let toolbar = NSToolbar(identifier: "StudioToolbar")
        toolbar.delegate = self
        toolbar.displayMode = .iconOnly
        toolbar.allowsUserCustomization = false
        window.titlebarSeparatorStyle = .none
        window.toolbar = toolbar
        window.toolbarStyle = .unifiedCompact
        window.contentView = web
        window.center(); window.makeKeyAndOrderFront(nil); NSApp.activate(ignoringOtherApps: true)
        web.loadHTMLString("<html><body style='background:#f7f7f5;color:#555;font:15px -apple-system;display:grid;place-items:center;height:90vh'>正在打开 Qwen Studio…</body></html>", baseURL: nil)
        startBackend()
    }
    func buildMenu() {
        let menu = NSMenu(); let appItem = NSMenuItem(); menu.addItem(appItem)
        let app = NSMenu(); appItem.submenu = app
        app.addItem(withTitle: "关于 Qwen Studio", action: #selector(about), keyEquivalent: "")
        app.addItem(withTitle: "设置…", action: #selector(settings), keyEquivalent: ",")
        app.addItem(.separator()); app.addItem(withTitle: "退出 Qwen Studio", action: #selector(NSApplication.terminate(_:)), keyEquivalent: "q")
        let fileItem=NSMenuItem();menu.addItem(fileItem);let file=NSMenu(title:"文件");fileItem.submenu=file
        file.addItem(withTitle:"新会话",action:#selector(newSession),keyEquivalent:"n")
        file.addItem(withTitle:"关闭窗口",action:#selector(NSWindow.performClose(_:)),keyEquivalent:"w")
        let editItem=NSMenuItem();menu.addItem(editItem);let edit=NSMenu(title:"编辑");editItem.submenu=edit
        for (title,action,key) in [("撤销","undo:","z"),("剪切","cut:","x"),("复制","copy:","c"),("粘贴","paste:","v"),("全选","selectAll:","a")] { edit.addItem(withTitle:title,action:Selector(action),keyEquivalent:key) }
        NSApp.mainMenu=menu
    }
    @objc func about() { let a=NSAlert();a.messageText="Qwen Studio";a.informativeText="本地图像与对话工作室\nQwen-Image-2.1 / Diffusers / Ollama\n版本 2.1.0";a.runModal() }
    @objc func settings(){web.evaluateJavaScript("window.studioAction?.('settings')")}
    @objc func newSession(){web.evaluateJavaScript("window.studioAction?.('new')")}
    @objc func toggleSidebar(){web.evaluateJavaScript("window.studioAction?.('sidebar')")}
    func toolbarAllowedItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] { [NSToolbarItem.Identifier("StudioSidebar"), .flexibleSpace] }
    func toolbarDefaultItemIdentifiers(_ toolbar: NSToolbar) -> [NSToolbarItem.Identifier] { [NSToolbarItem.Identifier("StudioSidebar"), .flexibleSpace] }
    func toolbar(_ toolbar: NSToolbar, itemForItemIdentifier identifier: NSToolbarItem.Identifier, willBeInsertedIntoToolbar flag: Bool) -> NSToolbarItem? {
        guard identifier.rawValue == "StudioSidebar" else { return nil }
        let item = NSToolbarItem(itemIdentifier: identifier)
        sidebarButton = NSButton(image: NSImage(systemSymbolName: "sidebar.left", accessibilityDescription: "切换侧栏")!, target: self, action: #selector(toggleSidebar))
        sidebarButton.bezelStyle = .texturedRounded
        sidebarButton.isBordered = false
        sidebarButton.focusRingType = .none
        sidebarButton.toolTip = "收起侧栏"
        sidebarButton.setAccessibilityLabel("收起侧栏")
        item.view = sidebarButton
        item.label = "侧栏"
        return item
    }
    func startBackend(){
        guard let resources=Bundle.main.resourceURL else { return }
        let root=resources.path
        let python=ProcessInfo.processInfo.environment["QWEN_STUDIO_PYTHON"] ?? dataURL.appendingPathComponent("runtime/bin/python3").path
        guard FileManager.default.isExecutableFile(atPath:python) else {
            fail("请先运行下载包中的 setup.command 安装 Python 依赖。\nRun setup.command from the download package before opening Qwen Studio.")
            return
        }
        let process=Process();process.executableURL=URL(fileURLWithPath:python)
        process.arguments=[root+"/backend/server.py"]
        process.currentDirectoryURL=URL(fileURLWithPath:root)
        var env=ProcessInfo.processInfo.environment;env["PYTHONUNBUFFERED"]="1";process.environment=env
        let output=Pipe();process.standardOutput=output
        try? FileManager.default.createDirectory(at:dataURL,withIntermediateDirectories:true)
        let log=dataURL.appendingPathComponent("app.log");FileManager.default.createFile(atPath:log.path,contents:nil)
        process.standardError=try? FileHandle(forWritingTo:log)
        backend=process
        do { try process.run() } catch { fail("无法启动 Python 环境：\(error.localizedDescription)");return }
        DispatchQueue.global().async { [weak self] in
            let data=output.fileHandleForReading.availableData
            guard let line=String(data:data,encoding:.utf8)?.split(separator:"\n").first,
                  let jsonData=String(line).data(using:.utf8),
                  let info=(try? JSONSerialization.jsonObject(with:jsonData)) as? [String:Any],
                  let port=info["port"] as? Int else { DispatchQueue.main.async{self?.fail("本地服务没有启动，请查看应用数据目录中的 app.log。")} ;return }
            DispatchQueue.main.async{self?.backendPort=port;self?.web.load(URLRequest(url:URL(string:"http://127.0.0.1:\(port)/")!))}
        }
    }
    func fail(_ text:String){let a=NSAlert();a.messageText="Qwen Studio 启动失败";a.informativeText=text;a.runModal()}
    func applicationShouldTerminateAfterLastWindowClosed(_ sender:NSApplication)->Bool {true}
    func applicationWillTerminate(_ notification:Notification){if backend?.isRunning == true { backend?.terminate() }}
    func webView(_ webView:WKWebView,decidePolicyFor action:WKNavigationAction,decisionHandler:@escaping(WKNavigationActionPolicy)->Void){
        guard let u=action.request.url else{decisionHandler(.cancel);return}
        if (u.host=="127.0.0.1" && u.port==backendPort) || u.scheme=="about" {decisionHandler(.allow)} else {if u.scheme=="https"{NSWorkspace.shared.open(u)};decisionHandler(.cancel)}
    }
    func webView(_ webView:WKWebView,runOpenPanelWith parameters:WKOpenPanelParameters,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping([URL]?)->Void){
        let panel=NSOpenPanel();panel.allowsMultipleSelection=true;panel.canChooseDirectories=false;panel.allowedContentTypes=[.png,.jpeg,.webP];panel.beginSheetModal(for:window){result in completionHandler(result == .OK ? panel.urls:nil)}
    }
    func webView(_ webView:WKWebView,runJavaScriptConfirmPanelWithMessage message:String,initiatedByFrame frame:WKFrameInfo,completionHandler:@escaping(Bool)->Void){let a=NSAlert();a.messageText=message;a.addButton(withTitle:"确定");a.addButton(withTitle:"取消");a.beginSheetModal(for:window){r in completionHandler(r == .alertFirstButtonReturn)}}
    func userContentController(_ controller:WKUserContentController,didReceive message:WKScriptMessage){
        guard message.frameInfo.isMainFrame,message.frameInfo.request.url?.host=="127.0.0.1",message.frameInfo.request.url?.port==backendPort,let p=message.body as? [String:Any],let action=p["action"] as? String else{return}
        if action=="revealData"{NSWorkspace.shared.open(dataURL)}
        if action=="sidebarState",let collapsed=p["collapsed"] as? Bool { sidebarButton.toolTip=collapsed ? "展开侧栏" : "收起侧栏";sidebarButton.setAccessibilityLabel(sidebarButton.toolTip) }
        if action=="saveImage",let name=p["name"] as? String,name==URL(fileURLWithPath:name).lastPathComponent {
            let source=dataURL.appendingPathComponent("images").appendingPathComponent(name)
            guard FileManager.default.fileExists(atPath:source.path) else{return}
            let panel=NSSavePanel();panel.allowedContentTypes=[.png];panel.nameFieldStringValue="Qwen-\(name.prefix(8)).png"
            panel.beginSheetModal(for:window){response in if response == .OK,let dest=panel.url {do { let data=try Data(contentsOf:source);try data.write(to:dest,options:.atomic) }catch{ self.fail(error.localizedDescription) }}}
        }
    }
}
let app=NSApplication.shared
let delegate=AppDelegate();app.delegate=delegate;app.run()
