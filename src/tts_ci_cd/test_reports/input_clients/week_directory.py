import logging
from pathlib import Path
import pdb
import re

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults
from tts_data_utils.core.data_container import DataContainer
from tts_data_utils.core.data_container import DataItem

log = logging.getLogger(__name__)

class WeekDirectoryItem(DataItem):
    #not actually doing anything with these yet,
    #so these are meaningless here
    DICT_VALID_KEYS = [('path', str)]

    @property
    def time(self):
        return
    
    @property
    def default_html_row_style(self):
        return {}


class WeekDirectoryClient(InputClient, DataContainer):
    NAME = 'Week Directory'
    DATA_ITEM_CLS = WeekDirectoryItem

    def _impl_init(self, week_directory, output_path=None, ignore_ext=None, ignore_prefix=None, planning_week=None):
        self.week_directory = Path(week_directory).resolve()
        self.output_path = output_path
        self.planning_week = self.week_directory.name if planning_week is None else planning_week
        self.ignore_ext = ignore_ext if ignore_ext is not None else ['h5', 'png', 'DS_Store']
        self.ignore_prefix = ignore_prefix if ignore_prefix is not None else ['._']
        self.records = []
        self.time_labels = []
        self.defalt_time_label = None
        self._repr_cols = []
        self._default_time_label = None
        DataContainer.__init__(self)

    @property
    def repr_cols(self):
        return self._repr_cols

    @property
    def default_time_label(self):
        return self._default_time_label

    def _impl_populate(self):
        self.file_paths = [str(file) for file in Path(self.week_directory).rglob('*') if file.is_file()]
        #yes, file_paths and records are redundant here
        #I'm in the middle of swapping things out
        self.file_paths = [x for x in self.file_paths if x.split('.')[-1] not in self.ignore_ext]
        records = [{'path', f} for f in self.file_paths]
        for ignore_prefix in self.ignore_prefix:
            self.file_paths = [x for x in self.file_paths if not Path(x).name.startswith(ignore_prefix)]
            records = [{'path': f} for f in self.file_paths if not Path(f).name.startswith(ignore_prefix)]
        self.append(records)

    def _get_run_info(self):
        return {
            'Patch ATS Directory': f'/groups/MOS/ATS/{self.planning_week}',
            'Switch Buffer': 'S switch buffer now ()'
        }

    def get_expanded_ats_path(self):
        ats_regex = fr'ATS_{self.planning_week}.txt$'
        return self.get_file_paths_by_regex(ats_regex, multiple_behavior='UNIQUE', required=True)

    def get_file_paths_by_regex(self, pattern, multiple_behavior='LAST_ALPHA', required=False):
        # to do: make a warning if multiples found for now
        regex = re.compile(pattern)
        matching_paths = [file_path for file_path in self.file_paths if regex.search(str(file_path)) is not None]
        if len(matching_paths) == 0 and required:
            raise ValueError(f'No files found matching regex pattern "{pattern}"')
        elif len(matching_paths) == 0:
            return None
        elif multiple_behavior.upper() == 'FIRST_ALPHA':
            matching_paths.sort()
            return Path(matching_paths[0])
        elif multiple_behavior.upper() == 'LAST_ALPHA':
            matching_paths.sort(reverse=True)
            return Path(matching_paths[0])
        elif multiple_behavior.upper() == 'ALL':
            return [Path(x) for x in matching_paths]
        elif multiple_behavior.upper() == 'UNIQUE':
            if len(matching_paths) == 1:
                return Path(matching_paths[0])
            else:
                raise ValueError(f'Found {len(matching_paths)} file(s) matching regex pattern "{pattern}" in {self.week_directory}, but this pattern should be unique among files searched.')
        else:
            raise ValueError(f'Found {len(matching_paths)} file(s) matching regex pattern "{pattern}" in {self.week_directory}, but I don\'t know what to do with multiple_behavior of "{multiple_behavior}"')