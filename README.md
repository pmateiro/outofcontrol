# OutOfControl

Agente de uso geral em Python — skills, tools, OpenAI agora, Ollama depois.

Estilo próximo ao agente do Cursor: linguagem natural → tools → resultado, com skills carregadas sob demanda.

## O que tem no MVP

- **CLI** interativa (`chat`) e **API HTTP** (`serve`)
- **Providers**: `openai` (padrão) e `ollama` (API compatível)
- **Skills** em `skills/*/SKILL.md` (`list_skills` / `load_skill`)
- **Tools de código**: `read_file`, `write_file`, `edit_file`, `delete_file`, `grep`, `glob_files`, `list_dir`
- **Shell** com confirmação em comandos sensíveis; **`confirm_action`** também para deletes
- **Web** search/fetch, **calendário** local, **memória** persistente (`memory_*`)
- Skills de exemplo: `repo-edit`, `git-workflow`, `web-research`, `daily-planning`, `memory`
- Escopo **geral** (não só o repo): web, calendário, shell, memória, etc.

## Setup

```bash
cd outofcontrol
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp config.example.yaml config.yaml
export OPENAI_API_KEY=sk-...
```

## CLI

```bash
# one-shot
outofcontrol chat "Liste minhas skills e resuma o que você pode fazer"

# REPL
outofcontrol chat
```

No REPL: `/reset` limpa histórico, `/exit` sai.  
Ações sensíveis (`rm`/sudo/`git push`, `delete_file`, etc.) pedem confirmação no terminal.

## API HTTP

```bash
outofcontrol serve --host 127.0.0.1 --port 8000
```

```bash
curl -s http://127.0.0.1:8000/health

curl -s http://127.0.0.1:8000/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message":"O que tem na minha agenda?","session_id":"phone"}'
```

Se um shell sensível precisar de confirmação, a resposta traz `pending_confirmations` com `confirmation_token`. Aprove assim:

```bash
curl -s http://127.0.0.1:8000/v1/confirm \
  -H 'content-type: application/json' \
  -d '{"confirmation_token":"...","approve":true,"session_id":"phone"}'
```

Docs interativas: `http://127.0.0.1:8000/docs`

> Acesso pelo celular exige host público (deploy) ou túnel; este processo local sozinho não fica na internet.

## Trocar para Ollama

Em `config.yaml`:

```yaml
provider: ollama
model: llama3.1
ollama_base_url: http://127.0.0.1:11434/v1
```

## Skills

Coloque skills em `skills/<nome>/SKILL.md`:

```markdown
---
name: minha-skill
description: Quando usar esta skill.
---

Instruções detalhadas para o agente...
```

## Testes

```bash
pytest -q
```

## Layout

```
src/outofcontrol/     # agente, providers, tools, CLI, API
skills/               # skills estilo Cursor
config.example.yaml
tests/
```
