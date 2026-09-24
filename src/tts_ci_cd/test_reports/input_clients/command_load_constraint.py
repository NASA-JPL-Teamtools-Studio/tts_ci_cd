#Python Imports
import logging
from pathlib import Path
import pdb


#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class CommandConstraintItem(DataItem):
    #not actually doing anything with these yet,
    #so these are meaningless here
    DICT_VALID_KEYS = [('vcid', str), ('name', str), ('scet', str), ('Type', str)]
    
    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        return


class ComandLoadConstraintClient(InputClient):
    NAME = 'Command Constraint'
    DATA_ITEM_CLS = CommandConstraintItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.records = []
        self.defalt_time_label = None
        self.time_labels = []
        
    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.ccvr$')

        in_hard_violation_section = False
        in_soft_violation_section = False
        in_other_message_section = False

        hard_violations = []
        soft_violations = []
        other_messages = []
        unexpected_lines = []

        for line in self.filepath.open('r'):
            line = line.strip()
            if line == 'HARD CONSTRAINT VIOLATIONS':
                in_hard_violation_section = True
                in_soft_violation_section = False
                in_other_message_section = False
            elif line == 'SOFT CONSTRAINT VIOLATIONS':
                in_hard_violation_section = False
                in_soft_violation_section = True
                in_other_message_section = False
            elif line == 'OTHER MESSAGES':
                in_hard_violation_section = False
                in_soft_violation_section = False
                in_other_message_section = True
            elif line == '' or set(line) == {'='} or line[0] == '#':
                pass
            elif in_hard_violation_section:
                if line != 'NO VIOLATIONS.': hard_violations.append(line)
            elif in_soft_violation_section:
                if line != 'NO VIOLATIONS.': soft_violations.append(line)
            elif in_other_message_section:
                if line != 'NO MESSAGES.': other_messages.append(line)
            else:
                unexpected_lines.append(line)

        self.hard_violations = hard_violations
        self.soft_violations = soft_violations
        self.other_messages = other_messages
        self.unexpected_lines = unexpected_lines

    def simple_record_table(self, *args, **kwargs):
        #placeholder for breaking tests. One day at a time here...
        return

    def file_contents_as_string(self):
        with open(self.filepath, 'r') as f:
            return f.read()

    def _get_run_info(self):
        return {
            'CCVR': self.filepath.name,
            'Hard Violations Reported by CCVR': str(len(self.hard_violations)),
            'Soft Violations Reported by CCVR': str(len(self.soft_violations)),
            'Unexpected CCVR Messages': str(len(self.other_messages)),
        }