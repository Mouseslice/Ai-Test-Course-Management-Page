# Environment Variables

## Required
- `TUTOR_OPENAI_API_KEY`
- `TUTOR_OPENAI_API_BASE`
- `TUTOR_OPENAI_MODEL`

## Required when RAG is enabled
- `TUTOR_EMBEDDING_API_KEY`
- `TUTOR_EMBEDDING_API_BASE`
- `TUTOR_EMBEDDING_MODEL`

## Required when translation is enabled
- `TUTOR_TRANSLATION_API_KEY`
- `TUTOR_TRANSLATION_API_BASE`
- `TUTOR_TRANSLATION_MODEL`

## Core runtime
- `BACKEND_PORT` (default: `8000`)
- `REDIS_URL` (default in compose: `redis://redis:6379/0`)
- `REDIS_HOST` (default in compose: `redis`)
- `REDIS_PORT` (default in compose: `6379`)
- `DATABASE_URL` (default in compose: `sqlite:///./app/db/database.db`)
- `LLM_MAX_TOKENS` (default: `65535`)
- `LLM_TEMPERATURE` (default: `0.7`)

## Feature flags
- `ENABLE_RAG_SERVICE` (`true`/`false`)
- `ENABLE_SENTIMENT_ANALYSIS` (`true`/`false`)
- `ENABLE_CLUSTERING_SERVICE` (`true`/`false`)
- `ENABLE_TRANSLATION_SERVICE` (`true`/`false`)
