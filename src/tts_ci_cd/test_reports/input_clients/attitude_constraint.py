#Python Imports
import logging
from pathlib import Path
import re
import pdb

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

#This class is not super necessary, but it's a bit of
#a load bearing poster at the moment...
class AttitudeConstraintViolation:
    def __init__(self):
        self.rule_id = None
        self.message = None
        self.defalt_time_label = None
        self.time_labels = []

class AttitudeConstraintItem(DataItem):
    DICT_VALID_KEYS = [('Level', str), ('Rule ID', str), ('Message', str)]
    TIME_FORMATS = {}

    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        pass # Must define some way to time-tag each data item


class AttitudeConstraintClient(InputClient, DataContainer):
    NAME = 'Attitude Constraint'
    DATA_ITEM_CLS = AttitudeConstraintItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.records = []   
        self.hard_attitude_constraint_violations = []
        self.soft_attitude_constraint_violations = []
        self.other_messages = []
        self.filepath = None
        self.time_labels = {}
        DataContainer.__init__(self)

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.acvr$')

        hard_constraints_found = False
        hard_constraints_active = False
        soft_constraints_found = False
        soft_constraints_active = False
        other_messages_found = False
        other_messages_active = False
        out_of_order_violation = False

        first_line_pattern = r'(OCO-\S{2,3}-\d+):\s*(.*)$'
        subsequent_line_pattern = r'\s*(\S.*)$'

        for line in open(self.filepath, 'r'):
            line = line.strip()
            if sum([x == '=' for x in line]) == len(line) or line == '':
                continue
            if line[0] == '#':
                continue
            elif line == 'HARD CONSTRAINT VIOLATIONS':
                hard_constraints_found = True
                hard_constraints_active = True
                if soft_constraints_found or other_messages_found:
                    raise Exception(f'HARD CONSTRAINT VIOLATIONS is not the first section in {self.filepath}')
                continue
            elif line == 'SOFT CONSTRAINT VIOLATIONS':
                hard_constraints_active = False
                soft_constraints_found = True
                soft_constraints_active = True
                if other_messages_found:
                    raise Exception(f'SOFT CONSTRAINT VIOLATIONS is not the second section in {self.filepath}')
                continue
            elif line == 'OTHER MESSAGES':
                soft_constraints_active = False
                other_messages_found = True
                other_messages_active = True
                continue

            first_line_match = re.findall(first_line_pattern, line, re.DOTALL)
            subsequent_line_match = re.findall(subsequent_line_pattern, line, re.DOTALL)
            if first_line_match:
                new_attitude_constraint_violation = AttitudeConstraintViolation()
                new_attitude_constraint_violation.rule_id = first_line_match[0][0]
                new_attitude_constraint_violation.message = first_line_match[0][1]
                if hard_constraints_active:
                    self.hard_attitude_constraint_violations.append(new_attitude_constraint_violation)
                elif soft_constraints_active:
                    self.soft_attitude_constraint_violations.append(new_attitude_constraint_violation)
                elif other_messages_active:
                    self.other_messages.append(new_attitude_constraint_violation)
                    raise NotImplementedError('OTHER MESSAGES not yet implemented.')
            elif subsequent_line_match:
                if hard_constraints_active and len(self.hard_attitude_constraint_violations) != 0:
                    self.hard_attitude_constraint_violations[-1].message += f' {subsequent_line_match[0]}'
                elif soft_constraints_active and len(self.soft_attitude_constraint_violations) != 0:
                    self.soft_attitude_constraint_violations[-1].message += f' {subsequent_line_match[0]}'
                elif other_messages_active:
                    if subsequent_line_match[0] != 'NO MESSAGES.':
                        self.other_messages.append(new_attitude_constraint_violation)
                        raise NotImplementedError('OTHER MESSAGES not yet implemented.')
            else:
                raise Exception(f'How did I get here? {line}')

        if not hard_constraints_found:
            raise Exception(f'No HARD CONSTRAINT VIOLATIONS section found in {self.filepath}')
        if not soft_constraints_found:
            raise Exception(f'No SOFT CONSTRAINT VIOLATIONS section found in {self.filepath}')
        if not other_messages_found:
            raise Exception(f'No OTHER MESSAGES section found in {self.filepath}')
        
        for hard_attitude_constraint_violation in self.hard_attitude_constraint_violations:
            self.append({
                    'Level': 'Hard', 
                    'Rule ID': hard_attitude_constraint_violation.rule_id,
                    'Message': hard_attitude_constraint_violation.message},
                )
        for soft_attitude_constraint_violation in self.soft_attitude_constraint_violations:
            self.append({
                    'Level': 'Soft', 
                    'Rule ID': soft_attitude_constraint_violation.rule_id,
                    'Message': soft_attitude_constraint_violation.message},
                )

    def file_contents_as_string(self):
        with open(self.filepath, 'r') as f:
            return f.read()


    def _get_run_info(self):
        return {
            'ACVR': self.filepath.name,
            'Hard Violations Reported by ACVR': str(len(self.hard_attitude_constraint_violations)),
            'Soft Violations Reported by ACVR': str(len(self.soft_attitude_constraint_violations)),
            'Unexpected ACVR Messages': str(len(self.other_messages)),
            'X-band Sun Pointing Hard Violations': 'See Violation Table tab',
        }