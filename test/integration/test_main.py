# -*- coding: utf-8 -*-
from __future__ import print_function
from ansible_runner.__main__ import main

import os
import codecs
import multiprocessing
import shutil
import yaml
import tempfile
import time
from contextlib import contextmanager
import pytest


from ansible_runner.exceptions import AnsibleRunnerException


def ensure_directory(directory):
    if not os.path.exists(directory):
        os.makedirs(directory)


def ensure_removed(path):
    if os.path.exists(path):
        if os.path.isfile(path):
            os.unlink(path)
        elif os.path.isdir(path):
            shutil.rmtree(path)


@contextmanager
def temp_directory(files=None):
    temp_dir = tempfile.mkdtemp()
    print(temp_dir)
    try:
        yield temp_dir
        shutil.rmtree(temp_dir)
    except BaseException:
        if files is not None:
            for file in files:
                if os.path.exists(file):
                    with open(file) as f:
                        print(f.read())
        raise


def test_temp_directory():

    context = dict()


    def will_fail():
        with temp_directory() as temp_dir:
            context['saved_temp_dir'] = temp_dir
            assert False

    def will_pass():
        with temp_directory() as temp_dir:
            context['saved_temp_dir'] = temp_dir
            assert True

    with pytest.raises(AssertionError):
        will_fail()
    assert os.path.exists(context['saved_temp_dir'])
    shutil.rmtree(context['saved_temp_dir'])

    will_pass()
    assert not os.path.exists(context['saved_temp_dir'])


def test_help():
    with pytest.raises(SystemExit) as exc:
        main([])
    assert exc.value.code == 2, 'Should raise SystemExit with return code 2'


def test_module_run():
    try:
        rc = main(['run', '-m', 'ping',
                   '--hosts', 'localhost',
                   'ping'])
        assert os.path.exists('./ping')
        assert os.path.exists('./ping/artifacts')
        assert rc == 0
    finally:
        if os.path.exists('./ping'):
            shutil.rmtree('./ping')


def test_module_run_debug():
    try:
        rc = main(['run', '-m', 'ping',
                   '--hosts', 'localhost',
                   '--debug',
                   'ping'])
        assert os.path.exists('./ping')
        assert os.path.exists('./ping/artifacts')
        assert rc == 0
    finally:
        if os.path.exists('./ping'):
            shutil.rmtree('./ping')


@pytest.mark.serial
def test_module_run_clean():
    with temp_directory() as temp_dir:
        rc = main(['run', '-m', 'ping',
                   '--hosts', 'localhost',
                   temp_dir])
    assert rc == 0


def test_role_run(skipif_pre_ansible28, test_data_dir):
    rc = main(['run', '-r', 'benthomasson.hello_role',
               '--hosts', 'localhost',
               '--roles-path', 'test/integration/roles',
               os.path.join(test_data_dir, 'misc')])
    assert rc == 0
    ensure_removed("test/integration/artifacts")


def test_role_run_abs(test_data_dir):
    with temp_directory() as temp_dir:
        rc = main(['run', '-r', 'benthomasson.hello_role',
                   '--hosts', 'localhost',
                   '--roles-path', os.path.join(test_data_dir, 'misc', 'project/roles'),
                   os.path.join(test_data_dir, 'misc')])
    assert rc == 0


def test_role_logfile(skipif_pre_ansible28, test_data_dir):
    try:
        rc = main(['run', '-r', 'benthomasson.hello_role',
                   '--hosts', 'localhost',
                   '--roles-path', 'test/integration/project/roles',
                   '--logfile', 'new_logfile',
                   os.path.join(test_data_dir, 'misc')])
        assert os.path.exists('new_logfile')
        assert rc == 0
    finally:
        ensure_removed(os.path.join(test_data_dir, 'misc', 'artifacts'))


def test_role_logfile_abs(test_data_dir):
    try:
        with temp_directory() as temp_dir:
            rc = main(['run', '-r', 'benthomasson.hello_role',
                       '--hosts', 'localhost',
                       '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                       '--logfile', 'new_logfile',
                       temp_dir])
        assert os.path.exists('new_logfile')
        assert rc == 0
    finally:
        ensure_removed("new_logfile")


def test_role_bad_project_dir(test_data_dir):

    with open("bad_project_dir", 'w') as f:
        f.write('not a directory')

    try:
        with pytest.raises(OSError):
            main(['run', '-r', 'benthomasson.hello_role',
                  '--hosts', 'localhost',
                  '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                  '--logfile', 'new_logfile',
                  'bad_project_dir'])
    finally:
        os.unlink('bad_project_dir')
        ensure_removed("new_logfile")


@pytest.mark.serial
def test_role_run_clean(skipif_pre_ansible28, test_data_dir):

    rc = main(['run', '-r', 'benthomasson.hello_role',
               '--hosts', 'localhost',
               '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
               os.path.join(test_data_dir, 'misc')])
    assert rc == 0
    ensure_removed(os.path.join(test_data_dir, 'misc', 'artifacts'))


def test_role_run_cmd_line_abs(test_data_dir):
    with temp_directory() as temp_dir:
        rc = main(['run', '-r', 'benthomasson.hello_role',
                   '--hosts', 'localhost',
                   '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles',
                   temp_dir])
    assert rc == 0


