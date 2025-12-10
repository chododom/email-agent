_default:
    just --list

### Variables ###

NAME := "email-agent"
ARTIFACT_REGISTRY := "europe-west3-docker.pkg.dev/alza-email-agent/email-agent-repo"

### Recipes ###

fix:
    uv run ruff check --fix email_agent/

format:
    uv run ruff format email_agent/

run:
    uvicorn email_agent.main:app --host 0.0.0.0 --port 8080 --reload

build tag="latest":
    docker build --platform linux/amd64 -t {{NAME}}:{{tag}} .

run-docker tag="latest":
    docker run -p 8080:8080 {{NAME}}:{{tag}}

push-ar tag="latest":
    docker build --platform linux/amd64 -t {{ARTIFACT_REGISTRY}}/{{NAME}}:{{tag}} .
    docker push {{ARTIFACT_REGISTRY}}/{{NAME}}:{{tag}}

test-hook:
    curl -X POST http://localhost:8080/v1/gmail-webhook \
        -H "Content-Type: application/json" \
        -d '{ \
            "message": { \
                "data": "ewogICJlbWFpbEFkZHJlc3MiOiAiYWx6YS5hZ2VudC5kb21pbmlrQGdtYWlsLmNvbSIsCiAgImhpc3RvcnlJZCI6ICIxOTUwIgp9", \
                "messageId": "pubsub-123456789", \
                "publishTime": "2025-12-07T00:00:00Z" \
            }, \
            "subscription": "projects/your-project-id/subscriptions/gmail-push-subscription" \
        }'