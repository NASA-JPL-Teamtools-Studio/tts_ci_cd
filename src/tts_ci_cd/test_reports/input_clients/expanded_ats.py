#Python Imports
import logging
from pathlib import Path
import pdb
import pandas as pd
from datetime import datetime
from copy import copy

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.rule_results import RuleResults
from tts_tower.inputs.input_client import InputClient

log = logging.getLogger(__name__)

class ExpandedAtsItem(DataItem):
    DICT_VALID_KEYS = [
        ('Line #', (int, None)),
        ('Orbit #', int),
        ('Time (UTC)', datetime),
        ('Time (GPS)', datetime),
        ('Event Type', str),
        ('command', str),
        ('command note', str),
        ('ACS Mode', str),
        ('Instrument Mode', str),
        ('Door Position', str),
        ('Lamp Status', str),
        ('in_sun', bool) #TO DO: Fix case on this
        ]

    TIME_FORMATS = {
        'Time (UTC)': '%Y-%m-%dT%H:%M:%S.%fZ',
        'Time (GPS)': '%Y-%m-%dT%H:%M:%S.%fG',
    }
    
    @property
    def default_html_row_style(self):
        #TO DO: forcing white/black here
        #overrides the even/odd shading
        #that comes out of the box, and I don't like
        #that.
        #TO DO: Make this more efficient. Lots of
        #duplicate code here.
        text_color = 'black'
        bg_color = 'white'
        if self.values['Event Type'] == 'OEF':
            text_color = 'white'
            bg_color = 'black'
        elif 'timeout' in self.values['Event Type']:
            bg_color = '#FFDD44'
        elif 'Macro' in self.values['Event Type']:
            bg_color = '#DFA8A9'
        elif 'RTS' in self.values['Event Type']:
            bg_color = '#B9CFED'
        elif self.values['Event Type'] == 'CAF':
            bg_color = '#B5FFA8'
        elif self.values['Event Type'] == 'SBW':
            bg_color = '#6082B6'
            text_color = 'white'
        elif self.values['command note'] in [f'Predicted {x}OS' for x in ['L','A']]:
            bg_color = '#6D9E3E'
            text_color = 'white'
        elif 'TSM' in self.values['Event Type']:
            bg_color = '#F8C8D3'
        elif self.values['Event Type'] == 'ABS':
            bg_color = '#66B2FF'
        elif self.values['Event Type'] == 'LNR':
            bg_color = '#FF9900'

        return {'color': text_color, 'background-color': bg_color}

    @property
    def default_rich_text_row_style(self):
        rich_text_stype = self.default_html_row_style
        rich_text_stype['shading'] = rich_text_stype['background-color']
        del rich_text_stype['background-color']
        rich_text_stype['size'] = 8
        return rich_text_stype

    @property
    def time(self):
        return
    
class ExpandedAtsClient(InputClient, DataContainer):
    NAME = 'Expanded ATS'
    DATA_ITEM_CLS = ExpandedAtsItem

    def _impl_init(self, week_dir_client, odf_client, ats_under_review):
        self.args = (week_dir_client)
        self.kwargs = {}

        self.week_dir_client = week_dir_client
        self.odf_client = odf_client
        self.ats_under_review = ats_under_review
        self.filepath = None
        self._default_time_label = 'Time (UTC)'
        self.time_labels = [
            {'name': 'Time (UTC)', 'format': '%Y-%m-%dT%H:%M:%S.%fZ'}, 
            {'name': 'Time (GPS)', 'format': '%Y-%m-%dT%H:%M:%S.%fG'}
            ]
        self._repr_cols = ['Line #', 'Orbit #', 'Time (UTC)', 'Time (GPS)', 'Event Type', 'command', 'command note', 'ACS Mode', 'Instrument Mode', 'Door Position', 'Lamp Status', 'in_sun']
        self.records = []
        DataContainer.__init__(self)

    @property
    def repr_cols(self):
        return self._repr_cols

    @property
    def default_time_label(self):
        return self._default_time_label

    
    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_expanded_ats_path()
        df = pd.read_csv(self.filepath, delimiter='\t')
        expected_columns = ['Line #', 'Orbit #', 'Time (UTC)', 'Time (GPS)', 'Event Type','command', 'command note', 'ACS Mode', 'Instrument Mode','Door Position', 'Lamp Status']
        if list(df.columns) != expected_columns:
            raise ValueError(f'Columns in {self.filepath} are not as expected.')
        records = df.fillna('').to_dict('records')

        #What? I thought we were trying to get rid of this style of filter!
        #Well... this one is still here because I need access to this filter
        #before we append any records to self
        #TO DO: Invent column extension and do it that way instead
        first_eclipse_record = [r for r in records if 'Eclipse' in r['command note']][0]
        in_sun = False if 'Exit' in first_eclipse_record['command note'] else False
        for record in records:
            if 'Exit' in record['command note']:
                in_sun = True
            elif 'Entry' in record['command note']:
                in_sun = False
            else:
                pass
            record['in_sun'] = in_sun

        self.append(records, cast_fields=True)

    def _get_run_info(self):

        
        if self.ats_under_review:
            targets_removed = []
            target_removal_records = self.contains('command note', 'Target removed')
            orbits_with_removed_targets = target_removal_records.unique('Orbit #')
            orbits_with_removed_targets.sort()
            
            for orbit in orbits_with_removed_targets:
                target = self.odf_client.eq('Absolute Orbit #', orbit, exactly=1)['Target']
                targets_removed.append(f'{orbit} -- {target}')
            targets_removed = '<br \>'.join(targets_removed)
            orbits = self.unique('Orbit #')
            orbits.sort()
            orbit_range = f'{orbits[0]} to {orbits[-1]}',
        else:
            orbit_range = 'UNKNOWN'
            targets_removed = 'UNKNOWN'
        
        return {
            'Expanded ATS File': self.filepath,
            'Orbit Range': orbit_range,
            'Targets Removed for Glint Violations': targets_removed
        }

    def get_x_band_orbits(self, records=None):
        return self.contains('command note', 'AOS RTS - X band only').unique('Orbit #')

    def get_s_band_orbits(self, records=None):
        #example s band orbit: https://nephthys.jpl.nasa.gov/cal_reports/ATS/2025_01_16/sub_pages/orbit_56084.html
        return self.contains('command note', 'AOS RTS - S band only').unique('Orbit #')

    def get_alaska_orbits(self, records=None):
        return self.contains('command note', 'AOS at AS').unique('Orbit #')

    def get_trollsat_orbits(self, records=None):
        return self.contains('command note', 'AOS at TR').unique('Orbit #')

    def get_burn_orbits(self, records=None):
        return self.contains('ACS Mode', 'THRUST').unique('Orbit #')

    def get_glint_orbits(self, records=None):        
        return self.contains('ACS Mode', 'GLINT').unique('Orbit #')
