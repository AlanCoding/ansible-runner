import pytest
import tempfile
from distutils.spawn import find_executable
import json
import os
import shutil

from ansible_runner import run, run_async


@pytest.mark.serial
@pytest.mark.parametrize('containerized', [True, False])
def test_basic_events(containerized, container_runtime_available, is_pre_ansible28, is_run_async=False, g_facts=False):
    if containerized and not container_runtime_available:
        pytest.skip('container runtime(s) not available')
    tdir = tempfile.mkdtemp()

    if is_pre_ansible28:
        inventory = 'localhost ansible_connection=local ansible_python_interpreter="/usr/bin/env python"'
    else:
        inventory = 'localhost ansible_connection=local'

    playbook = [{'hosts': 'all', 'gather_facts': g_facts, 'tasks': [{'debug': {'msg': "test"}}]}]
    run_args = {'private_data_dir': tdir,
                'inventory': inventory,
                'envvars': {"ANSIBLE_DEPRECATION_WARNINGS": "False", 'ANSIBLE_PYTHON_INTERPRETER': 'auto_silent'},
                'playbook': playbook}
    if containerized:
        run_args.update({'process_isolation': True,
                         'process_isolation_executable': 'podman',
                         'container_image': 'localhost/ansible/ansible-runner',
                         'container_volume_mounts': [f'{tdir}:{tdir}']})

    if not is_run_async:
        r = run(**run_args)
    else:
        thread, r = run_async(**run_args)
        thread.join()  # ensure async run finishes

    event_types = [x['event'] for x in r.events if x['event'] != 'verbose']
    okay_events = [x for x in filter(lambda x: 'event' in x and x['event'] == 'runner_on_ok',
                                     r.events)]

    assert event_types[0] == 'playbook_on_start'
    assert "playbook_on_play_start" in event_types
    assert "runner_on_ok" in event_types
    assert "playbook_on_stats" in event_types
    assert r.rc == 0
    if not is_run_async:
        assert len(okay_events) == 1
    else:
        assert len(okay_events) == 2

    okay_event = okay_events[0]
    assert "uuid" in okay_event and len(okay_event['uuid']) == 36
    assert "parent_uuid" in okay_event and len(okay_event['parent_uuid']) == 36
    assert "stdout" in okay_event and len(okay_event['stdout']) > 0
    assert "start_line" in okay_event and int(okay_event['start_line']) > 0
    assert "end_line" in okay_event and int(okay_event['end_line']) > 0
    assert "event_data" in okay_event and len(okay_event['event_data']) > 0


@pytest.mark.serial
@pytest.mark.parametrize('containerized', [True, False])
def test_async_events(containerized, container_runtime_available, is_pre_ansible28):
    test_basic_events(containerized, container_runtime_available, is_pre_ansible28, is_run_async=True,g_facts=True)


def test_basic_serializeable(is_pre_ansible28):
    tdir = tempfile.mkdtemp()
    if is_pre_ansible28:
        inv = 'localhost ansible_connection=local ansible_python_interpreter="/usr/bin/env python"'
    else:
        inv = 'localhost ansible_connection=local'
    r = run(private_data_dir=tdir,
            inventory=inv,
            playbook=[{'hosts': 'all', 'gather_facts': False, 'tasks': [{'debug': {'msg': "test"}}]}])
    events = [x for x in r.events]
    json.dumps(events)


def test_event_omission(is_pre_ansible28):
    tdir = tempfile.mkdtemp()
    if is_pre_ansible28:
        inv = 'localhost ansible_connection=local ansible_python_interpreter="/usr/bin/env python"'
    else:
        inv = 'localhost ansible_connection=local'
    r = run(private_data_dir=tdir,
            inventory=inv,
            omit_event_data=True,
            playbook=[{'hosts': 'all', 'gather_facts': False, 'tasks': [{'debug': {'msg': "test"}}]}])
    assert not any([x['event_data'] for x in r.events])


def test_event_omission_except_failed(is_pre_ansible28):
    tdir = tempfile.mkdtemp()
    if is_pre_ansible28:
        inv = 'localhost ansible_connection=local ansible_python_interpreter="/usr/bin/env python"'
    else:
        inv = 'localhost ansible_connection=local'
    r = run(private_data_dir=tdir,
            inventory=inv,
            only_failed_event_data=True,
            playbook=[{'hosts': 'all', 'gather_facts': False, 'tasks': [{'fail': {'msg': "test"}}]}])
    all_event_datas = [x['event_data'] for x in r.events if x['event_data']]
    assert len(all_event_datas) == 1


def test_runner_on_start(rc, skipif_pre_ansible28):
    tdir = tempfile.mkdtemp()
    r = run(private_data_dir=tdir,
            inventory="localhost ansible_connection=local",
            playbook=[{'hosts': 'all', 'gather_facts': False, 'tasks': [{'debug': {'msg': "test"}}]}])
    start_events = [x for x in filter(lambda x: 'event' in x and x['event'] == 'runner_on_start',
                                      r.events)]
    assert len(start_events) == 1


def test_playbook_on_stats_summary_fields(rc, is_pre_ansible28):
    if is_pre_ansible28:
        inv = 'localhost ansible_connection=local ansible_python_interpreter="/usr/bin/env python"'
    else:
        inv = 'localhost ansible_connection=local'
    tdir = tempfile.mkdtemp()
    r = run(private_data_dir=tdir,
            inventory=inv,
            playbook=[{'hosts': 'all', 'gather_facts': False, 'tasks': [{'debug': {'msg': "test"}}]}])
    stats_events = [x for x in filter(lambda x: 'event' in x and x['event'] == 'playbook_on_stats',
                                      r.events)]
    assert len(stats_events) == 1

    EXPECTED_SUMMARY_FIELDS = ('changed', 'dark', 'failures', 'ignored', 'ok', 'rescued', 'skipped')
    fields = stats_events[0]['event_data'].keys()
    assert set(fields) >= set(EXPECTED_SUMMARY_FIELDS)


