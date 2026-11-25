# MP098 prediction service  ->  docker build -t mp098-api:1.0 .
FROM python:3.13-slim

WORKDIR /app

# libraries first: cached layer
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# code and the exported @champion model
COPY app/ app/
COPY models/model.joblib models/model.joblib

RUN useradd --create-home appuser
USER appuser

# commit the image was built from; /health reports it so CD can verify a rollout
ARG GIT_SHA=dev
ENV GIT_SHA=$GIT_SHA
LABEL org.opencontainers.image.source="https://github.com/testing-archit/tiffin-relay-delivery-time"

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
