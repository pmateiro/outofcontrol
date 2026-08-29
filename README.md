# OutOfControl

Agente de uso geral em Python — skills, tools, OpenAI agora, Ollama depois.

Estilo próximo ao agente do Cursor: linguagem natural → tools → resultado, com skills carregadas sob demanda.

## O que tem

- **CLI** (`chat`, `watch`) e **API HTTP** (`serve`)
- **Providers**: `openai` | `ollama`
- **Código**: `read/write/edit/delete_file`, `grep`, `glob_files`, shell + `confirm_action`
- **Web** + **browser** opcional (Playwright)
- **Calendário** local com lembretes (`watch`) + **Google Calendar** (`gcal_*`, token opcional)
- **Memória** e **tasks** locais
- **Knowledge** em `docs/` (`knowledge_*`)
- **GitHub**: issues, PRs, CI (`gh` ou `GITHUB_TOKEN`)
- **Skills**: `repo-edit`, `git-workflow`, `web-research`, `daily-planning`, `memory`, `triage-issue`, `pr-helper`, `meeting-notes`, `watch-ci`, `verify-ui`, `knowledge-search`

## Setup

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
# opcional browser:
# pip install -e ".[browser]" && playwright install chromium
cp config.example.yaml config.yaml
export OPENAI_API_KEY=sk-...
# opcionais:
# export GITHUB_TOKEN=...          # ou use `gh auth login`
# export GOOGLE_CALENDAR_ACCESS_TOKEN=...
```

## CLI

```bash
outofcontrol chat "Liste minhas skills e o que você pode fazer"
outofcontrol chat   # REPL: /reset, /exit
```

Ações sensíveis (`rm`/sudo/`git push`, `delete_file`, `github_pr_merge`) pedem confirmação.

## Lembretes de calendário

Eventos em `data/calendar.json` podem ter `remind_minutes_before` (padrão `[60, 15]`).
Rode um watcher em background para notificar:

```bash
# loop contínuo (console + notify-send se existir)
outofcontrol watch

# uma verificação só
outofcontrol watch --once

# intervalo customizado
outofcontrol watch --interval 30
```

Opcional no `config.yaml`: `reminder_webhook_url` (POST JSON com título/corpo/evento).
Com systemd user, um unit simples com `ExecStart=.../outofcontrol watch` mantém o serviço vivo.

## API HTTP

```bash
outofcontrol serve --host 127.0.0.1 --port 8000
```

```bash
curl -s http://127.0.0.1:8000/v1/chat \
  -H 'content-type: application/json' \
  -d '{"message":"O que tem na minha agenda?","session_id":"phone"}'
```

Confirmação pendente → `POST /v1/confirm` com `confirmation_token`.

## Trocar para Ollama

```yaml
provider: ollama
model: llama3.1
ollama_base_url: http://127.0.0.1:11434/v1
```

## Skills

```markdown
---
name: minha-skill
description: Quando usar esta skill.
---

Instruções...
```

## Testes

```bash
pytest -q
```

## Layout

```
src/outofcontrol/   # agente, providers, tools, CLI, API
skills/             # playbooks
docs/               # knowledge base local
config.example.yaml
tests/
```
