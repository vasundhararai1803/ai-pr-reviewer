# Use a fast, official slim python footprint
FROM python:3.11-slim

WORKDIR /app

# Prevent python from buffering stdout/stderr streams
ENV PYTHONUNBUFFERED=1

# Install systems dependencies if necessary
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy over requirements dependency lists
COPY requirements.txt .

# Install pinned python dependencies cleanly
RUN pip install --no-cache-dir -r requirements.txt

# Copy source tree architecture 
COPY ./app ./app

EXPOSE 8000

# Fire server engine on port 8000 bound globally
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
