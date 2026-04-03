pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
    }

    parameters {
        string(name: 'REPO_URL', defaultValue: 'https://github.com/vietviet08/bitenex-api.git', description: 'Git repository URL')
        string(name: 'DEPLOY_DIR', defaultValue: '/opt/bitenex/repo', description: 'Deployment checkout on the Jenkins host')
        string(name: 'COMPOSE_FILE', defaultValue: 'docker-compose.prod.yml', description: 'Compose file used in deployment')
        string(name: 'AWS_REGION', defaultValue: 'ap-southeast-1', description: 'AWS region for ECR')
        string(name: 'ECR_REGISTRY', defaultValue: '640168447652.dkr.ecr.ap-southeast-1.amazonaws.com', description: 'Optional ECR registry, e.g. 123456789012.dkr.ecr.ap-southeast-1.amazonaws.com')
        string(name: 'ECR_REPOSITORY', defaultValue: 'bitenex-api', description: 'ECR repository name')
    }

    environment {
        LOCAL_IMAGE_NAME = 'bitenex-api'
        DEPLOY_IMAGE = 'bitenex-api:local'
        IMAGE_TAG = 'develop-local'
        SHORT_COMMIT = 'unknown'
        BUILD_BRANCH = 'develop'
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    def resolvedBranch = env.CHANGE_TARGET?.trim()

                    if (!resolvedBranch) {
                        resolvedBranch = env.BRANCH_NAME?.trim()
                    }

                    if (!resolvedBranch) {
                        def gitBranch = env.GIT_BRANCH?.trim()
                        if (gitBranch?.startsWith('origin/')) {
                            gitBranch = gitBranch.substring('origin/'.length())
                        }
                        resolvedBranch = gitBranch
                    }

                    if (!resolvedBranch) {
                        resolvedBranch = 'develop'
                    }

                    def shortCommit = sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()

                    env.BUILD_BRANCH = resolvedBranch
                    env.SHORT_COMMIT = shortCommit
                    env.IMAGE_TAG = "${resolvedBranch}-${env.BUILD_NUMBER}-${shortCommit}"
                    env.DEPLOY_IMAGE = "${env.LOCAL_IMAGE_NAME}:local"
                    echo "CHANGE_TARGET=${env.CHANGE_TARGET ?: ''}"
                    echo "BRANCH_NAME=${env.BRANCH_NAME ?: ''}"
                    echo "GIT_BRANCH=${env.GIT_BRANCH ?: ''}"
                    echo "Deploy branch resolved from Jenkins context: ${env.BUILD_BRANCH}"
                    echo "Image tag: ${env.IMAGE_TAG}"
                }
            }
        }

        stage('Build API image') {
            steps {
                sh '''#!/usr/bin/env bash
                    set -euo pipefail

                    : "${LOCAL_IMAGE_NAME:?LOCAL_IMAGE_NAME is required}"
                    : "${IMAGE_TAG:?IMAGE_TAG is required}"

                    docker build \
                    --target production \
                    -t "${LOCAL_IMAGE_NAME}:${IMAGE_TAG}" \
                    -t "${LOCAL_IMAGE_NAME}:local" \
                    .
                    '''
            }
        }

        stage('Push image to ECR') {
            when {
                expression { return params.ECR_REGISTRY?.trim() }
            }
            steps {
                script {
                    env.DEPLOY_IMAGE = "${params.ECR_REGISTRY.trim()}/${params.ECR_REPOSITORY.trim()}:${env.IMAGE_TAG}"
                }
                sh '''#!/usr/bin/env bash
                    set -euo pipefail

                    : "${LOCAL_IMAGE_NAME:?LOCAL_IMAGE_NAME is required}"
                    : "${IMAGE_TAG:?IMAGE_TAG is required}"
                    : "${DEPLOY_IMAGE:?DEPLOY_IMAGE is required}"
                    : "${ECR_REGISTRY:?ECR_REGISTRY is required}"

                    aws ecr get-login-password --region "${AWS_REGION}" | \
                    docker login --username AWS --password-stdin "${ECR_REGISTRY}"

                    docker tag "${LOCAL_IMAGE_NAME}:${IMAGE_TAG}" "${DEPLOY_IMAGE}"
                    docker push "${DEPLOY_IMAGE}"
                    '''
            }
        }

        stage('Update deployment checkout') {
            steps {
                sh '''#!/usr/bin/env bash
                    set -euo pipefail

                    : "${DEPLOY_DIR:?DEPLOY_DIR is required}"
                    : "${REPO_URL:?REPO_URL is required}"
                    : "${BUILD_BRANCH:?BUILD_BRANCH is required}"

                    mkdir -p "$(dirname "${DEPLOY_DIR}")"

                    if [ ! -d "${DEPLOY_DIR}/.git" ]; then
                    git clone "${REPO_URL}" "${DEPLOY_DIR}"
                    fi

                    git -C "${DEPLOY_DIR}" fetch --all --prune
                    git -C "${DEPLOY_DIR}" checkout "${BUILD_BRANCH}"
                    git -C "${DEPLOY_DIR}" reset --hard "origin/${BUILD_BRANCH}"
                    '''
            }
        }

        stage('Deploy compose stack') {
            steps {
                sh '''#!/usr/bin/env bash
                    set -euo pipefail

                    : "${DEPLOY_DIR:?DEPLOY_DIR is required}"
                    : "${COMPOSE_FILE:?COMPOSE_FILE is required}"
                    : "${DEPLOY_IMAGE:?DEPLOY_IMAGE is required}"

                    cd "${DEPLOY_DIR}"

                    if [ -n "${ECR_REGISTRY}" ]; then
                    aws ecr get-login-password --region "${AWS_REGION}" | \
                        docker login --username AWS --password-stdin "${ECR_REGISTRY}"
                    API_IMAGE="${DEPLOY_IMAGE}" docker compose -f "${COMPOSE_FILE}" pull api
                    fi

                    API_IMAGE="${DEPLOY_IMAGE}" docker compose -f "${COMPOSE_FILE}" up -d --no-deps --force-recreate api
                    API_IMAGE="${DEPLOY_IMAGE}" docker compose -f "${COMPOSE_FILE}" exec -T api alembic upgrade head
                    API_IMAGE="${DEPLOY_IMAGE}" docker compose -f "${COMPOSE_FILE}" ps api
                    '''
            }
        }
    }

    post {
        success {
            echo "Deployment completed with image ${env.DEPLOY_IMAGE}"
        }
        failure {
            echo 'Deployment failed. Check stage logs for details.'
        }
    }
}
