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
        ECR_REGISTRY = '640168447652.dkr.ecr.ap-southeast-1.amazonaws.com'
        ECR_REPOSITORY = 'bitenex-api'
        REPO_URL = 'https://github.com/vietviet08/bitenex-api.git'
        DEPLOY_DIR = '/opt/bitenex/repo'
        COMPOSE_FILE = 'docker-compose.prod.yml'
        AWS_REGION = 'ap-southeast-1'
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
                    def repoUrl = params.REPO_URL?.trim() ?: env.REPO_URL
                    def deployDir = params.DEPLOY_DIR?.trim() ?: env.DEPLOY_DIR
                    def composeFile = params.COMPOSE_FILE?.trim() ?: env.COMPOSE_FILE
                    def awsRegion = params.AWS_REGION?.trim() ?: env.AWS_REGION
                    def ecrRegistry = params.ECR_REGISTRY?.trim() ?: env.ECR_REGISTRY
                    def ecrRepository = params.ECR_REPOSITORY?.trim() ?: env.ECR_REPOSITORY
                    def imageTag = "${resolvedBranch}-${env.BUILD_NUMBER}-${shortCommit}"
                    def deployImage = ecrRegistry ? "${ecrRegistry}/${ecrRepository}:${imageTag}" : "${env.LOCAL_IMAGE_NAME}:local"

                    echo "CHANGE_TARGET=${env.CHANGE_TARGET ?: ''}"
                    echo "BRANCH_NAME=${env.BRANCH_NAME ?: ''}"
                    echo "GIT_BRANCH=${env.GIT_BRANCH ?: ''}"
                    echo "Deploy branch resolved from Jenkins context: ${resolvedBranch}"
                    echo "Image tag: ${imageTag}"
                    echo "AWS region: ${awsRegion}"
                    echo "ECR registry: ${ecrRegistry ?: '(disabled)'}"
                    echo "ECR repository: ${ecrRepository}"

                    writeFile file: '.jenkins-build.env', text: """LOCAL_IMAGE_NAME=${env.LOCAL_IMAGE_NAME}
BUILD_BRANCH=${resolvedBranch}
SHORT_COMMIT=${shortCommit}
IMAGE_TAG=${imageTag}
DEPLOY_IMAGE=${deployImage}
REPO_URL=${repoUrl}
DEPLOY_DIR=${deployDir}
COMPOSE_FILE=${composeFile}
AWS_REGION=${awsRegion}
ECR_REGISTRY=${ecrRegistry}
ECR_REPOSITORY=${ecrRepository}
"""
                }
            }
        }

        stage('Build API image') {
            steps {
                sh '''#!/usr/bin/env bash
                    set -euo pipefail
                    set -a
                    . ./.jenkins-build.env
                    set +a

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
            steps {
                sh '''#!/usr/bin/env bash
                    set -euo pipefail
                    set -a
                    . ./.jenkins-build.env
                    set +a

                    : "${LOCAL_IMAGE_NAME:?LOCAL_IMAGE_NAME is required}"
                    : "${IMAGE_TAG:?IMAGE_TAG is required}"
                    : "${DEPLOY_IMAGE:?DEPLOY_IMAGE is required}"

                    if [ -z "${ECR_REGISTRY}" ]; then
                        echo "ECR registry is disabled. Skipping image push."
                        exit 0
                    fi

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
                    set -a
                    . ./.jenkins-build.env
                    set +a
                    umask 0002

                    : "${DEPLOY_DIR:?DEPLOY_DIR is required}"
                    : "${REPO_URL:?REPO_URL is required}"
                    : "${BUILD_BRANCH:?BUILD_BRANCH is required}"

                    mkdir -p "$(dirname "${DEPLOY_DIR}")"
                    git config --global --add safe.directory "${DEPLOY_DIR}"

                    if [ ! -d "${DEPLOY_DIR}/.git" ]; then
                    git clone "${REPO_URL}" "${DEPLOY_DIR}"
                    fi

                    git -C "${DEPLOY_DIR}" config core.sharedRepository group
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
                    set -a
                    . ./.jenkins-build.env
                    set +a

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
            script {
                def deployImage = 'bitenex-api:local'
                if (fileExists('.jenkins-build.env')) {
                    def metadata = readProperties text: readFile('.jenkins-build.env')
                    deployImage = metadata.DEPLOY_IMAGE ?: deployImage
                }
                echo "Deployment completed with image ${deployImage}"
            }
        }
        failure {
            echo 'Deployment failed. Check stage logs for details.'
        }
    }
}
