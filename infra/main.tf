terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }

  # Remote state in S3 with DynamoDB-based state locking. The bucket and lock
  # table must exist before `terraform init` — see infra/README.md for the
  # one-time bootstrap. Backend blocks can't use variables, so these are
  # literal; override per-environment with `-backend-config` if needed.
  backend "s3" {
    bucket         = "atlas-counsel-tfstate"
    key            = "atlas-counsel/terraform.tfstate"
    region         = "us-east-1"
    dynamodb_table = "atlas-counsel-tflock"
    encrypt        = true
  }
}

provider "aws" {
  region = var.region
  default_tags {
    tags = {
      Project = var.project
    }
  }
}

# ── VPC & Networking ──────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_hostnames = true
  enable_dns_support   = true
}

resource "aws_subnet" "public" {
  count                   = 2
  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(aws_vpc.main.cidr_block, 8, count.index + 1)
  availability_zone       = data.aws_availability_zones.available.names[count.index]
  map_public_ip_on_launch = true
}

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }
}

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

data "aws_availability_zones" "available" {}

# ── ECR ───────────────────────────────────────────────────────────────────────

resource "aws_ecr_repository" "app" {
  name                 = var.project
  image_tag_mutability = "MUTABLE"
  force_delete         = true
}

# ── EFS (per-tenant checkpoints) ──────────────────────────────────────────────

resource "aws_efs_file_system" "checkpoints" {
  encrypted = true
}

resource "aws_efs_access_point" "data" {
  file_system_id = aws_efs_file_system.checkpoints.id
  posix_user {
    uid = 1000
    gid = 1000
  }
  root_directory {
    path = "/data"
    creation_info {
      owner_uid   = 1000
      owner_gid   = 1000
      permissions = "755"
    }
  }
}

resource "aws_security_group" "efs" {
  name        = "${var.project}-efs"
  description = "EFS mount targets"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 2049
    to_port         = 2049
    protocol        = "tcp"
    security_groups = [aws_security_group.app.id]
  }
}

resource "aws_efs_mount_target" "data" {
  count           = 2
  file_system_id  = aws_efs_file_system.checkpoints.id
  subnet_id       = aws_subnet.public[count.index].id
  security_groups = [aws_security_group.efs.id]
}

# ── Secrets Manager ───────────────────────────────────────────────────────────

resource "random_password" "mcp_api_key" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "qdrant_url" {
  name = "${var.project}/qdrant-url"
}

resource "aws_secretsmanager_secret_version" "qdrant_url" {
  secret_id     = aws_secretsmanager_secret.qdrant_url.id
  secret_string = var.qdrant_url
}

resource "aws_secretsmanager_secret" "mcp_api_key" {
  name = "${var.project}/mcp-api-key"
}

resource "aws_secretsmanager_secret_version" "mcp_api_key" {
  secret_id     = aws_secretsmanager_secret.mcp_api_key.id
  secret_string = random_password.mcp_api_key.result
}

resource "random_password" "mcp_jwt_secret" {
  length  = 64
  special = false
}

resource "aws_secretsmanager_secret" "mcp_jwt_secret" {
  name = "${var.project}/mcp-jwt-secret"
}

resource "aws_secretsmanager_secret_version" "mcp_jwt_secret" {
  secret_id     = aws_secretsmanager_secret.mcp_jwt_secret.id
  secret_string = random_password.mcp_jwt_secret.result
}

# ── ALB ───────────────────────────────────────────────────────────────────────

resource "aws_security_group" "alb" {
  name        = "${var.project}-alb"
  description = "ALB public ingress"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb" "main" {
  name               = var.project
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = aws_subnet.public[*].id
  idle_timeout       = 300
}

resource "aws_lb_target_group" "app" {
  name        = var.project
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = aws_vpc.main.id
  target_type = "ip"
  health_check {
    path    = "/health"
    matcher = "200"
  }
}

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"
  default_action {
    type = "redirect"
    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.main.arn
  port              = 443
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = var.certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.app.arn
  }
}

# ── ECS ───────────────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = var.project
}

