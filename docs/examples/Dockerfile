# This Dockerfile is for reference only.
# The doc_builder.py script now automatically creates and uses Docker
# containers for local builds. You don't need to build this manually.
#
# Note: The actual Dockerfile used by doc_builder.py includes additional
# setup for authentication with Git repositories and PyPI/Artifactory.

FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y git openssh-client make && \
    rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy the current directory contents into the container
COPY . /app/

# Install the package
RUN pip install --no-cache-dir -e .

# Set up SSH for GitHub access
RUN mkdir -p /root/.ssh && \
    echo "StrictHostKeyChecking no" >> /root/.ssh/config

# Command to run when the container starts
ENTRYPOINT ["python", "-m", "tts_ci_cd.doc_builder"]
CMD ["--help"]

# Note: This container is similar to what the doc_builder.py script
# creates automatically when run locally. The script detects when
# it's running in GitHub Actions and uses direct execution instead.
