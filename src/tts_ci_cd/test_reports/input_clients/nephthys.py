import logging
from pathlib import Path
import pdb
import pandas as pd
from datetime import datetime
import re

from tts_tower.inputs.input_client import InputClient
from tts_tower.rule_results import RuleResults

from tts_html_utils.core.components.misc import Link

log = logging.getLogger(__name__)

class NephthysClient(InputClient):
    def _impl_init(self, planning_week):
        self.planning_week = planning_week
        self.base_url = f'https://nephthys.jpl.nasa.gov/cal_reports/ATS/{self.planning_week}/'
        self.planning_datestring = re.match(r"[0-9]{4}_[0-9]{2}_[0-9]{2}", self.planning_week)[0]
        self.lunar_cal_times_path = Path(__file__).parent.parent.joinpath('support_files/oco2_predicted_lunar_cals.csv')
        self.lunar_cal_times = pd.read_csv(self.lunar_cal_times_path, header=None)

        lunar_cals_in_future = [
            datetime.strptime(j.values[0], '%Y-%m-%dT%H:%M:%S.%fZ') for i, j in self.lunar_cal_times.iterrows() 
            if (datetime.strptime(j.values[0], '%Y-%m-%dT%H:%M:%S.%fZ') - datetime.strptime(self.planning_datestring, '%Y_%m_%d')).total_seconds() > 0
            ]
        lunar_cals_in_future.sort()
        self.next_lunar_cal = lunar_cals_in_future[0]
        self.default_time_label = None
        self.time_labels = []

    def _impl_populate(self):
        return

    def _get_run_info(self):
        return {
            'Nephthys Link': Link(self.base_url),
            'Next Lunar Calibration': self.next_lunar_cal,
        }

    def get_orbit_sub_page_link(self, orbit):
        return f'{self.base_url}sub_pages/orbit_{orbit}.html'

    def get_orbit_sub_page_anchor(self, orbit, display_text=None, new_tab=True):
        if display_text is None: display_text = orbit
        target_string = ' target="_blank" ' if new_tab else ''
        return f'<a href="{self.get_orbit_sub_page_link(orbit)}"{target_string}>{display_text}</a>'

    def get_compare_sequences_page_link(self, orbit):
        return f'{self.base_url}ATS_compare_{orbit}.html'

    def get_compare_sequences_page_anchor(self, orbit, display_text=None, new_tab=True):
        href = {self.get_compare_sequences_page_link(orbit)}
        if display_text is None: display_text = href
        target_string = ' target="_blank" ' if new_tab else ''
        return f'<a href="{href}"{target_string}>{display_text}</a>'

    def get_raw_file_link(self, filename):
        return f'{self.base_url}raw_files/{filename}'

    def get_ats_report_link(self):
        return f'{self.base_url}index.html'

    def get_sun_violations_anchor(self):
        return f'{self.base_url}/index.html#contacts'

    def get_ats_report_anchor(self, display_text=None, new_tab=True):
        href = {self.get_ats_report_link()}
        if display_text is None: display_text = href
        target_string = ' target="_blank" ' if new_tab else ''
        return f'<a href="{href}"{target_string}>{display_text}</a>'