resource "aws_security_group" "app" {
  name        = "${var.project}-app"
  description = "App container"
  vpc_id      = aws_vpc.main.id
  ingress {
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_ecs_task_definition" "app" {
  family                   = var.project
  network_mode             = "awsvpc"
  requires_compatibilities = ["FARGATE"]
  cpu                      = var.container_cpu
  memory                   = var.container_memory
  execution_role_arn       = aws_iam_role.task_exec.arn
  task_role_arn            = aws_iam_role.task.arn

  container_definitions = jsonencode([{
    name  = var.project
    image = "${aws_ecr_repository.app.repository_url}:${var.container_image_tag}"
    portMappings = [{
      containerPort = 8000
      protocol      = "tcp"
    }]
    environment = [
      { name = "CHECKPOINT_DIR", value = "/data" },
      { name = "MCP_REQUIRE_AUTH", value = "true" },
      { name = "MCP_JWT_AUDIENCE", value = "atlas-counsel" },
    ]
    secrets = [
      { name = "QDRANT_URL", valueFrom = aws_secretsmanager_secret.qdrant_url.arn },
      { name = "MCP_API_KEY", valueFrom = aws_secretsmanager_secret.mcp_api_key.arn },
      { name = "MCP_JWT_SECRET", valueFrom = aws_secretsmanager_secret.mcp_jwt_secret.arn },
    ]
    mountPoints = [{
      sourceVolume  = "checkpoints"
      containerPath = "/data"
    }]
    logConfiguration = {
      logDriver = "awslogs"
      options = {
        awslogs-group         = aws_cloudwatch_log_group.app.name
        awslogs-region        = var.region
        awslogs-stream-prefix = var.project
      }
    }
  }])

  volume {
    name = "checkpoints"
    efs_volume_configuration {
      file_system_id     = aws_efs_file_system.checkpoints.id
      transit_encryption = "ENABLED"
      authorization_config {
        access_point_id = aws_efs_access_point.data.id
      }
    }
  }
}

resource "aws_ecs_service" "app" {
  name            = var.project
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.app.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"
  network_configuration {
    subnets          = aws_subnet.public[*].id
    security_groups  = [aws_security_group.app.id]
    assign_public_ip = true
  }
  load_balancer {
    target_group_arn = aws_lb_target_group.app.arn
    container_name   = var.project
    container_port   = 8000
  }
  depends_on = [aws_lb_listener.http, aws_lb_listener.https]
}

# ── CloudWatch Logs ────────────────────────────────────────────────────────────

resource "aws_cloudwatch_log_group" "app" {
  name              = "/ecs/${var.project}"
  retention_in_days = 30
}

# ── IAM (task roles) ──────────────────────────────────────────────────────────

resource "aws_iam_role" "task_exec" {
  name = "${var.project}-task-exec"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "task_exec" {
  role       = aws_iam_role.task_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "task_exec_secrets" {
  name = "${var.project}-task-exec-secrets"
  role = aws_iam_role.task_exec.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Action = ["secretsmanager:GetSecretValue"]
      Resource = [
        aws_secretsmanager_secret.qdrant_url.arn,
        aws_secretsmanager_secret.mcp_api_key.arn,
        aws_secretsmanager_secret.mcp_jwt_secret.arn,
      ]
    }]
  })
}

resource "aws_iam_role" "task" {
  name = "${var.project}-task"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "ecs-tasks.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

# ── GitHub Actions OIDC (keyless CI/CD) ───────────────────────────────────────
# An AWS account can hold only one GitHub OIDC provider, so reference the
# existing one via a data source rather than creating it here.

data "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"
}

resource "aws_iam_role" "github_deploy" {
  name = "${var.project}-github-deploy"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Federated = data.aws_iam_openid_connect_provider.github.arn }
      Action    = "sts:AssumeRoleWithWebIdentity"
      Condition = {
        StringEquals = { "token.actions.githubusercontent.com:aud" : "sts.amazonaws.com" }
        StringLike   = { "token.actions.githubusercontent.com:sub" : "repo:gpazevedo/atlas-counsel:*" }
      }
    }]
  })
}

resource "aws_iam_role_policy" "github_deploy" {
  name = "${var.project}-github-deploy"
  role = aws_iam_role.github_deploy.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken",
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:PutImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
        ]
        Resource = "*"
      },
      {
        Effect = "Allow"
        Action = [
          "ecs:UpdateService",
          "ecs:DescribeServices",
        ]
        Resource = aws_ecs_service.app.id
      }
    ]
  })
}