@pytest.mark.serial
def test_include_role_events(test_data_dir):
    data_dir = os.path.join(test_data_dir, 'misc')
    try:
        r = run(
            private_data_dir=data_dir,
            playbook='use_role.yml'
        )
        role_events = [event for event in r.events if event.get('event_data', {}).get('role', '') == "benthomasson.hello_role"]
        assert 'runner_on_ok' in [event['event'] for event in role_events]
        for event in role_events:
            event_data = event['event_data']
            assert not event_data.get('warning', False)  # role use should not contain warnings
            if event['event'] == 'runner_on_ok':
                assert event_data['res']['msg'] == 'Hello world!'
    finally:
        shutil.rmtree(os.path.join(data_dir, 'artifacts'))


def test_use_aggregate_callback(data_directory):
    data_dir = os.path.join(data_directory, 'aggregate_callback')
    try:
        r = run(
            private_data_dir=data_dir,
            playbook='debug.yml'
        )
        stdout = '\n'.join([event['stdout'] for event in r.events])
        assert 'ready_set_play_start' in stdout
        assert 'ready_set_on_ok' in stdout
    finally:
        shutil.rmtree(os.path.join(data_dir, 'artifacts'))


def test_hide_skipped_tasks(data_directory):
    data_dir = os.path.join(data_directory, 'callback_options')
    try:
        r = run(private_data_dir=data_dir, playbook='task_status.yml')
        stdout = '\n'.join([event['stdout'] for event in r.events])
        # skipped tasks should not be shown
        assert 'skipping:' not in stdout
    finally:
        shutil.rmtree(os.path.join(data_dir, 'artifacts'))


def test_use_display_callback(data_directory):
    data_dir = os.path.join(data_directory, 'display_callback')
    try:
        r = run(private_data_dir=data_dir, playbook='task_status.yml')
        stdout = '\n'.join([event['stdout'] for event in r.events])
        # the task names should not be displayed in output (due to use of "selective" callback)
        assert 'Use debug task to produce different status for several hosts' not in stdout
        # callback should print stuff in blue color too
        assert '\u001b' in stdout or '\x1b' in stdout
    finally:
        shutil.rmtree(os.path.join(data_dir, 'artifacts'))


def test_use_display_callback_with_option(data_directory):
    data_dir = os.path.join(data_directory, 'display_callback_options')
    try:
        r = run(private_data_dir=data_dir, playbook='task_status.yml')
        # with this option set, callback should not print anything in blue color
        stdout = '\n'.join([event['stdout'] for event in r.events])
        assert 'Use debug task to produce different status for several hosts' not in stdout
        assert '\u001b' not in stdout and '\x1b' not in stdout
    finally:
        shutil.rmtree(os.path.join(data_dir, 'artifacts'))



@pytest.mark.skipif(find_executable('cgexec') is None,
                    reason="cgexec not available")
def test_profile_data(skipif_pre_ansible28):
    tdir = tempfile.mkdtemp()
    try:
        r = run(private_data_dir=tdir,
                inventory="localhost ansible_connection=local",
                resource_profiling=True,
                resource_profiling_base_cgroup='ansible-runner',
                playbook=[{'hosts': 'all', 'gather_facts': False, 'tasks': [{'debug': {'msg': "test"}}]}])
        assert r.config.env['ANSIBLE_CALLBACK_WHITELIST'] == 'cgroup_perf_recap'
        assert r.config.env['CGROUP_CONTROL_GROUP'].startswith('ansible-runner/')
        expected_datadir = os.path.join(tdir, 'profiling_data')
        assert r.config.env['CGROUP_OUTPUT_DIR'] == expected_datadir
        assert r.config.env['CGROUP_OUTPUT_FORMAT'] == 'json'
        assert r.config.env['CGROUP_CPU_POLL_INTERVAL'] == '0.25'
        assert r.config.env['CGROUP_MEMORY_POLL_INTERVAL'] == '0.25'
        assert r.config.env['CGROUP_PID_POLL_INTERVAL'] == '0.25'
        assert r.config.env['CGROUP_FILE_PER_TASK'] == 'True'
        assert r.config.env['CGROUP_WRITE_FILES'] == 'True'
        assert r.config.env['CGROUP_DISPLAY_RECAP'] == 'False'

        data_files = [f for f in os.listdir(expected_datadir)
                      if os.path.isfile(os.path.join(expected_datadir, f))]
        # Ensure each type of metric is represented in the results
        for metric in ('cpu', 'memory', 'pids'):
            assert len([f for f in data_files if '{}.json'.format(metric) in f]) == 1

        # Ensure each file consists of a list of json dicts
        for file in data_files:
            with open(os.path.join(expected_datadir, file)) as f:
                for line in f:
                    line = line[1:-1]  # strip RS and LF (see https://tools.ietf.org/html/rfc7464#section-2.2)
                    try:
                        json.loads(line)
                    except json.JSONDecodeError as e:
                        pytest.fail("Failed to parse {}: '{}'"
                                    .format(os.path.join(expected_datadir, file), e))

    except RuntimeError:
        pytest.skip(
            'this test requires a cgroup to run e.g., '
            'sudo cgcreate -a `whoami` -t `whoami` -g cpuacct,memory,pids:ansible-runner'
        )  # noqa
