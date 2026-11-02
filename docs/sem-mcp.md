# Inspect a self-hosted code repository with Sem MCP

Use [Sem](https://github.com/Ataraxy-Labs/sem) when an OpenAgent workflow needs
to locate functions or inspect code relationships in a checkout you operate.
This is a custom MCP connection, not a public hosted service.

## Start the server

Install Sem on the machine containing the Git checkout. On the **same host
network as the OpenAgent API process**, run:

```bash
export SEM_REPO=/absolute/path/to/git/repo
export SEM_CLOUD=0
export SEM_MCP_HTTP_TOKEN="$(python3 -c 'import secrets; print(secrets.token_hex(32))')"
sem mcp --http 127.0.0.1:8765
```

Keep that process running. The token must contain at least 32 characters.
In OpenAgent's MCP configuration, create a custom connection with:

- Transport: `streamable_http`
- URL: `http://127.0.0.1:8765/mcp`
- Header name: `Authorization`
- Header value: `Bearer ` followed by the generated token

Select the connection for the agent and discover its tools. Try asking it to
find a known function by name, then inspect its relationships. The HTTP server
exposes read-only discovery; it does not provide Weave editing.

## Deployment and data handling

`127.0.0.1` means the OpenAgent **backend's** network namespace, not the browser.
For Docker deployments, the server above is not automatically reachable from
the API container. Use a deliberate authenticated TLS proxy/tunnel reachable
from the backend, or run both processes in the same network namespace. Do not
publish an unauthenticated endpoint or paste the token into source control.

Code excerpts returned by Sem enter the configured agent/model context.
`SEM_CLOUD=0` disables Sem uploads, not OpenAgent's model requests. Choose only
repositories that the configured users and models may inspect. Disconnect the
MCP binding and stop the Sem process to remove access.
