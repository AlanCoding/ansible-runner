# Copyright (c) 2016 Ansible by Red Hat, Inc.
#
# This file is part of Ansible Tower, but depends on code imported from Ansible.
#
# Ansible is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# Ansible is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with Ansible.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import (absolute_import, division, print_function)

# Python
import base64
import contextlib
import datetime
import json
import multiprocessing
import io
import os
import stat
import threading
import uuid

__all__ = ['event_context']


class EventContext(object):
    '''
    Store global and local (per thread/process) data associated with callback
    events and other display output methods.
    '''

    def __init__(self):
        self.display_lock = multiprocessing.RLock()
        self._local = threading.local()

    def add_local(self, **kwargs):
        tls = vars(self._local)
        ctx = tls.setdefault('_ctx', {})
        ctx.update(kwargs)

    def remove_local(self, **kwargs):
        for key in kwargs.keys():
            self._local._ctx.pop(key, None)

    @contextlib.contextmanager
    def set_local(self, **kwargs):
        try:
            self.add_local(**kwargs)
            yield
        finally:
            self.remove_local(**kwargs)

    def get_local(self):
        return getattr(getattr(self, '_local', None), '_ctx', {})

    def add_global(self, **kwargs):
        if not hasattr(self, '_global_ctx'):
            self._global_ctx = {}
        self._global_ctx.update(kwargs)

    def remove_global(self, **kwargs):
        if hasattr(self, '_global_ctx'):
            for key in kwargs.keys():
                self._global_ctx.pop(key, None)

    @contextlib.contextmanager
    def set_global(self, **kwargs):
        try:
            self.add_global(**kwargs)
            yield
        finally:
            self.remove_global(**kwargs)

    def get_global(self):
        return getattr(self, '_global_ctx', {})

    def get(self):
        ctx = {}
        ctx.update(self.get_global())
        ctx.update(self.get_local())
        return ctx

    def get_begin_dict(self):
        event_data = self.get()
        # TODO: Need to rework these values
        if os.getenv('JOB_ID', ''):
            event_data['job_id'] = int(os.getenv('JOB_ID', '0'))
        if os.getenv('AD_HOC_COMMAND_ID', ''):
            event_data['ad_hoc_command_id'] = int(os.getenv('AD_HOC_COMMAND_ID', '0'))
        if os.getenv('PROJECT_UPDATE_ID', ''):
            event_data['project_update_id'] = int(os.getenv('PROJECT_UPDATE_ID', '0'))
        event_data.setdefault('pid', os.getpid())
        event_data.setdefault('uuid', str(uuid.uuid4()))
        event_data.setdefault('created', datetime.datetime.utcnow().isoformat())
        if not event_data.get('parent_uuid', None):
            for key in ('task_uuid', 'play_uuid', 'playbook_uuid'):
                parent_uuid = event_data.get(key, None)
                if parent_uuid and parent_uuid != event_data.get('uuid', None):
                    event_data['parent_uuid'] = parent_uuid
                    break

        event = event_data.pop('event', None)
        if not event:
            event = 'verbose'
            for key in ('debug', 'verbose', 'deprecated', 'warning', 'system_warning', 'error'):
                if event_data.get(key, False):
                    event = key
                    break
        max_res = int(os.getenv("MAX_EVENT_RES", 700000))
        if event not in ('playbook_on_stats',) and "res" in event_data and len(str(event_data['res'])) > max_res:
            event_data['res'] = {}
        event_dict = dict(event=event, event_data=event_data)
        for key in list(event_data.keys()):
            if key in ('job_id', 'ad_hoc_command_id', 'project_update_id', 'uuid', 'parent_uuid', 'created',):
                event_dict[key] = event_data.pop(key)
            elif key in ('verbosity', 'pid'):
                event_dict[key] = event_data[key]
        return event_dict

    def get_end_dict(self):
        return {}

    def dump(self, fileobj, data, max_width=1024):
        b64data = base64.b64encode(json.dumps(data).encode('utf-8')).decode()
        with self.display_lock:
            # pattern corresponding to OutputEventFilter expectation
            fileobj.write(u'\x1b[K')
            for offset in range(0, len(b64data), max_width):
                chunk = b64data[offset:offset + max_width]
                escaped_chunk = u'{}\x1b[{}D'.format(chunk, len(chunk))
                fileobj.write(escaped_chunk)
            fileobj.write(u'\x1b[K')
            fileobj.flush()

    def dump_begin(self, fileobj):
        self.dump(fileobj, self.get_begin_dict())

    def dump_end(self, fileobj):
        self.dump(fileobj, self.get_end_dict())


event_context = EventContext()
