#Python imports
import logging
from pathlib import Path
import pdb
from datetime import datetime
from copy import copy

#JPL Imports
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

#This Library Imports
from tts_tower.rule_results import RuleResults
from tts_tower.inputs.input_client import InputClient

log = logging.getLogger(__name__)

class AbsoluteCommandItem(DataItem):
    #not actually doing anything with these yet,
    #so these are meaningless here
    DICT_VALID_KEYS = [('Purpose', str), ('Time', datetime), ('Built by', str), ('Command', str), ('Orbit', int)]
    TIME_FORMATS = {
        'Time': '%Y/%m/%d %H:%M:%S.%f'
        }

    @property
    def default_html_row_style(self):
        return {}

    @property
    def time(self):
        pass # Must define some way to time-tag each data item

class AbsoluteCommandClient(InputClient, DataContainer):
    NAME = 'Expanded ATS'
    DATA_ITEM_CLS = AbsoluteCommandItem

    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.snap_version = None
        self.abs_format = None
        self.records = []
        self.time_labels = [
            {'name': 'Time', 'format': '%Y/%m/%d %H:%M:%S.%f'}, 
            ]
        DataContainer.__init__(self)

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.abs$', multiple_behavior='LAST_ALPHA')
        begin_found = False
        end_found = False
        record = None
        metadata_dict = {}            
        last_purpose = None
        if self.filepath is None:
            log.warning('No ABS path found.')
            return

        for line in open(self.filepath, 'r'):
            line = line.strip()
            if line == '': 
                metadata_dict = {}
                continue

            if self.abs_format is None:
                #we care about comment lines below for
                #metadata reasons, but before FORMAT
                #they don't matter, so ignore them
                if line[0] == '#':
                    continue
                elif line.startswith('FORMAT'):
                    self.abs_format = line.split()[-1]
            else:
                pass
            if end_found:
                break
            elif not(begin_found):
                if line == 'BEGIN': begin_found = True
            elif end_found:
                pass
            elif line == 'END':
                end_found = True
            elif line.startswith('#'):
                k, v = [x.strip() for x in line.replace('#','').split(':',1)]
                if k in [x['name'] for x in self.time_labels]:
                    metadata_dict[f'{k} (commented metadata)'] = v
                else:
                    metadata_dict[k] = v

                if 'SNAP' in v:
                    if self.snap_version is None and self.snap_version != v:
                        self.snap_version = v
                    else:
                        raise Exception('Conflicting SNAP versions found!')
            elif line.startswith('20'): 
                #this elif feels hacky. It should be fine because the mission will end
                #before the year 2100, but still...
                time_string, remainder = line.split('|')
                command, comment = remainder.split(';')
                record = copy(metadata_dict)
                #TO DO: Handle time better
                record['Time'] = time_string.strip()
                record['Command'] = command.strip()
                record['Comment'] = comment.strip()
                self.append(record, cast_fields=True, fill=True)
            elif line == '':
                pass
            else:
                raise Exception('Unexpected line in ABS file.')


        if self.snap_version is None:
            log.warning('SNAP version does not appear in ABS file. This is OK if this ABS was not made by SNAP')

    def file_contents_as_string(self):
        with open(self.filepath, 'r') as f:
            return f.read()

    def _get_run_info(self):
        door_open_cmd_orbits = [x.split()[-1] for x in self.contains('Purpose', 'Open Door post-TR contacts for Glint Collection Orbit')['Purpose']]
        nadir_cmd_orbits = [x.split()[-1] for x in self.contains('Purpose', 'Add Nadir CMD prior to TR Orbit')['Purpose']]

        return {
            'Absolute Command File (.abs)': self.filepath,
            'Nadir Commands added via ABS': ', '.join(nadir_cmd_orbits), 
            'Post-TR Door Open Commands added via ABS': ', '.join(door_open_cmd_orbits),
            'SNAP Version (.abs)': self.snap_version,
            'SNAP Format (.abs)': self.abs_format
        }


