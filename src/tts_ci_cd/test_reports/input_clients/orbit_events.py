#Python Imports
import logging
from pathlib import Path
import pdb
from datetime import datetime

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class OrbitEventsItem(DataItem):
    DICT_VALID_KEYS = [
                ('Source', str),
                ('Time', datetime),
                ('Event', str),
                ('orbit', int), #TO DO: Fix case
                ('Removed', bool),
                ]

    TIME_FORMATS = {'Time': '%Y/%m/%d %H:%M:%S.%f'}

    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        pass # Must define some way to time-tag each data item

class OrbitEventsClient(InputClient, DataContainer):
    NAME = 'Orbit Events'
    DATA_ITEM_CLS = OrbitEventsItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        DataContainer.__init__(self)

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.oef$')
        begin_found = False
        end_found = False

        records = []
        for line in open(self.filepath, 'r'):
            line = line.strip()
            if not(begin_found):
                if line == 'BEGIN': begin_found = True
            elif end_found:
                pass
            elif line == 'END':
                end_found = True
            else:
                positional_fields = line.split(',')[0:3]
                keyword_fields = line.split(',')[3:]                

                record = {
                    'Source': positional_fields[0],
                    'Time': positional_fields[1],
                    'Event': positional_fields[2]
                }

                for keyword_field in keyword_fields:
                    k, v = keyword_field.split(':')
                    record[k] = v

                record['Removed'] = True if line[0] == '#' else False
                self.append(record, cast_fields=True)


    def _get_run_info(self):
        return {
            'Orbit Events File (.oef)': self.filepath,
        }
