# Use Ringfence with OpenRouter

[OpenRouter](https://openrouter.ai) gives one API key for hundreds of models. Ringfence does not care which model the agent is. It is an MCP server, so any agent that can call tools can run payroll through it, and the same controls apply to every model: no approve tool, no tool takes a bank detail, and a person signs.

This is the page to read if your agent runs on an OpenRouter model. Other MCP clients: [MCP.md](MCP.md).

## Two ways in

| | Use when | You need |
|---|---|---|
| **A client that supports OpenRouter and MCP** | You use an agent app and pick the model in its settings | An OpenRouter key in the app, and the Ringfence URL added as an HTTP MCP server |
| **The example script** | You want to see the whole loop in code, or build your own agent | `OPENROUTER_API_KEY`, and [examples/openrouter_agent.py](../examples/openrouter_agent.py) |

## A client app

1. In the app, choose OpenRouter as the provider and pick a model that supports tool calling.
2. Add an MCP server of type HTTP (Streamable HTTP) with this URL:

   ```
   https://ringfence-hs23-eu.indiasouthcentral.cloudapp.azure.com/mcp
   ```

3. Ask it: "Run this week's payroll from demo/payday. Show me what will be paid and anything suspicious." What you should see is in [MCP.md](MCP.md#try-it-in-two-minutes).

The setting is called something different in each app, and some take a JSON block like the one in [MCP.md](MCP.md#connect). Look for "remote MCP", "HTTP MCP" or "Streamable HTTP". We have not tested any specific app, so check its own MCP page if the option is not where you expect.

## The example script

[examples/openrouter_agent.py](../examples/openrouter_agent.py) is about 60 lines. It connects to Ringfence, converts the four MCP tools into OpenRouter's tool format, sends the payroll files to the model and runs whichever tool calls the model asks for.

```
uv run python examples/openrouter_agent.py --tools
```

Connects and lists the four tools. No key needed. This is how to check your connection.

```
OPENROUTER_API_KEY=<your key> uv run python examples/openrouter_agent.py demo/payday
```

Runs the loop. The model calls `run_payroll`, then prints the payments, anything quarantined and the `approve_at` link. Open the link to approve (on the public demo only the operator's passkey can, see [MCP.md](MCP.md#the-approval-page)), then call `release_payroll` from your agent.

| Setting | Default | Meaning |
|---|---|---|
| `OPENROUTER_API_KEY` | none | Your OpenRouter key. Keep it in your shell, not in the repo. |
| `OPENROUTER_MODEL` | `anthropic/claude-sonnet-4.5` | Any model id from OpenRouter that supports tool calling |
| `RINGFENCE_MCP_URL` | the public demo | Point it at your own instance: `https://<your-host>/mcp` |

## What the model changes, and what it does not

| Depends on the model | Does not |
|---|---|
| Whether it passes all the files verbatim, and how well it summarises the run | What gets paid. Code reads the files again, prices the run and checks every bank account. |
| Whether it follows the "show the approval link" instruction in `next` | That a person must approve. There is no tool that approves. |
| Whether it obeys a hostile document | The result. A model that obeys every instruction still cannot move money without an approval ([GAUNTLET.md](GAUNTLET.md): 28 attacks attempted, all 28 blocked by the gate). |

A weaker model can make the run less useful, for example by forgetting to pass a file, but it cannot make it less safe.

## What is tested

- The script's connection and tool listing against the live Ringfence endpoint.
- We have not run the chat loop against OpenRouter with a key, and we have not tried specific models or client apps. The OpenRouter side follows its [OpenAI-compatible chat completions API](https://openrouter.ai/docs), so a model that does not support tool calling will fail at the first request.
- Ringfence's own server-side steps, such as reading the files, use Claude (see [RUN_IT.md](RUN_IT.md#using-claude)), whichever model your agent is. Moving those to OpenRouter is not built.
