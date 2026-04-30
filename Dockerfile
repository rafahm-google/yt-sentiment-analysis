# Use the official lightweight Python image.
FROM python:3.13-slim

# Allow statements and log messages to immediately appear in the Knative logs
ENV PYTHONUNBUFFERED True

# Set the working directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the source code
COPY . .

# Expose port 8080 (the default for Cloud Run)
EXPOSE 8080

# Run the streamlit app
# We use server.port 8080 and server.address 0.0.0.0 for Cloud Run compatibility
CMD ["sh", "-c", "streamlit run app.py --server.port=${PORT:-8080} --server.address=0.0.0.0"]
