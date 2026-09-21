# Security and privacy / 安全与隐私

Qwen Studio runs a local HTTP service bound to `127.0.0.1`. API calls use a per-process token. Native window bridges accept messages from that local origin. This is a single-user desktop application, not a server intended for public networks. Do not expose its port through a proxy or port-forwarding rule.

会话、参考图、生成结果和日志保存在本机。应用没有账户或内置遥测。安装脚本访问 PyPI、PyTorch 和 GitHub；模型下载访问所选的 ModelScope 或 Hugging Face。聊天通过本机 Ollama。Ollama 本身及用户另行安装的模型和服务不受本应用控制。

Conversations, references, outputs and logs remain in the local data directory. The app has no account system or bundled telemetry. Setup contacts PyPI, PyTorch and GitHub; downloads contact the selected model source; chat connects to local Ollama. Independently installed services have their own behavior.

Do not attach tokens, full databases, private images or unreviewed logs to public issues. Windows PNG exports include generation settings such as the prompt. Older builds may also include local paths in metadata.

请勿公开令牌、完整会话数据库、私人图片或未经检查的日志。报告安全问题请使用本仓库 Security 页中的私密漏洞报告功能；普通界面问题可提交 Issue。请勿在公开 Issue 中直接附上可利用的敏感信息。

Use the repository's private vulnerability reporting option on the Security tab for security issues. This early release has not had an independent security audit. Fixes target the latest published version.