def test_role_run_artifacts_dir(skipif_pre_ansible28, test_data_dir):
    rc = main(['run', '-r', 'benthomasson.hello_role',
               '--hosts', 'localhost',
               '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
               '--artifact-dir', 'otherartifacts',
               os.path.join(test_data_dir, 'misc')])
    assert rc == 0
    ensure_removed(os.path.join(test_data_dir, 'misc', 'artifacts'))


def test_role_run_artifacts_dir_abs(skipif_pre_ansible28, test_data_dir):
    try:
        with temp_directory() as temp_dir:
            rc = main(['run', '-r', 'benthomasson.hello_role',
                       '--hosts', 'localhost',
                       '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                       '--artifact-dir', 'otherartifacts',
                       temp_dir])
        assert os.path.exists(os.path.join('.', 'otherartifacts'))
        assert rc == 0
    finally:
        shutil.rmtree(os.path.join('.', 'otherartifacts'))


@pytest.mark.parametrize('envvars', [
    {'msg': 'hi'},
    {
        'msg': u'utf-8-䉪ቒ칸ⱷ?噂폄蔆㪗輥',
        u'蔆㪗輥': u'䉪ቒ칸'
    }],
    ids=['regular-text', 'utf-8-text']
)
def test_role_run_env_vars(envvars, test_data_dir):

    with temp_directory() as temp_dir:
        ensure_directory(os.path.join(temp_dir, 'env'))
        with codecs.open(os.path.join(temp_dir, 'env/envvars'), 'w', encoding='utf-8') as f:
            f.write(yaml.dump(envvars))

        rc = main(['run', '-r', 'benthomasson.hello_role',
                   '--hosts', 'localhost',
                   '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                   temp_dir])
    assert rc == 0


def test_role_run_args(test_data_dir):

    with temp_directory() as temp_dir:
        rc = main(['run', '-r', 'benthomasson.hello_role',
                   '--hosts', 'localhost',
                   '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                   '--role-vars', 'msg=hi',
                   temp_dir])
    assert rc == 0


def test_role_run_inventory(is_pre_ansible28, test_data_dir):

    inv = 'inventory/localhost_preansible28' if is_pre_ansible28 else 'inventory/localhost'
    with temp_directory() as temp_dir:
        ensure_directory(os.path.join(temp_dir, 'inventory'))
        shutil.copy(
            os.path.join(test_data_dir, 'misc', 'inventory', 'localhost'),
            os.path.join(temp_dir, 'inventory/localhost'))

        rc = main(['run', '-r', 'benthomasson.hello_role',
                   '--hosts', 'localhost',
                   '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                   '--inventory', 'localhost',
                   temp_dir])
    assert rc == 0


def test_role_run_inventory_missing(is_pre_ansible28, test_data_dir):

    inv = 'inventory/localhost_preansible28' if is_pre_ansible28 else 'inventory/localhost'
    with temp_directory() as temp_dir:
        ensure_directory(os.path.join(temp_dir, 'inventory'))
        shutil.copy(
            os.path.join(test_data_dir, 'misc', 'inventory/localhost'),
            os.path.join(temp_dir, 'inventory/localhost'))

        with pytest.raises(AnsibleRunnerException):
            main(['run', '-r', 'benthomasson.hello_role',
                  '--hosts', 'localhost',
                  '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                  '--inventory', 'does_not_exist',
                  temp_dir])


def test_role_start(test_data_dir):


    with temp_directory() as temp_dir:
        p = multiprocessing.Process(target=main,
                                    args=[['start', '-r', 'benthomasson.hello_role',
                                           '--hosts', 'localhost',
                                           '--roles-path', os.path.join(test_data_dir, 'misc', 'project', 'roles'),
                                           temp_dir]])
        p.start()
        p.join()


@pytest.mark.serial
def test_playbook_start(skipif_pre_ansible28, test_data_dir):
    data_dir = os.path.join(test_data_dir, 'misc')

    inv = 'inventory/localhost'
    with temp_directory() as temp_dir:
        project_dir = os.path.join(temp_dir, 'project')
        ensure_directory(project_dir)
        shutil.copy(os.path.join(data_dir, 'project/hello.yml'), project_dir)
        ensure_directory(os.path.join(temp_dir, 'inventory'))
        shutil.copy(os.path.join(data_dir, 'inventory/localhost'), os.path.join(temp_dir, 'inventory/localhost'))

        # privateip: removed --hosts command line option from test beause it is
        # not a supported combination of cli options
        p = multiprocessing.Process(target=main,
                                    args=[['-p', 'hello.yml',
                                           '--inventory', os.path.join(data_dir, 'inventory/localhost'),
                                           #'--hosts', 'localhost',
                                           temp_dir]])
        p.start()


        time.sleep(5)

        assert os.path.exists(os.path.join(temp_dir, 'pid'))

        rc = main(['is-alive', temp_dir])
        assert rc == 0
        rc = main(['stop', temp_dir])
        assert rc == 0

        time.sleep(1)

        rc = main(['is-alive', temp_dir])
        assert rc == 1

        ensure_removed(os.path.join(temp_dir, 'pid'))

        rc = main(['stop', temp_dir])
    assert rc == 1
