# Security and privacy

The studio runs a local HTTP service bound to `127.0.0.1`. API calls need a random token that is stored in
`data/.token` (readable only by your user) and injected into the page the service serves. It is a
single-user tool, not a server for networks: do not expose its port through a proxy or port forwarding.

Chats, reference images, results and logs stay in the local `data` folder. There are no accounts and no
telemetry (`HF_HUB_DISABLE_TELEMETRY` is set). Network access: `setup.sh` contacts PyPI and GitHub (the
pinned diffusers archive); model downloads contact Hugging Face at pinned revisions and every file is
checked against its SHA-256. Workers run offline and never execute code from model repositories.

Do not attach tokens, databases, private images or unreviewed logs to public issues. PNG files contain the
prompt and settings in their metadata.

Please report security problems privately through the repository's Security tab.
