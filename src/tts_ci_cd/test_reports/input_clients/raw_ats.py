#Python Imports
import logging
from pathlib import Path
import pdb
import pandas as pd
from datetime import datetime
from copy import copy
import re 

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.rule_results import RuleResults
from tts_tower.inputs.input_client import InputClient


log = logging.getLogger(__name__)

class RawAtsItem(DataItem):
    DICT_VALID_KEYS = [
        ('Time', datetime),
        ('Raw Command', str)
        ]

    TIME_FORMATS = {
        'Time': '%y/%m:%d:%H:%M:%S',
    }
    
    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        return

class RawAtsClient(InputClient, DataContainer):
    NAME = 'Raw ATS'
    DATA_ITEM_CLS = RawAtsItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.records = []
        self.defalt_time_label = 'Time'
        self.time_labels = [{'name': 'Time', 'format': '%y/%m:%d:%H:%M:%S'}]
        DataContainer.__init__(self)
        self.metadata = {} #overwrite DC's base metadata attr

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.scr$')
        time_pattern = r'\$TIME=([^\s]+)'

        for line in open(self.filepath, 'r'):
            line = line.strip()
            if line[0] == ';':
                line = line[1:]
                try:
                    k, v = line.split(':')
                except ValueError:
                    continue
                try:
                    self.metadata[k.strip()] = v.strip()
                except:
                    pdb.set_trace()
            else:
                match = re.search(time_pattern, line)
                if not match: continue
                time = match.group(1)
                self.append({'Time': time, 'Raw Command': line}, cast_fields=True)
        # self.record_times_to_datetime()
    def _get_run_info(self):
        return {
            'SCR File Under Review': self.filepath.name,
            'Plan Period Start': self.metadata.get('Plan period start', 'UNKNOWN'),
            'Plan Period End': self.metadata.get('Plan period stop', 'UNKNOWN')
        }