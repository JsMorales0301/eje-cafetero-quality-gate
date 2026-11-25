// CI pipeline (Scenario 5). Jenkins runs it on every change detected in the repository.
//
// Stages: get the code, prepare the environment, build the image, bring up the two
// containers, run the example operation, verify its result, and always remove everything.
// The verification decides whether the build passes: `pipeline.verify` exits non-zero when
// the result differs from data/sample/expected_fixture.json.
pipeline {
    agent any

    options {
        timestamps()
        disableConcurrentBuilds()
        timeout(time: 20, unit: 'MINUTES')
        buildDiscarder(logRotator(numToKeepStr: '20'))
    }

    triggers {
        // Poll the repository about every 2 minutes. "H" spreads the load across the hour.
        pollSCM('H/2 * * * *')
    }

    parameters {
        string(name: 'CORRUPT', defaultValue: '',
               description: 'Optional, to provoke a failure on purpose: corruption kinds to inject, for example duplicates or nulls,typo_zeros. Leave it empty for a normal build.')
    }

    environment {
        // A Jenkins started as a macOS service does not inherit the shell PATH: add Docker's.
        PATH = "${env.HOME}/.docker/bin:/opt/homebrew/bin:/usr/local/bin:${env.PATH}"
        // One isolated Compose project per build, so it never collides with a developer's
        // containers; the override publishes no host ports.
        COMPOSE_PROJECT_NAME = "ci-${env.BUILD_NUMBER}"
        COMPOSE_FILE = 'docker-compose.yml:docker-compose.ci.yml'
    }

    stages {
        stage('Obtener codigo') {
            steps {
                script { env.CURRENT_STAGE = 'Obtener codigo' }
                checkout scm
                sh 'git log -1 --format="Commit %h: %s"'
                script {
                    def commit = sh(script: 'git rev-parse --short HEAD', returnStdout: true).trim()
                    currentBuild.displayName = "#${env.BUILD_NUMBER} ${commit}"
                }
            }
        }

        stage('Preparar entorno') {
            steps {
                script { env.CURRENT_STAGE = 'Preparar entorno' }
                // The shebang makes Jenkins skip its default `set -x`, so the generated
                // password is never echoed to the build log.
                sh '''#!/bin/bash -e
                    docker --version
                    docker compose version
                    umask 077
                    {
                      echo "POSTGRES_USER=ci"
                      echo "POSTGRES_PASSWORD=$(openssl rand -hex 16)"
                      echo "POSTGRES_DB=canasta"
                      echo "POSTGRES_HOST=db"
                      echo "POSTGRES_PORT=5432"
                      echo "SOCRATA_DATASET_URL=https://www.datos.gov.co/resource/gdqq-rry2.csv"
                    } > .env
                '''
            }
        }

        stage('Construir imagen') {
            steps {
                script { env.CURRENT_STAGE = 'Construir imagen' }
                sh 'docker compose build app'
            }
        }

        stage('Levantar contenedores') {
            steps {
                script { env.CURRENT_STAGE = 'Levantar contenedores' }
                sh 'docker compose up -d --wait'
                sh 'docker compose ps'
            }
        }

        stage('Operacion de ejemplo') {
            steps {
                script {
                    env.CURRENT_STAGE = 'Operacion de ejemplo'
                    def corrupt = (params.CORRUPT ?: '').trim()
                    // Only corruption-kind characters may reach the shell.
                    if (corrupt && !(corrupt ==~ /[a-z_,]+/)) {
                        error("CORRUPT solo admite letras minusculas, guion bajo y comas: '${corrupt}'")
                    }
                    def extra = corrupt ? "--corrupt ${corrupt}" : ''
                    sh "docker compose exec -T app python -m pipeline.run --source fixture ${extra}"
                }
            }
        }

        stage('Verificar resultado') {
            steps {
                script { env.CURRENT_STAGE = 'Verificar resultado' }
                sh 'docker compose exec -T app python -m pipeline.verify'
            }
        }
    }

    post {
        always {
            // Keep the diagnostics, then remove the containers even if the build failed.
            sh '''#!/bin/bash
                docker compose logs --no-color > ci-containers.log 2>&1 || true
                docker compose down -v --remove-orphans || true
                rm -f .env
            '''
            archiveArtifacts artifacts: 'ci-containers.log', allowEmptyArchive: true
        }
        success {
            echo 'CONSTRUCCION EXITOSA: la operacion de ejemplo dio el resultado esperado.'
        }
        failure {
            script {
                currentBuild.description = "Fallo en la etapa: ${env.CURRENT_STAGE}"
                echo "CONSTRUCCION FALLIDA. Fallo en la etapa: ${env.CURRENT_STAGE}"
            }
        }
    }
}
