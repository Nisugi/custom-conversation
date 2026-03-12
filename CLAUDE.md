# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Custom Conversation is a Home Assistant custom integration (HACS-compatible) that provides a highly configurable conversation agent with multi-provider LLM support via LiteLLM, optional Langfuse observability, and a dual-agent architecture (Home Assistant built-in intent matching + LLM fallback).

## Development Setup

Uses **Pipenv** with Python 3.14. Dependencies are in `Pipfile`.

```bash
pipenv install --dev --skip-lock
```

## Common Commands

### Run unit tests
```bash
pipenv run pytest unit_tests/ -v
```

### Run a single test file
```bash
pipenv run pytest unit_tests/test_conversation.py -v
```

### Run a single test
```bash
pipenv run pytest unit_tests/test_conversation.py::test_name -v
```

### Run with coverage (matches CI)
```bash
pipenv run pytest unit_tests/ -v --cov-branch --cov-report=xml
```

### Lint with ruff
```bash
pipenv run ruff check custom_components/
```

### Format with ruff
```bash
pipenv run ruff format custom_components/
```

## CI

- **Tests** (`test.yml`): Runs `unit_tests/` with pytest, uploads coverage to Codecov.
- **Validate** (`validate.yml`): HACS validation only.
- E2E tests exist in `e2e_tests/` but are not run in CI (they require a live HA instance and API keys).

## Architecture

### Dual-Agent Pipeline

The core flow in `conversation.py` (`CustomConversationEntity._async_handle_message`):
1. If the HA agent is enabled, it tries the built-in Home Assistant intent matcher first (fast, free, deterministic).
2. If that fails (or is disabled) and the LLM agent is enabled, it falls back to an LLM via LiteLLM streaming.
3. If both fail, returns an error response.

When both agents are enabled and HA agent fails, failed messages are stripped from the chat log before passing to the LLM (`_remove_failed_hass_agent_messages`).

### Key Modules

- **`__init__.py`** — Integration setup, config migration (v1→v2 moved provider/model to `data`, LLM params to top-level `options`), Langfuse client lifecycle.
- **`conversation.py`** — `CustomConversationEntity` (the conversation agent). Handles message routing between HA/LLM agents, LiteLLM streaming via `Router` with primary/secondary provider fallback, event firing, Langfuse trace tagging.
- **`cc_llm.py`** — `async_update_llm_data()` bridges prompt management with the HA chat log system. Selects the right prompt source (Langfuse, Custom LLM API, base HA API, or combined) and injects it as the system message.
- **`api.py`** — `CustomLLMAPI` (extends `llm.API`): custom LLM API that builds prompts from context (location, timers, exposed entities) and filters intent tools based on config. `IntentTool` wraps HA intents as LLM-callable tools.
- **`prompt_manager.py`** — `PromptManager` assembles prompts from config options or Langfuse. `LangfuseClient` manages the Langfuse SDK lifecycle, prompt fetching, and conversation scoring.
- **`providers.py`** — `LiteLLMProvider` definitions for supported providers (OpenAI, Gemini, OpenRouter, Mistral). Each knows its model list endpoint. `GeminiProvider` overrides model listing for Google's different API format.
- **`config_flow.py`** — Multi-step config flow with provider selection, API key entry, model selection, and options flow for all settings.
- **`service.py`** — HA services: `generate_image` (DALL-E via LiteLLM) and `score_conversation` (Langfuse scoring).
- **`const.py`** — All configuration keys, defaults, and event names.

### Config Structure

Config entries use `data` for credentials/provider info and `options` for behavioral settings:
- `data`: provider, api_key, base_url, chat_model (primary + optional secondary)
- `options`: temperature, top_p, max_tokens, agents section, custom prompts section, ignored intents, langfuse section

### LLM Completion Flow

`_async_generate_completion` creates a LiteLLM `Router` per request with primary model and optional secondary fallback. Responses are streamed and transformed from LiteLLM's format to HA's `AssistantContentDeltaDict` via `_transform_litellm_stream`. Tool call arguments from small models are repaired by `_parse_tool_args` and `_fix_invalid_arguments`.

### Event System

Fires three event types on the HA event bus:
- `custom_conversation_conversation_started`
- `custom_conversation_conversation_ended` (includes tool calls, affected entities, card data)
- `custom_conversation_conversation_error`

## Testing Notes

- Unit tests mock langfuse at the `sys.modules` level via `test_helpers.py::setup_mocks()` — this must run before any component imports. The `conftest.py` calls `setup_mocks()` at module level before other imports.
- Tests use `pytest-homeassistant-custom-component` which provides the `hass` fixture and HA test infrastructure.
- The `conftest.py` `config_entry` fixture creates a fully wired MockConfigEntry with the v2 data structure.
- `asyncio_mode = "auto"` — all async test functions run automatically without explicit marks.

## Compatibility

- Tracks Home Assistant releases closely (currently targeting HA 2026.3.1).
- Version bumps often correspond to HA core API changes (chat_log, conversation APIs evolve between releases).
- The `manifest.json` `version` field is the integration version; update it when releasing.
