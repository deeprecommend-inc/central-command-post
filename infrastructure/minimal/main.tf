# =============================================================================
# SNS Agent - Minimal/Cheapest Infrastructure Configuration
# =============================================================================
# Cost Breakdown (ap-northeast-1):
# - EC2 t3.micro: ~$8.50/month (or FREE with free tier)
# - EBS 20GB gp3: ~$1.60/month
# - Elastic IP: FREE when attached to running instance
# - Data Transfer: ~$0.114/GB outbound
# Total: ~$10-15/month (or nearly FREE with free tier)
# =============================================================================

terraform {
  required_version = ">= 1.0"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------------------------------------------------------
# Data Sources
# -----------------------------------------------------------------------------

# Get latest Amazon Linux 2023 AMI
data "aws_ami" "amazon_linux_2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "virtualization-type"
    values = ["hvm"]
  }
}

# Get current AWS account ID
data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# VPC - Minimal Setup (Public Subnet Only)
# -----------------------------------------------------------------------------

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = {
    Name = "${var.project_name}-vpc"
  }
}

resource "aws_subnet" "public" {
  vpc_id                  = aws_vpc.main.id
  cidr_block              = "10.0.1.0/24"
  availability_zone       = "${var.aws_region}a"
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project_name}-public"
  }
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-igw"
  }
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project_name}-public-rt"
  }
}

resource "aws_route_table_association" "public" {
  subnet_id      = aws_subnet.public.id
  route_table_id = aws_route_table.public.id
}

# -----------------------------------------------------------------------------
# Security Group
# -----------------------------------------------------------------------------

resource "aws_security_group" "instance" {
  name        = "${var.project_name}-instance-sg"
  description = "Security group for SNS Agent instance"
  vpc_id      = aws_vpc.main.id

  # SSH (optional - can be removed for production)
  ingress {
    from_port   = 22
    to_port     = 22
    protocol    = "tcp"
    cidr_blocks = var.ssh_allowed_cidr
    description = "SSH access"
  }

  # HTTP
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTP access"
  }

  # HTTPS
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "HTTPS access"
  }

  # Frontend direct access (for testing)
  ingress {
    from_port   = 3006
    to_port     = 3006
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Frontend direct access"
  }

  # Backend API direct access (for testing)
  ingress {
    from_port   = 8006
    to_port     = 8006
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Backend API direct access"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound traffic"
  }

  tags = {
    Name = "${var.project_name}-instance-sg"
  }
}

# -----------------------------------------------------------------------------
# IAM Role for EC2 (for ECR access and SSM)
# -----------------------------------------------------------------------------

resource "aws_iam_role" "ec2_role" {
  name = "${var.project_name}-ec2-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Action = "sts:AssumeRole"
        Effect = "Allow"
        Principal = {
          Service = "ec2.amazonaws.com"
        }
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-ec2-role"
  }
}

resource "aws_iam_role_policy_attachment" "ssm_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

resource "aws_iam_role_policy_attachment" "ecr_policy" {
  role       = aws_iam_role.ec2_role.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonEC2ContainerRegistryReadOnly"
}

resource "aws_iam_instance_profile" "ec2_profile" {
  name = "${var.project_name}-ec2-profile"
  role = aws_iam_role.ec2_role.name
}

# -----------------------------------------------------------------------------
# ECR Repository (optional - can use Docker Hub instead)
# -----------------------------------------------------------------------------

resource "aws_ecr_repository" "app" {
  count                = var.use_ecr ? 1 : 0
  name                 = var.project_name
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = false
  }

  # Lifecycle policy to keep costs down
  lifecycle {
    prevent_destroy = false
  }

  tags = {
    Name = "${var.project_name}-ecr"
  }
}

# ECR Lifecycle Policy - Keep only last 3 images
resource "aws_ecr_lifecycle_policy" "app" {
  count      = var.use_ecr ? 1 : 0
  repository = aws_ecr_repository.app[0].name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep only last 3 images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = 3
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}

# -----------------------------------------------------------------------------
# SSH Key Pair (optional)
# -----------------------------------------------------------------------------

resource "aws_key_pair" "main" {
  count      = var.ssh_public_key != "" ? 1 : 0
  key_name   = "${var.project_name}-key"
  public_key = var.ssh_public_key

  tags = {
    Name = "${var.project_name}-key"
  }
}

# -----------------------------------------------------------------------------
# EC2 Instance - Single Instance Running Everything
# -----------------------------------------------------------------------------

resource "aws_instance" "main" {
  ami                    = data.aws_ami.amazon_linux_2023.id
  instance_type          = var.instance_type
  subnet_id              = aws_subnet.public.id
  vpc_security_group_ids = [aws_security_group.instance.id]
  iam_instance_profile   = aws_iam_instance_profile.ec2_profile.name
  key_name               = var.ssh_public_key != "" ? aws_key_pair.main[0].key_name : null

  root_block_device {
    volume_size           = var.root_volume_size
    volume_type           = "gp3"
    iops                  = 3000
    throughput            = 125
    delete_on_termination = true
    encrypted             = true
  }

  user_data = base64encode(templatefile("${path.module}/user-data.sh", {
    project_name     = var.project_name
    aws_region       = var.aws_region
    secret_key       = var.secret_key
    use_ecr          = var.use_ecr
    ecr_repo_url     = var.use_ecr ? aws_ecr_repository.app[0].repository_url : ""
    aws_account_id   = data.aws_caller_identity.current.account_id
  }))

  # Enable detailed monitoring only if needed (costs extra)
  monitoring = false

  # Use spot instance for even more savings (optional)
  # instance_market_options {
  #   market_type = "spot"
  #   spot_options {
  #     max_price = "0.005"
  #   }
  # }

  tags = {
    Name = "${var.project_name}-instance"
  }

  lifecycle {
    create_before_destroy = true
  }
}

# -----------------------------------------------------------------------------
# Elastic IP (Free when attached to running instance)
# -----------------------------------------------------------------------------

resource "aws_eip" "main" {
  instance = aws_instance.main.id
  domain   = "vpc"

  tags = {
    Name = "${var.project_name}-eip"
  }
}

# -----------------------------------------------------------------------------
# CloudWatch Log Group (Minimal retention for cost saving)
# -----------------------------------------------------------------------------

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ec2/${var.project_name}"
  retention_in_days = 3  # Minimum retention for cost saving

  tags = {
    Name = "${var.project_name}-logs"
  }
}
