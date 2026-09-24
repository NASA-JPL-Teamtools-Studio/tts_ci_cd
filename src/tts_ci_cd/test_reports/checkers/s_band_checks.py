import pdb
from datetime import datetime

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.text import Paragraph
from tts_html_utils.core.components.text import Heading2 as H2

# ===================================================================
# :: Checker Class
# ===================================================================
class CheckerCheckXBand(CheckerBase):
    FR_IDS = [
        ('TEL-026', '3ef6ed76'),
    ]

    INPUTS = [
        ('expanded_ats', True),
        ('nephthys', True)
    ]
    NAME = 'S Band Checks'

    def _impl_init(self, expanded_ats_client, nephthys_client):
        pass

    def _impl_do_rulecheck(self, expanded_ats_client, nephthys_client):
        self.expanded_ats_client = expanded_ats_client
        s_band_orbits = expanded_ats_client.get_s_band_orbits()
        if len(s_band_orbits):
            for s_band_orbit in s_band_orbits:
                xats_this_orbit = expanded_ats_client.eq('Orbit #', s_band_orbit)
                self.check_rule_tel_026(s_band_orbit)
        else:
            self.get_rule('TEL-026').add_status_dispo('FLAGGED', f'No S-Band contacts in ATS. That seems wrong.')

    def check_rule_tel_026(self, s_band_orbit):
        xats_this_orbit = self.expanded_ats_client.eq('Orbit #', s_band_orbit)

        if len(xats_this_orbit.contains('command note', 'Begin target')):
            self.get_rule('TEL-026').add_status_dispo('FLAGGED', f'Target is scheduled on S-band orbit #{s_band_orbit}')
        else:
            self.get_rule('TEL-026').add_status_dispo('PASSED', f'S-band orbit #{s_band_orbit} has no target')


