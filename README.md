# LLM Prompt Injection Defense

This is a small research project I built to study how to defend a chatbot that runs shell commands from prompt injection attacks. The idea came from the OWASP LLM Top 10 list. I wanted to see what actually works when you put real defenses in front of an LLM agent that has the power to run code on your machine.

The whole thing runs locally with Ollama, so no API keys needed.

## What it does

There are two agents talking to each other. The first one is the Policeman. Its job is to look at everything the user types, decide if it is safe, and only then pass it along. The second one is the Chatbot. It can run two commands and nothing else, `ls` and `date`. Even if someone tricks the Policeman, the Chatbot will refuse anything outside that tiny whitelist.

The Policeman does a few things in order:

1. It checks the rate of requests so nobody can hammer it
2. It keeps track of the conversation so it can spot someone slowly building up an attack
3. It runs the input through about 29 regex rules looking for the obvious stuff like command chaining, path traversal, encoded payloads, and known jailbreak phrases
4. It asks a small local LLM (llama3.2 or qwen3.5 by default) for a second opinion on anything subtle
5. After the command runs, it scrubs the output for things like passwords, private keys, and internal IPs before showing it to the user

If Ollama is not running the system falls back to just the regex rules and keeps going. It does not crash.

## Running it

You need Node 18 or newer, Ollama installed and running, and Docker if you want the RAG memory part.

```bash
ollama serve
ollama pull llama3.2
npm install
npm run chromadb:start   # optional, only for RAG
npm start
```

That drops you into a REPL. Type a message. The prompt shows which defense layers are armed, something like `[R+S+L+M+G]>`. You can toggle them live with slash commands:

```
/status              show what is on
/off semantic        turn off the LLM check
/preset c1           rules only
/preset c5           full pipeline
/model qwen3.5:2b    switch the LLM
/reset               put it back to full pipeline
```

The toggles exist because I wanted to run an ablation study and see how much each layer actually helps.

## Running the experiments

There is an evaluation dataset I called CEDA 215 (https://huggingface.co/datasets/aalayed/CEDA-215). It has 215 entries split between benign requests and attack attempts. There is also a faster 56 entry version for quick checks.

```bash
npm run dataset:build         # build the full 215 set
npm run dataset:build:fast    # quick 56 set

npm run eval:ablation         # compare the 5 configs
npm run eval:models           # compare llama sizes
npm run eval:models:qwen      # compare qwen sizes
npm run eval:report           # turn raw json into a readable report
```

Or just run everything with `./run.sh eval:qwen` if you want the full qwen pipeline.

## Project layout

```
src/
  agents/         the Policeman and Chatbot
  validators/     regex rules, semantic check, output scrubber
  middleware/     rate limiter
  memory/         session tracking and long term memory
data/
  evaluation dataset and result jsons
scripts/
  dataset builder and evaluation runners
docs/
  methodology, results, architecture diagrams
findings/
  python script to generate the results figures
```

## A note on safety

This is research code. The chatbot only runs `ls` and `date` and uses `execFile` so the shell does not interpret special characters. Do not extend the whitelist without thinking carefully about what that opens up. The whole point of the project is that giving an LLM real command execution is dangerous, and the defenses around it have to be taken seriously.

## License

GPL 3.0 or later. See the LICENSE file.

If you find a bug or want to suggest something open an issue. If you use this for your own research I would love to hear about it.
