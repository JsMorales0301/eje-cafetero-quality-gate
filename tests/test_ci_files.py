"""Structural checks on the CI files. Jenkins itself runs the Jenkinsfile; these tests keep the
properties the delivery depends on from regressing silently (they do not execute Groovy)."""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
JENKINSFILE = ROOT / "Jenkinsfile"
CI_COMPOSE = ROOT / "docker-compose.ci.yml"

STAGES = ["Obtener codigo", "Preparar entorno", "Construir imagen", "Levantar contenedores",
          "Operacion de ejemplo", "Verificar resultado"]


@pytest.fixture(scope="module")
def jenkinsfile() -> str:
    return JENKINSFILE.read_text(encoding="utf-8")


def _post_always(text: str) -> str:
    start = text.index("post {")
    return text[start:]


def test_the_required_stages_exist_in_order(jenkinsfile):
    positions = [jenkinsfile.index(f"stage('{name}')") for name in STAGES]
    assert positions == sorted(positions)


def test_verification_comes_after_the_example_operation(jenkinsfile):
    assert jenkinsfile.index("stage('Operacion de ejemplo')") < jenkinsfile.index(
        "stage('Verificar resultado')")


def test_verification_runs_the_command_that_decides_the_result(jenkinsfile):
    assert "python -m pipeline.verify" in jenkinsfile
    assert "python -m pipeline.run --source fixture" in jenkinsfile


def test_each_stage_records_its_name_so_a_failure_can_say_where_it_happened(jenkinsfile):
    for name in STAGES:
        assert f"env.CURRENT_STAGE = '{name}'" in jenkinsfile
    assert "Fallo en la etapa: ${env.CURRENT_STAGE}" in jenkinsfile


def test_the_repository_is_polled_automatically(jenkinsfile):
    assert re.search(r"pollSCM\('[^']+'\)", jenkinsfile)


def test_containers_are_removed_even_when_the_build_fails(jenkinsfile):
    post = _post_always(jenkinsfile)
    always = post[post.index("always {"):post.index("success {")]
    assert "docker compose down -v" in always
    assert "rm -f .env" in always


def test_it_uses_sh_because_the_jenkins_machine_is_macos(jenkinsfile):
    assert "sh '" in jenkinsfile or 'sh "' in jenkinsfile
    assert not re.search(r"\bbat\s*['\"]", jenkinsfile)


def test_no_secret_is_written_in_the_repository(jenkinsfile):
    for line in jenkinsfile.splitlines():
        if "POSTGRES_PASSWORD" in line:
            assert "openssl rand" in line, f"a password must be generated, not written: {line}"
    assert "withCredentials" not in jenkinsfile  # nothing needs a stored credential


def test_the_generated_password_is_never_echoed_to_the_log(jenkinsfile):
    block = jenkinsfile[jenkinsfile.index("stage('Preparar entorno')"):]
    block = block[:block.index("stage('Construir imagen')")]
    script = block[block.index("sh '''"):]  # the shell script itself, not the comments around it
    assert script.startswith("sh '''#!/bin/bash -e")  # a shebang disables Jenkins' default `set -x`
    assert "set -x" not in script and "set -o xtrace" not in script


def test_each_build_gets_its_own_isolated_compose_project(jenkinsfile):
    assert "COMPOSE_PROJECT_NAME = \"ci-${env.BUILD_NUMBER}\"" in jenkinsfile
    assert "docker-compose.ci.yml" in jenkinsfile


def test_docker_is_found_even_though_a_macos_service_has_a_minimal_path(jenkinsfile):
    assert ".docker/bin" in jenkinsfile


def test_a_failure_can_be_provoked_on_purpose_with_a_validated_parameter(jenkinsfile):
    assert "string(name: 'CORRUPT'" in jenkinsfile
    assert "==~ /[a-z_,]+/" in jenkinsfile  # only corruption-kind characters reach the shell


def test_the_ci_override_publishes_no_host_ports():
    text = CI_COMPOSE.read_text(encoding="utf-8")
    assert "ports: !reset []" in text
    assert text.count("ports: !reset []") == 2  # one for db, one for app


def test_build_logs_and_the_generated_env_are_not_committed():
    ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()
    assert ".env" in ignored and "ci-containers.log" in ignored
