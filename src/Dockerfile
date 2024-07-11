FROM public.ecr.aws/lambda/python:3.12

# Install unzip using microdnf
RUN microdnf install -y unzip

# Copy all the files in a folder
COPY . ${LAMBDA_TASK_ROOT}

# Determine the OS architecture
ARG ARCH=${ARCH:-"amd64"}

# Determine the Vault radar version from environment variable or use 0.11.0 as default
ARG VAULT_RADAR_VERSION=${VAULT_RADAR_VERSION:-0.11.0}

# Create a directory for Vault radar
RUN mkdir /vault-radar

# Download and install the appropriate Vault radar binary based on the architecture
RUN cd /vault-radar && if [ "$ARCH" = "amd64" ]; then \
    curl -LO https://releases.hashicorp.com/vault-radar/${VAULT_RADAR_VERSION}/vault-radar_${VAULT_RADAR_VERSION}_linux_amd64.zip && \
    unzip vault-radar_${VAULT_RADAR_VERSION}_linux_amd64.zip && \
    rm vault-radar_${VAULT_RADAR_VERSION}_linux_amd64.zip; \
    elif [ "$ARCH" = "arm64" ]; then \
    curl -LO https://releases.hashicorp.com/vault-radar/${VAULT_RADAR_VERSION}/vault-radar_${VAULT_RADAR_VERSION}_linux_arm64.zip && \
    unzip vault-radar_${VAULT_RADAR_VERSION}_linux_arm64.zip && \
    rm vault-radar_${VAULT_RADAR_VERSION}_linux_arm64.zip; \
    elif [ "$ARCH" = "darwin" ]; then \
    curl -LO https://releases.hashicorp.com/vault-radar/${VAULT_RADAR_VERSION}/vault-radar_${VAULT_RADAR_VERSION}_darwin_amd64.zip && \
    unzip vault-radar_${VAULT_RADAR_VERSION}_darwin_amd64.zip && \
    rm vault-radar_${VAULT_RADAR_VERSION}_darwin_amd64.zip; \
    else \
    echo "Unsupported architecture"; \
    exit 1; \
    fi

# Install the specified packages
RUN pip install -r requirements.txt

# Set the CMD to the lambda_handler
CMD [ "handler.lambda_handler" ]
