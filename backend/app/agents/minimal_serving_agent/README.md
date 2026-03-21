# Minimal Serving Specialist Agent

A small sample agent designed to be deployed on Databricks Model Serving as
a specialist for the LangGraph supervisor.

## Deployment

1. **Log the model** using the deploy notebook at
   `notebooks/serving/deploy_specialist.py`
2. **Create a serving endpoint** from the registered model
3. **Configure the app** by setting:
   - `SERVING_SPECIALIST_ENDPOINT=<endpoint-name>`
   - `SERVING_SPECIALIST_API_MODE=chat_completions`  (or `responses`)

## Compatibility

The app's serving specialist tool supports both:
- `chat_completions` — standard OpenAI chat completions API
- `responses` — Databricks Responses API

Set `SERVING_SPECIALIST_API_MODE` accordingly based on how you deploy
this agent.

## Customization

- Edit `SYSTEM_PROMPT` to tailor the agent's behavior
- Change the model name in the `predict` method
- Add tool calling, RAG, or other capabilities as needed
