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
        DEPLOY_IMAGE = ''
        IMAGE_TAG = ''
        SHORT_COMMIT = ''
        BUILD_BRANCH = ''
    }

    stages {
        stage('Checkout') {
            steps {
                checkout scm
                script {
                    env.BUILD_BRANCH = (
                        env.CHANGE_TARGET?.trim() ?:
                        env.BRANCH_NAME?.trim() ?:
                        env.GIT_BRANCH?.replaceFirst(/^origin\\//, '')?.trim() ?:
                        'develop'
                    )
                    env.SHORT_COMMIT = sh(script: 'git rev-parse --short=7 HEAD', returnStdout: true).trim()
                    env.IMAGE_TAG = "${env.BUILD_BRANCH}-${env.BUILD_NUMBER}-${env.SHORT_COMMIT}"
                    env.DEPLOY_IMAGE = "${env.LOCAL_IMAGE_NAME}:local"
                    echo "Deploy branch resolved from Jenkins context: ${env.BUILD_BRANCH}"
                }
            }
        }

        stage('Build API image') {
            steps {
                sh '''#!/usr/bin/env bash
                    set -euo pipefail

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
