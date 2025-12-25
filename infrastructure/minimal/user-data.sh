#!/bin/bash
# =============================================================================
# SNS Agent - EC2 User Data Script
# Sets up Docker and runs the application
# =============================================================================

set -e

# Variables (injected by Terraform)
PROJECT_NAME="${project_name}"
AWS_REGION="${aws_region}"
SECRET_KEY="${secret_key}"
USE_ECR="${use_ecr}"
ECR_REPO_URL="${ecr_repo_url}"
AWS_ACCOUNT_ID="${aws_account_id}"

# Log everything
exec > >(tee /var/log/user-data.log) 2>&1
echo "Starting user-data script at $(date)"

# -----------------------------------------------------------------------------
# System Updates
# -----------------------------------------------------------------------------
echo "Updating system packages..."
dnf update -y

# -----------------------------------------------------------------------------
# Install Docker
# -----------------------------------------------------------------------------
echo "Installing Docker..."
dnf install -y docker
systemctl enable docker
systemctl start docker

# Add ec2-user to docker group
usermod -aG docker ec2-user

# -----------------------------------------------------------------------------
# Install Docker Compose
# -----------------------------------------------------------------------------
echo "Installing Docker Compose..."
DOCKER_COMPOSE_VERSION="v2.24.0"
curl -L "https://github.com/docker/compose/releases/download/$${DOCKER_COMPOSE_VERSION}/docker-compose-linux-x86_64" -o /usr/local/bin/docker-compose
chmod +x /usr/local/bin/docker-compose
ln -sf /usr/local/bin/docker-compose /usr/bin/docker-compose

# -----------------------------------------------------------------------------
# Install Git
# -----------------------------------------------------------------------------
echo "Installing Git..."
dnf install -y git

# -----------------------------------------------------------------------------
# Create application directory
# -----------------------------------------------------------------------------
APP_DIR="/opt/$${PROJECT_NAME}"
mkdir -p $${APP_DIR}
cd $${APP_DIR}

# -----------------------------------------------------------------------------
# Create docker-compose.yml
# -----------------------------------------------------------------------------
echo "Creating docker-compose.yml..."
cat > docker-compose.yml << 'COMPOSE_EOF'
version: '3.8'

services:
  # Redis (in-memory cache)
  redis:
    image: redis:7-alpine
    restart: unless-stopped
    command: redis-server --appendonly no --maxmemory 128mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 3

  # Backend API
  backend:
    image: ${USE_ECR == "true" ? ECR_REPO_URL : "ghcr.io/your-org/sns-agent-backend"}:latest
    build:
      context: ./backend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "8006:8006"
    environment:
      - DATABASE_URL=sqlite+aiosqlite:///data/sns_agent.db
      - REDIS_URL=redis://redis:6379/0
      - SECRET_KEY=${SECRET_KEY}
      - PYTHONUNBUFFERED=1
    volumes:
      - ./data:/app/data
      - ./browser_data:/app/browser_data
    depends_on:
      redis:
        condition: service_healthy
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8006/health"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  # Frontend
  frontend:
    image: ${USE_ECR == "true" ? ECR_REPO_URL : "ghcr.io/your-org/sns-agent-frontend"}:latest
    build:
      context: ./frontend
      dockerfile: Dockerfile
    restart: unless-stopped
    ports:
      - "3006:3006"
    environment:
      - NEXT_PUBLIC_API_URL=http://backend:8006
    depends_on:
      backend:
        condition: service_healthy

volumes:
  data:
  browser_data:
COMPOSE_EOF

# -----------------------------------------------------------------------------
# Create data directory
# -----------------------------------------------------------------------------
mkdir -p $${APP_DIR}/data
mkdir -p $${APP_DIR}/browser_data

# -----------------------------------------------------------------------------
# Create .env file
# -----------------------------------------------------------------------------
cat > .env << ENV_EOF
SECRET_KEY=$${SECRET_KEY}
DATABASE_URL=sqlite+aiosqlite:///data/sns_agent.db
REDIS_URL=redis://redis:6379/0
ENV_EOF

# -----------------------------------------------------------------------------
# ECR Login (if using ECR)
# -----------------------------------------------------------------------------
if [ "$${USE_ECR}" = "true" ] && [ -n "$${ECR_REPO_URL}" ]; then
    echo "Logging into ECR..."
    aws ecr get-login-password --region $${AWS_REGION} | docker login --username AWS --password-stdin $${AWS_ACCOUNT_ID}.dkr.ecr.$${AWS_REGION}.amazonaws.com
fi

# -----------------------------------------------------------------------------
# Create systemd service for docker-compose
# -----------------------------------------------------------------------------
echo "Creating systemd service..."
cat > /etc/systemd/system/$${PROJECT_NAME}.service << SERVICE_EOF
[Unit]
Description=SNS Agent Docker Compose Application
Requires=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=yes
WorkingDirectory=$${APP_DIR}
ExecStart=/usr/local/bin/docker-compose up -d
ExecStop=/usr/local/bin/docker-compose down
TimeoutStartSec=300

[Install]
WantedBy=multi-user.target
SERVICE_EOF

systemctl daemon-reload
systemctl enable $${PROJECT_NAME}.service

# -----------------------------------------------------------------------------
# Install CloudWatch Agent (optional - for log monitoring)
# -----------------------------------------------------------------------------
echo "Installing CloudWatch Agent..."
dnf install -y amazon-cloudwatch-agent

cat > /opt/aws/amazon-cloudwatch-agent/etc/amazon-cloudwatch-agent.json << CW_EOF
{
  "logs": {
    "logs_collected": {
      "files": {
        "collect_list": [
          {
            "file_path": "/var/log/user-data.log",
            "log_group_name": "/ec2/$${PROJECT_NAME}",
            "log_stream_name": "{instance_id}/user-data"
          },
          {
            "file_path": "$${APP_DIR}/data/*.log",
            "log_group_name": "/ec2/$${PROJECT_NAME}",
            "log_stream_name": "{instance_id}/app"
          }
        ]
      }
    }
  }
}
CW_EOF

systemctl enable amazon-cloudwatch-agent
systemctl start amazon-cloudwatch-agent

# -----------------------------------------------------------------------------
# Install Playwright dependencies (for browser automation)
# -----------------------------------------------------------------------------
echo "Installing Playwright dependencies..."
dnf install -y \
    alsa-lib \
    atk \
    cups-libs \
    gtk3 \
    libXcomposite \
    libXcursor \
    libXdamage \
    libXext \
    libXi \
    libXrandr \
    libXScrnSaver \
    libXtst \
    pango \
    xorg-x11-fonts-100dpi \
    xorg-x11-fonts-75dpi \
    xorg-x11-fonts-cyrillic \
    xorg-x11-fonts-misc \
    xorg-x11-fonts-Type1 \
    xorg-x11-utils \
    mesa-libgbm \
    nss \
    libdrm

# -----------------------------------------------------------------------------
# Final message
# -----------------------------------------------------------------------------
echo "========================================"
echo "SNS Agent setup completed at $(date)"
echo "========================================"
echo ""
echo "Next steps:"
echo "1. Build and push your Docker images"
echo "2. SSH into the instance and run: cd $${APP_DIR} && docker-compose up -d"
echo ""
echo "Or if using pre-built images:"
echo "  systemctl start $${PROJECT_NAME}"
echo ""
echo "Access URLs:"
echo "  Frontend: http://<public-ip>:3006"
echo "  Backend:  http://<public-ip>:8006"
echo "========================================"
