#Python Imports
import logging
from pathlib import Path
import pandas as pd
import pdb
from datetime import datetime

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults



log = logging.getLogger(__name__)

class OrbitDesignationItem(DataItem):
    DICT_VALID_KEYS = [
                ('Day', int),
                ('OCO-2 Reference Ground Path', int),
                ('Orbit', int),
                ('Target', str),
                ('Absolute Orbit #', int),
                ('Floating Dark Offset', str),
                ('Calibration Mode', str),
                ('Science Mode', str)
                ]

    TIME_FORMATS = {}

    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        pass # Must define some way to time-tag each data item


class OrbitDesignationClient(InputClient, DataContainer):
    NAME = 'Orbit Designation'
    DATA_ITEM_CLS = OrbitDesignationItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.time_labels = []
        DataContainer.__init__(self)

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.odf$')
        found_column_headers = False
        expected_column_headers = [
                    'Day', 
                    'OCO-2 Reference Ground Path', 
                    'Orbit',
                    'Target', 
                    'Absolute Orbit #', 
                    'Floating Dark Offset', 
                    'Calibration Mode', 
                    'Science Mode'
                    ]
        for line in open(self.filepath, 'r'):
            if '# Column Headers: ' in line:
                found_column_headers = True
                column_headers = [x.strip() for x in line.replace('# Column Headers:  ', '').split(',')]
        if not found_column_headers:
            raise ValueError('No column headers found!')
        elif column_headers != expected_column_headers:
            raise ValueError('Headers found don\'t match expected!')

        df = pd.read_csv(self.filepath, header=None, names=column_headers, comment='#').fillna('')
        self.append(df.to_dict('records'), cast_fields=True)

    def _get_run_info(self):
        return {
            'Orbit Designation File (.odf)': self.filepath,
        }

