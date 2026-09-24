import pdb
from datetime import datetime, timedelta
from copy import deepcopy
import pytest

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.text import Paragraph
from tts_html_utils.core.components.text import Heading1 as H1
from tts_html_utils.core.components.text import Heading2 as H2

# ===================================================================
# :: Checker Class
# ===================================================================
class CheckerMisc(CheckerBase):
    FR_IDS = [
        ('GEN-008', '3ef6ed76'),
        ('GEN-009', '3ef6ed76'),
        ('GEN-010', '3ef6ed76'),
        ('GEN-011', 'a3ac6e33'),
        ('INST-002', '3ef6ed76'),
        ('INST-003', '3ef6ed76'),
		('INST-005', 'd10fbb64'),
    ]

    INPUTS = [
        ('expanded_ats', True),
        ('oef', True),
        ('scr', True),
    ]

    def _impl_init(self, expanded_ats_client, oef_client, raw_ats_client):
        pass

    def _impl_do_rulecheck(self, expanded_ats_client, oef_client, raw_ats_client):
        self.expanded_ats_client = expanded_ats_client
        self.oef_client = oef_client
        self.raw_ats_client = raw_ats_client
        for orbit in self.oef_client.unique('orbit'):
            oef_this_orbit = self.oef_client.eq('orbit', orbit)
            target_starts = oef_this_orbit.eq('Event', 'TargetVisibleStart')
            target_stops = oef_this_orbit.eq('Event', 'TargetVisibleStop')
            commented_target_starts = target_starts.eq('Removed', True)
            commented_target_stops = target_stops.eq('Removed', True)

            self.check_rule_gen_008(commented_target_starts, commented_target_stops, orbit)
            self.check_rule_gen_009(commented_target_starts, commented_target_stops, orbit)

        # These rules get checked against the whole xats, so it's outside the orbit loop
        self.check_rule_gen_010()
        self.check_rule_gen_011()
        # self.check_rule_inst_002()
        # self.check_rule_inst_003()
        self.check_rule_inst_005()

    def check_rule_gen_008(self, commented_target_starts, commented_target_stops, orbit):
        if commented_target_starts + commented_target_stops:
            targets_this_orbit = self.expanded_ats_client.contains('command note', 'Begin target').eq('Orbit #', orbit)
            if len(targets_this_orbit):
                self.get_rule('GEN-008').add_status_dispo('VIOLATING', f'Target removed from OEF on orbit {orbit}, but still exists in expanded ATS.')
            else:
                self.get_rule('GEN-008').add_status_dispo('PASSED', f'Target removed from OEF on orbit {orbit}, and does not exist in expanded ATS.')
        else:
            self.get_rule('GEN-008').add_status_dispo('PASSED', f'No targets removed from OEF on orbit {orbit}. Cannot violate rule.')

    def check_rule_gen_009(self, commented_target_starts, commented_target_stops, orbit):        
        if commented_target_starts + commented_target_stops:
            targets_started = [e['targetID'] for e in commented_target_starts]
            targets_stopped = [e['targetID'] for e in commented_target_stops]
            targets_started_not_stopped = [t for t in targets_started if t not in targets_stopped]
            targets_stopped_not_started = [t for t in targets_stopped if t not in targets_started]

            if len(targets_started_not_stopped):
                for t in targets_started_not_stopped:
                    self.get_rule('GEN-009').add_status_dispo('VIOLATING', f'Start for target {t} removed from OEF on orbit {orbit}, but its stop is still present.')
            if len(targets_stopped_not_started):
                for t in targets_stopped_not_started:
                    self.get_rule('GEN-009').add_status_dispo('VIOLATING', f'Stop for target {t} removed from OEF on orbit {orbit}, but its start is still present.')
            if len(targets_started_not_stopped + targets_stopped_not_started) == 0:
                for t in targets_started:
                    self.get_rule('GEN-009').add_status_dispo('PASSED', f'Start and stop for target {t} both removed from OEF on orbit {orbit}.')
        else:
            self.get_rule('GEN-009').add_status_dispo('PASSED', f'No targets removed from OEF on orbit {orbit}. Cannot violate rule.')

    def check_rule_gen_010(self):
        inst_mode_changes = self.expanded_ats_client.on_change('Instrument Mode')
        mode_change_violation = False
        for r1, r2 in zip(inst_mode_changes[:-1], inst_mode_changes[1:]):
            if (r2['Time (UTC)'] - r1['Time (UTC)']).total_seconds() > 6*3600:
                self.get_rule('GEN-010').add_status_dispo('VIOLATING', f"Greater than 6 hours between mode changes at {r1['Time (UTC)']} and {r2['Time (UTC)']}")
                mode_change_violation = True

        first_mode_change = inst_mode_changes[0]
        beginning_of_ats = self.expanded_ats_client[0]
        beginning_of_ats_to_first_mode_change = first_mode_change['Time (UTC)'] - beginning_of_ats['Time (UTC)']
        if beginning_of_ats_to_first_mode_change.total_seconds() > 6*3600:
            self.get_rule('GEN-010').add_status_dispo('VIOLATING', f"Greater than 6 hours between beginning of ATS at {beginning_of_ats['Time (UTC)']} and first mode change at {first_mode_change['Time (UTC)']}.")
            mode_change_violation = True
            #We assume it's OK so long as there's a mode change within 6 hours because the way we build ATSs, there will always be >6hr overlap
            #there might be an exception when transitioning out of comm_only, but that'll just be a false positive when it happens.


        last_mode_change = inst_mode_changes[-1]
        end_of_ats = self.expanded_ats_client[-1]
        last_mode_change_to_end_of_ats = end_of_ats['Time (UTC)'] - last_mode_change['Time (UTC)']
        if last_mode_change_to_end_of_ats.total_seconds() > 6*3600:
            self.get_rule('GEN-010').add_status_dispo('VIOLATING', f"Greater than 6 hours between last mode change at {last_mode_change['Time (UTC)']} and end of ATS at {end_of_ats['Time (UTC)']}")
            mode_change_violation = True

        if not mode_change_violation:
            self.get_rule('GEN-010').add_status_dispo('PASSED', f'All mode changes less than 6 hours apart and mode changes within 6 hours of ATS start and stop.')

    def check_rule_gen_011(self):

        force_standby      = self.raw_ats_client[-10]['Raw Command'].startswith('@rem:standby_cmd 0x0,0x0,0xff')
        close_door         = self.raw_ats_client[-9]['Raw Command'].startswith('@rem:door_command CNTRL1,19200')
        nadir_cmds         = self.raw_ats_client[-8]['Raw Command'].startswith('@ac:select_mode NadirPointing')
        nadir_cmds         = self.raw_ats_client[-7]['Raw Command'].startswith('@ac:select_mode NadirPointing')
        enable_rts_58      = self.raw_ats_client[-6]['Raw Command'].startswith('@sc:enable_rts 58')
        enable_rts_59      = self.raw_ats_client[-5]['Raw Command'].startswith('@sc:enable_rts 59')
        start_rts_59       = self.raw_ats_client[-4]['Raw Command'].startswith('@sc:start_rts 58')
        tdrs_start_tlm_cmd = self.raw_ats_client[-3]['Raw Command'].startswith('@to:start_telemetry 2,3')
        tdrs_set_vcdu_cmd  = self.raw_ats_client[-2]['Raw Command'].startswith('@s1:ul_set_vcdu_default')
        reset_dl_card_cmd  = self.raw_ats_client[-1]['Raw Command'].startswith('@s1:ul_reset_downlink_card')

        all_cmds = [
            force_standby,
            close_door,
            nadir_cmds,
            enable_rts_58,
            enable_rts_59,
            start_rts_59,
            tdrs_start_tlm_cmd,
            tdrs_set_vcdu_cmd,
            reset_dl_card_cmd
        ]

        if sum(all_cmds) == len(all_cmds):
            self.get_rule('GEN-011').add_status_dispo('PASSED', f'End of ATS contains all expected end of ATS rote commands.')
        else:
            self.get_rule('GEN-011').add_status_dispo('VIOLATING', f'ATS missing at least one expected end of ATS rote command.')

    def check_rule_inst_002(self):
        pdb.set_trace()

    def check_rule_inst_003(self):
        pdb.set_trace()

    def check_rule_inst_005(self):
        stellar_point_record = self.expanded_ats_client.contains('command', 'select_mode_stellar_pointing')
        if (len(stellar_point_record) > 0):
            records_5min_before_stellar = self.expanded_ats_client.between(
                    'Time (UTC)', 
                    stellar_point_record[0]['Time (UTC)']-timedelta(seconds=5*60), 
                    stellar_point_record[0]['Time (UTC)'], inclusive='lower'
                )
            records_5min_before_stellar_in_nadir = records_5min_before_stellar.eq('ACS Mode', 'NADIR')
		
            if len(records_5min_before_stellar_in_nadir) == len(records_5min_before_stellar):
                self.get_rule('INST-005').add_status_dispo('PASSED', f'All records in NADIR within 5 minutes of stellar point.')
            else:
                self.get_rule('INST-005').add_status_dispo('VIOLATING', f'Some records not in NADIR within 5 minutes of stellar point.')

