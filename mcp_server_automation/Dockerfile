# Dockerfile

# Use the official Python 3.13.3 slim-bookworm image as the base.
# This provides a lightweight Debian-based environment with Python pre-installed.
FROM python:3.13.3-slim-bookworm

# Set the working directory inside the container.
# All subsequent commands will be executed relative to this directory.
WORKDIR /app

# Copy the requirements.txt file into the container's working directory.
# This is done separately to leverage Docker's build cache.
COPY requirements.txt .

# Install the Python dependencies.
# --no-cache-dir: Prevents pip from storing cached data, reducing image size.
# --upgrade: Ensures packages are upgraded if already present.
RUN pip install --no-cache-dir --upgrade -r requirements.txt

# Copy the 'app' directory (containing main.py) into the container.
# For development, this is less critical as we'll use a volume mount,
# but it's good practice for the final image.
COPY app/ app/

# Expose port 8080. This declares that the container listens on this port.
EXPOSE 8080

# Define the command to run the FastAPI application using Uvicorn.
# --host 0.0.0.0: Makes the application accessible from outside the container.
# --port 8080: Specifies the port Uvicorn should listen on.
# --reload: This is crucial for development! Uvicorn will watch for changes
#           in the mounted 'app' directory and automatically restart the app.
CMD ["uvicorn", "app.code:app", "--host", "0.0.0.0", "--port", "8080", "--reload"]