pipeline {
    
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        choice(
            name: 'BRANCH_SOURCE',
            choices: ['auto', 'develop', 'master', 'main'],
            description: 'auto = infer from BRANCH_NAME/CHANGE_TARGET'
        )
        string(name: 'EC2_HOST', defaultValue: 'ec2-54-179-86-79.ap-southeast-1.compute.amazonaws.com', description: 'EC2 public hostname or IP')
        string(name: 'EC2_USER', defaultValue: 'ubuntu', description: 'SSH user on EC2')
        string(name: 'EC2_PORT', defaultValue: '22', description: 'SSH port')
        string(name: 'SSH_CREDENTIALS_ID', defaultValue: 'ec2-pem-key', description: 'Jenkins Credentials ID (SSH Username with private key PEM)')
        string(name: 'REMOTE_BASE_DIR', defaultValue: '/home/ubuntu/apps', description: 'Base directory on EC2')
        string(name: 'API_SUBDIR', defaultValue: 'bitenex-api', description: 'Folder name for API repo on EC2')
        string(name: 'REPO_URL', defaultValue: 'https://github.com/vietviet08/bitnex-api', description: 'Git repository URL accessible from EC2')
    }

    environment {
        DEPLOY_BRANCH = ''
    }

    stages {
        stage('Resolve Branch') {
            steps {
                script {
                    def normalize = { String v ->
                        if (!v) return ''
                        return v.replaceFirst(/^origin\//, '').trim()
                    }

                    def selected = params.BRANCH_SOURCE?.trim()
                    def fromPrTarget = normalize(env.CHANGE_TARGET)
                    def fromBranchName = normalize(env.BRANCH_NAME)
                    def resolvedBranch = 'develop'

                    if (selected && selected != 'auto') {
                        resolvedBranch = selected
                    } else if (fromPrTarget in ['develop', 'master', 'main']) {
                        resolvedBranch = fromPrTarget
                    } else if (fromBranchName in ['develop', 'master', 'main']) {
                        resolvedBranch = fromBranchName
                    }

                    if (!(resolvedBranch in ['develop', 'master', 'main'])) {
                        resolvedBranch = 'develop'
                    }

                    env.DEPLOY_BRANCH = resolvedBranch

                    echo "Resolved deploy branch: ${resolvedBranch}"
                }
            }
        }

        stage('Deploy API on EC2') {
            steps {
                script {
                    def normalize = { String v ->
                        if (!v) return ''
                        return v.replaceFirst(/^origin\//, '').trim()
                    }

                    def ec2Host = params.EC2_HOST?.trim()
                    def ec2User = params.EC2_USER?.trim() ?: 'ubuntu'
                    def ec2Port = params.EC2_PORT?.trim() ?: '22'
                    def remoteBaseDir = params.REMOTE_BASE_DIR?.trim() ?: '/home/ubuntu/apps'
                    def apiSubdir = params.API_SUBDIR?.trim() ?: 'bitenex-api'
                    def repoUrl = params.REPO_URL?.trim()
                    def selected = params.BRANCH_SOURCE?.trim()
                    def deployBranch = 'develop'

                    if (selected && selected != 'auto') {
                        deployBranch = selected
                    } else {
                        def fromPrTarget = normalize(env.CHANGE_TARGET)
                        def fromBranchName = normalize(env.BRANCH_NAME)
                        if (fromPrTarget in ['develop', 'master', 'main']) {
                            deployBranch = fromPrTarget
                        } else if (fromBranchName in ['develop', 'master', 'main']) {
                            deployBranch = fromBranchName
                        }
                    }

                    if (!(deployBranch in ['develop', 'master', 'main'])) {
                        deployBranch = 'develop'
                    }

                    if (!ec2Host) {
                        error('EC2_HOST is required')
                    }
                    if (!repoUrl) {
                        error('REPO_URL is required')
                    }

                    withCredentials([
                        sshUserPrivateKey(
                            credentialsId: params.SSH_CREDENTIALS_ID,
                            keyFileVariable: 'SSH_KEY_FILE',
                            usernameVariable: 'SSH_USERNAME'
                        )
                    ]) {
                        withEnv([
                            "EC2_HOST=${ec2Host}",
                            "EC2_USER=${ec2User}",
                            "EC2_PORT=${ec2Port}",
                            "REMOTE_BASE_DIR=${remoteBaseDir}",
                            "API_SUBDIR=${apiSubdir}",
                            "REPO_URL=${repoUrl}",
                            "DEPLOY_BRANCH=${deployBranch}"
                        ]) {
                            sh '''#!/usr/bin/env bash
set -euo pipefail

REMOTE_USER="$EC2_USER"
if [ -z "$REMOTE_USER" ]; then
  REMOTE_USER="$SSH_USERNAME"
fi
SSH_OPTS="-i $SSH_KEY_FILE -p ${EC2_PORT} -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile=/dev/null"

ssh $SSH_OPTS "$REMOTE_USER@$EC2_HOST" \
  DEPLOY_BRANCH="$DEPLOY_BRANCH" \
  REMOTE_BASE_DIR="$REMOTE_BASE_DIR" \
  API_SUBDIR="$API_SUBDIR" \
  REPO_URL="$REPO_URL" \
  'bash -se' <<'REMOTE_EOF'
set -euo pipefail

APP_DIR="$REMOTE_BASE_DIR/$API_SUBDIR"

echo "[info] Deploy branch: $DEPLOY_BRANCH"
echo "[info] App dir: $APP_DIR"

mkdir -p "$REMOTE_BASE_DIR"

if [ ! -d "$APP_DIR/.git" ]; then
  echo "[git] Repository not found, cloning..."
  git clone "$REPO_URL" "$APP_DIR"
fi

cd "$APP_DIR"

echo "[git] Fetch latest"
git fetch --all --prune

if git show-ref --verify --quiet "refs/remotes/origin/$DEPLOY_BRANCH"; then
  git checkout "$DEPLOY_BRANCH"
  git reset --hard "origin/$DEPLOY_BRANCH"
else
  echo "[error] Branch origin/$DEPLOY_BRANCH not found"
  exit 1
fi

echo "[lint] Basic lint (always bypass)"
if command -v ruff >/dev/null 2>&1; then
  ruff check . || true
else
  echo "[lint] ruff not found on EC2, skipping (bypass enabled)"
fi

echo "[test] Run pytest"
if [ ! -f requirements.txt ]; then
    echo "[error] requirements.txt not found"
    exit 1
fi

if ! python3 -m venv .venv-ci >/dev/null 2>&1; then
    echo "[test] python3-venv missing, trying to install"
    sudo apt-get update
    sudo apt-get install -y python3-venv
    python3 -m venv .venv-ci
fi

. .venv-ci/bin/activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pytest
pytest

echo "[docker] Build API image"
docker compose -f docker-compose.yml build api

echo "[docker] Deploy API container"
docker compose -f docker-compose.yml up -d api

echo "[docker] Current API container status"
docker compose -f docker-compose.yml ps api
REMOTE_EOF
'''
                        }
                    }
                }
            }
        }
    }

    post {
        success {
            echo 'Deployment completed successfully.'
        }
        failure {
            echo 'Deployment failed. Check stage logs for details.'
        }
    }
}
