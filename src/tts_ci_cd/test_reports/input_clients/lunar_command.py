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

class LunarCommandItem(DataItem):
    DICT_VALID_KEYS = [
        ('Time (GPS)', datetime),
        ('Command', str),
        ('Command Note', str)
        ]

    TIME_FORMATS = {
        'Time (GPS)': '%Y/%m/%d %H:%M:%S.%f',
    }
    
    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        return
class LunarCommandClient(InputClient, DataContainer):
    NAME = 'NG Lunar Command File'
    DATA_ITEM_CLS = LunarCommandItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self._default_time_label = 'Time (GPS)'
        self.time_labels = []
        self.comments = []
        DataContainer.__init__(self)

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.lnr$', required=False)
        if self.filepath is None: return
        
        for line in self.filepath.open('r'):
            line = line.strip()
            if line in ['', 'FORMAT MIXED', 'BEGIN', 'END']: 
                continue
            elif line[0] == '#':
                self.comments.append(line)
            else:
                splitline = line.split('|')
                if len(splitline) == 2: 
                    self.comments.append(line)
                    continue
                time, _, command_and_comment = splitline
                command, comment = command_and_comment.split(';')
                self.append({
                        'Time (GPS)': time.strip(),
                        'Command': command.strip(),
                        'Command Note': comment.strip(),
                    }, cast_fields=True)

    def _get_run_info(self):
        return {
            'Lunar Command File': self.filepath,
        }