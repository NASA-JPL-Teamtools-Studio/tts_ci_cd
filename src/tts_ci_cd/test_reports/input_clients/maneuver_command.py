import logging
from pathlib import Path
import pdb
from datetime import datetime

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

log = logging.getLogger(__name__)

class ManeuverCommandClient(InputClient):
    def _impl_init(self, week_dir_client):
        self.week_dir_client = week_dir_client
        self.filepath = None
        self.default_time_label = None
        self.time_labels = []

    def _impl_populate(self):
        self.filepath = self.week_dir_client.get_file_paths_by_regex(r'.*\.mnvr$', required=False)
        if self.filepath is not None: 
            self.maneuver_parameters = {}
            for line in self.filepath.open('r'):
                if line.startswith('#'): continue
                line = line.strip()
                k, v = line.split('=')
                self.maneuver_parameters[k.strip()] = v.strip()
            self.maneuver_parameters['MAN_START'] = datetime.strptime(self.maneuver_parameters['MAN_START'], '%Y/%m/%d %H:%M:%S.%f')
            self.maneuver_parameters['MAN_STOP'] = datetime.strptime(self.maneuver_parameters['MAN_STOP'], '%Y/%m/%d %H:%M:%S.%f')
            self.maneuver_parameters['MAN_DUR_S'] = (self.maneuver_parameters['MAN_STOP'] - self.maneuver_parameters['MAN_START']).total_seconds()

    def _get_run_info(self):
        return {
            'ManeuverCommandClient(InputClient) Info': self.filepath,
        }