FROM pytorch/pytorch:latest-cuda

# Set the working directory in the container
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    git \
    ffmpeg \
    libsndfile1 \
    && rm -rf /var/lib/apt/lists/*

# Clone the repository
RUN git clone https://github.com/KPEKEP/universal-llm-chatbot.git .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Set the entrypoint to run the bot
CMD ["python", "main.py"]