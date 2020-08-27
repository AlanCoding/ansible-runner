import pytest
import pexpect
import subprocess
from ansible_runner.runner_config import RunnerConfig


@pytest.fixture(scope='function')
def rc(request, tmpdir):
    rc = RunnerConfig(str(tmpdir))
    rc.suppress_ansible_output = True
    rc.expect_passwords = {
        pexpect.TIMEOUT: None,
        pexpect.EOF: None
    }
    rc.cwd = str(tmpdir)
    rc.env = {}
    rc.job_timeout = 2
    rc.idle_timeout = 0
    rc.pexpect_timeout = .1
    rc.pexpect_use_poll = True
    return rc


# TODO: determine if we want to add docker / podman
# to zuul instances in order to run these tests
@pytest.fixture(params=['docker', 'podman'], ids=['docker', 'podman'], scope='session')
def container_runtime_available(request, cli):
    try:
        subprocess.run([request.param, '-v'])
        return request.param
    except FileNotFoundError:
        pytest.skip(f'{request.param} runtime not available')


# TODO: determine if we want to add docker / podman
# to zuul instances in order to run these tests
@pytest.fixture(scope="session", autouse=True)
def container_runtime_installed(container_runtime_available):
    import subprocess

    if container_runtime_available:
        for runtime in ('podman', 'docker'):
            try:
                subprocess.run([runtime, '-v'])
                return runtime
            except FileNotFoundError:
                pass
