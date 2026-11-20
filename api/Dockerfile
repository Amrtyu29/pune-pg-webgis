# Bonus API image: a slim Python base, the four packages from requirements.txt, and one file of code.
# Built by "docker compose up -d --build" (service "api" in docker-compose.yml).
FROM python:3.12-slim

WORKDIR /app

# Install the dependencies first, in their own layer, so a change to main.py does not re-download them.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

EXPOSE 8000
# uvicorn serves the FastAPI app object called "app" in main.py on every interface of the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
