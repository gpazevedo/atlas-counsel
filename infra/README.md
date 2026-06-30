# ATLAS Counsel — AWS Infrastructure

Terraform configuration for deploying ATLAS Counsel on ECS Fargate, fronted by
an Application Load Balancer, with per-tenant SQLite checkpoints on EFS and
keyless CI/CD via GitHub Actions OIDC.

## Prerequisites

- AWS account with permissions to create the resources below
- Terraform >= 1.5
- Qdrant Cloud cluster (free tier works) — get the URL from the dashboard
- A GitHub Actions OIDC provider in the account (one per account; see below)

## One-time bootstrap (remote state)

State lives in S3 with DynamoDB-based locking. Because a backend can't create
its own bucket, provision these once before the first `terraform init`:

```bash
aws s3api create-bucket --bucket atlas-counsel-tfstate --region us-east-1
aws s3api put-bucket-versioning --bucket atlas-counsel-tfstate \
  --versioning-configuration Status=Enabled

aws dynamodb create-table --table-name atlas-counsel-tflock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST --region us-east-1
```

If you prefer different names, override at init time:
`terraform init -backend-config="bucket=..." -backend-config="dynamodb_table=..."`.

## GitHub Actions OIDC provider

The `github_deploy` role trusts the account's GitHub OIDC provider, referenced
via a data source. If the account doesn't have one yet, create it once:

```bash
aws iam create-open-id-connect-provider \
  --url https://token.actions.githubusercontent.com \
  --client-id-list sts.amazonaws.com \
  --thumbprint-list 6938fd4d98bab03faadb97b34396831e3780aea1
```

After `apply`, set the `github_deploy_role_arn` output as the repository
variable `AWS_ROLE_ARN` (used by `.github/workflows/deploy.yml`).

## Quickstart

```bash
cd infra
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your Qdrant Cloud URL
terraform init
terraform plan
terraform apply
```

## What it creates

- VPC with 2 public subnets, Internet Gateway
- ECS Fargate cluster + service (1 task, 256 CPU / 512 MB)
- Application Load Balancer (HTTP on port 80, health check at /health)
- EFS file system for per-tenant SQLite checkpoints (encrypted at rest)
- ECR repository for Docker images
- CloudWatch log group (30-day retention)
- GitHub Actions OIDC deploy role (keyless ECR push + ECS deploy)
- Security groups: ALB public, app from ALB only, EFS from app only

## Required secrets

- `qdrant_url` — Qdrant Cloud cluster URL (set in terraform.tfvars, not committed)

## Cleaning up

```bash
terraform destroy
```
