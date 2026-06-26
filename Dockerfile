# Use an official lightweight Python base image
FROM python:3.11-slim

# Set the working directory inside the container
WORKDIR /app

# Prevent Python from buffering stdout/stderr streams
ENV PYTHONUNBUFFERED=1

# Copy the requirements file first to leverage Docker cache
COPY requirements.txt .

# Install dependencies securely without keeping cache to reduce image size
RUN pip install --no-cache-dir -r requirements.txt

# Copy all the workspace files (including the .pem key!) into the container
COPY . .

# Expose the application port
EXPOSE 8000

# Command to boot up the FastAPI app using Uvicorn 
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
