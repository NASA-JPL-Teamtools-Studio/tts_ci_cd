import logging
from pathlib import Path
import pdb
import re
from lxml import html
import pandas as pd
from io import StringIO

from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class ViolationTableItem(DataItem):
    #not actually doing anything with these yet,
    #so these are meaningless here
    DICT_VALID_KEYS = [
        ('Violation ID*', str),
        ('Violation Type', str),
        ('Start Time', str),
        ('Duration', str),
        ('Worst Case Value', str),
        ('Orbit Number', int),
        ('Type', str),
        ]
    
    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        return
    

class ViolationsTableClient(InputClient, DataContainer):
    NAME = 'Nephthys Violations Table'
    DATA_ITEM_CLS = ViolationTableItem

    def _impl_init(self, week_dir_client, ignore_ext=None):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.raw_violations_table = None
        self.records = []
        self.defalt_time_label = None
        self.time_labels = []
        self.violation_id_label = 'Violation ID*'
        self.violation_map = {
            'Hard Violations': 'Hard',
            'X-band Sun Pointing Hard Violations': 'X-band Hard',
            'Soft Violations': 'Soft',
            'Glint Violations': 'Glint',
            'Star Tracker Hard Violations': 'Star Tracker Hard'
            }
        self.expected_columns = [
            'Violation ID*', 
            'Violation Type', 
            'Start Time', 
            'Duration', 
            'Worst Case Value', 
            'Orbit Number'
            ]
        DataContainer.__init__(self)

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*index\.html$', multiple_behavior='UNIQUE')

        with self.filepath.open('r', encoding='utf-8') as file:
            tree = html.fromstring(file.read())
        tables = tree.xpath('//table')

        #what is this doing? Depending on how many tables get generated in Nephthys (usually due to no ABS)
        #we don't know exactly which table the violations table will be.
        #so we search through until we find it and break when we do
        #if we never find it violation_table_found stays False and the exception is raised
  
        violation_table_found = False
        for table_number in range(len(tables)):
            self.raw_violations_table = pd.read_html(StringIO(html.tostring(tables[table_number], encoding='unicode')), header=1)[0].fillna('NA')
            
            #self.raw_violations_table.columns gets wrapped in a list comprehension
            #because we want it to be the same datatype as self.expected_columns
            #and for some reason list() wasn't working
            if [x for x in self.raw_violations_table.columns] == self.expected_columns:
                violation_table_found = True
                break
            #in older versions of this report, there's no * on the first column name
            if [x for x in self.raw_violations_table.columns] == [x.replace('*','') for x in self.expected_columns]:
                violation_table_found = True
                self.violation_id_label = 'Violation ID'
                break

        if not violation_table_found:
            raise Exception('Violation table columns don\'t match expected.')

        current_violation_type = None
        for _, row in self.raw_violations_table.iterrows(): 
            if row[self.violation_id_label].replace('*','') in self.violation_map.keys(): 
                current_violation_type = self.violation_map[row[self.violation_id_label].replace('*','')]
            else:
                this_violation = row.to_dict()
                this_violation['Type'] = current_violation_type
                self.append(this_violation, cast_fields=True)

    def _get_run_info(self):
        n_hard = len(self.eq('Type', 'Hard'))
        n_soft = len(self.eq('Type', 'Soft'))
        n_glint = len(self.eq('Type', 'Glint'))
        n_xband = len(self.eq('Type', 'X-band Hard'))
        n_total = len(self)
        all_violations_found = n_total == n_hard + n_soft + n_glint + n_xband

        return {
            'Hard Violations Reported by ART': str(n_hard) if all_violations_found else f'{str(n_hard)} reported, but total does not match! See violation tab FMI.',
            'Soft Violations Reported by ART': str(n_soft) if all_violations_found else f'{str(n_soft)} reported, but total does not match! See violation tab FMI.',
            'Glint Violations Reported by ART': str(n_glint) if all_violations_found else f'{str(n_glint)} reported, but total does not match! See violation tab FMI.',
            'X-Band Violations Reported by ART': str(n_xband) if all_violations_found else f'{str(n_xband)} reported, but total does not match! See violation tab FMI.',
            'Total Violations Reported by ART': str(n_total),
            'OCO-AC-004 (Sun within 80 deg cone of radiator)': 'See ACVR tab' if len( self.eq(self.violation_id_label, 'OCO-AC-004')) else 'No Violations',
            'OCO-AC-006 (Earth within 34.5 deg of star tracker)': 'See ACVR tab' if len( self.eq(self.violation_id_label, 'OCO-AC-006')) else 'No Violations',
            'OCO-AC-007 (Sun within 34.5 deg of star tracker)':  'See ACVR tab' if len( self.eq(self.violation_id_label, 'OCO-AC-007')) else 'No Violations',
            'OCO-AC-008 (Sun within 25 deg cone of instrument)': 'See ACVR tab' if len( self.eq(self.violation_id_label, 'OCO-AC-008')) else 'No Violations',
            'OCO-AC-010 (Glint Spot is within 2.50 degrees cone angle of instrument)':  'See ACVR tab' if len( self.eq(self.violation_id_label, 'OCO-AC-010')) else 'No Violations',
        }

