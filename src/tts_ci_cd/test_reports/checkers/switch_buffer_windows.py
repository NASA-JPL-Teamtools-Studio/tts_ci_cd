import pdb
from datetime import datetime, timedelta
from copy import deepcopy

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.text import Paragraph
from tts_html_utils.core.components.text import Heading1 as H1
from tts_html_utils.core.components.text import Heading2 as H2

# ===================================================================
# :: Checker Class
# ===================================================================
class CheckerCheckSwitchBufferWindows(CheckerBase):
    FR_IDS = [
        ('SBW-001', '3ef6ed76'),
        ('SBW-002', '3ef6ed76'),
        ('SBW-003', '3ef6ed76'),
        ('SBW-004', '3ef6ed76'),
        ('SBW-005', 'd10fbb64'),
        ('SBW-006', 'a3ac6e33'),
        ('SBW-007', 'a3ac6e33'),
        ('SBW-008', '3ef6ed76'),
        ('SBW-009', 'd10fbb64')
    ]

    INPUTS = [
        ('expanded_ats', True),
        ('last_expanded_ats', False),
        ('switch_buffer', True)
    ]

    def _impl_init(self, expanded_ats_client, last_expanded_ats, switch_buffer_client):
        pass

    def _impl_do_rulecheck(self, expanded_ats_client, last_expanded_ats, switch_buffer_client):
        self.expanded_ats_client = expanded_ats_client
        self.last_expanded_ats = last_expanded_ats
        self.switch_buffer_client = switch_buffer_client

        if self.switch_buffer_client.filepath is None:
            for rule_id, _ in self.FR_IDS:
                self.get_rule(rule_id).add_status_dispo('FLAGGED', f'Switch_Buffer.txt not found.')

        for switch_buffer_record in switch_buffer_client:
            xats_this_orbit = expanded_ats_client.eq('Orbit #', switch_buffer_record['Orbit'])
            if last_expanded_ats is not None:
                xats_this_orbit_last_week = last_expanded_ats.eq('Orbit #', switch_buffer_record['Orbit'])
            else:
                xats_this_orbit_last_week = None 

            self.check_rule_sbw_001(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record, expanded_ats_client, last_expanded_ats)
            self.check_rule_sbw_002(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_003(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_004(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_005(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_006(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_007(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_008(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)
            self.check_rule_sbw_009(xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record)

        self.make_sbw_report()


    def make_sbw_report(self):
        for orbit in self.switch_buffer_client.unique('Orbit'):
            header = H1(f'Switch Buffer Records for orbit {orbit}')
            xats_table = self.switch_buffer_client.sbw_table(orbit)
            self.get_rule('SBW-001').add_report('Switch Buffer Windows (beta)', [header, xats_table], append=True)
        for rule, _ in self.FR_IDS:
            if rule != 'SBW-001': self.get_rule(rule).add_report('Switch Buffer Windows (beta)', [], append=True)

    def check_rule_sbw_001(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record, expanded_ats_client, last_expanded_ats):
        rts_81_records = xats_this_orbit.eq('Event Type', 'RTS #81')
        rts_81_records += xats_this_orbit_last_week.eq('Event Type', 'RTS #81')
        macro_records_this_week = expanded_ats_client.contains('Event Type', 'Macro')
        macro_records_last_week = last_expanded_ats.contains('Event Type', 'Macro')

        #Why the bools? To make this an XOR. I tried using ^, but that's a bitwise XOR, which
        #didn't work like I expected when I passed lens into it.
        switching_between_sci_and_comm = bool(len(macro_records_this_week)) != bool(len(macro_records_last_week))

        if switching_between_sci_and_comm and len(rts_81_records):
            self.get_rule('SBW-001').add_status_dispo('VIOLATING', f'Contact on orbit {switch_buffer_record["Orbit"]} is s-band, and we are switching between comm_only and science.')
        elif len(rts_81_records):
            self.get_rule('SBW-001').add_status_dispo('PASSED', f'Contact on orbit {switch_buffer_record["Orbit"]} is s-band, but both ATSs are science or both are comm_only')
        else:
            self.get_rule('SBW-001').add_status_dispo('PASSED', f'Contact on orbit {switch_buffer_record["Orbit"]} is not s-band.')

    def check_rule_sbw_002(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        #TO DO: Validate that it's really just these command types that we care about
        #and change the language in the rule to reflect that
        # cmd_records = xats_this_orbit.isin('Event Type', ['RTS #80', 'RTS #81', 'ATS', 'ABS', 'LNR'])
        cmd_records = xats_this_orbit.isin('Event Type', ['RTS #80', 'RTS #81', 'ATS', 'ABS', 'LNR'])
        cmd_records += xats_this_orbit_last_week.isin('Event Type', ['RTS #80', 'RTS #81', 'ATS', 'ABS', 'LNR'])
        #To do: turn this into a dict so we don't have magic numbers
        time_deltas = [(switch_buffer_record['Start Time'] - r['Time (UTC)']).total_seconds() for r in cmd_records]
        #if t < 0, then command is after SBW start, which is checked in other rules.
        #if t > 10, then command is early enough that this is OK
        too_short_deltas = [t for t in time_deltas if t > 0 and t < 10]

        if len(too_short_deltas):
            self.get_rule('SBW-002').add_status_dispo('VIOLATING', f'Switch buffer starts too soon after command on orbit #{switch_buffer_record["Orbit"]}.')
        else:
            self.get_rule('SBW-002').add_status_dispo('PASSED', f'Switch buffer does not start too soon after command on orbit #{switch_buffer_record["Orbit"]}.')

    def check_rule_sbw_003(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        #I'd want to check this against both weeks, but because we don't have an LOS record
        #for last week in the case of an s-band blind acq, there's no good way to do it in
        #general. Consider whether it's worth expanding this
        los_time = switch_buffer_record['LOS']
        sbw_to_los_time = (los_time - switch_buffer_record['Stop Time']).total_seconds()
        if sbw_to_los_time < 30:
            self.get_rule('SBW-003').add_status_dispo('VIOLATING', f'Switch buffer ends {sbw_to_los_time}s before LOS on orbit #{switch_buffer_record["Orbit"]}. Should be at least 30.')
        else:
            self.get_rule('SBW-003').add_status_dispo('PASSED', f'Switch buffer ends {sbw_to_los_time}s before LOS on orbit #{switch_buffer_record["Orbit"]}. Should be at least 30.')

    def check_rule_sbw_004(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        cmd_records = xats_this_orbit.isin('Event Type', ['ATS', 'ABS', 'LNR'])
        cmd_records += xats_this_orbit_last_week.isin('Event Type', ['ATS', 'ABS', 'LNR'])
        time_deltas = [(r['Time (UTC)'] - switch_buffer_record['Stop Time']).total_seconds() for r in cmd_records]

        if [t for t in time_deltas if t >0 and t <15]:
            self.get_rule('SBW-004').add_status_dispo('VIOLATING', f'Switch ends less than 15s before ATS command on orbit #{switch_buffer_record["Orbit"]}.')
        else:
            self.get_rule('SBW-004').add_status_dispo('PASSED', f'Switch ends 15s or more before any ATS command on orbit #{switch_buffer_record["Orbit"]}.')

    def check_rule_sbw_005(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        delta = [(r_this['Time (UTC)'] - r_last['Time (UTC)']).total_seconds() for r_last, r_this in zip(xats_this_orbit, xats_this_orbit_last_week)]
        delta_too_large = [d for d in delta if abs(d) > 5]
        # if 'sbw_005/passed' in str(self.expanded_ats_client.filepath): pdb.set_trace()
        
        if len(xats_this_orbit) != len(xats_this_orbit_last_week):
            self.get_rule('SBW-005').add_status_dispo('FLAGGED', f'Different number of commands in this week\'s and last week\'s ATS for switch buffer orbit #{switch_buffer_record["Orbit"]}. Must inspect manually')            
        elif len(delta_too_large):
            self.get_rule('SBW-005').add_status_dispo('VIOLATING', f'Some commands on orbit #{switch_buffer_record["Orbit"]} >5s apart between planned ATS and currently executing ATS')
        else:
            self.get_rule('SBW-005').add_status_dispo('PASSED', f'All commands on orbit #{switch_buffer_record["Orbit"]} <=5s apart between planned ATS and currently executing ATS')

    def check_rule_sbw_006(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        sbw_dur = (switch_buffer_record['Stop Time'] - switch_buffer_record['Start Time']).total_seconds()
        if sbw_dur < 60:
            self.get_rule('SBW-006').add_status_dispo(
                'VIOLATING', 
                f'Switch buffer is {sbw_dur}s on orbit #{switch_buffer_record["Orbit"]}. Should be >=60.0s')
        else:
            self.get_rule('SBW-006').add_status_dispo(
                'PASSED', 
                f'Switch buffer is {sbw_dur}s on orbit #{switch_buffer_record["Orbit"]}. Should be >=60.0s')

    def check_rule_sbw_007(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        target_records = xats_this_orbit.contains('command note', 'Begin target')
        target_records += xats_this_orbit_last_week.contains('command note', 'Begin target')
        is_s_band = 'S-Band' in switch_buffer_record['Type']

        if len(target_records) and is_s_band:
            self.get_rule('SBW-007').add_status_dispo('FLAGGED', f'Target found on S-Band switch buffer orbit {switch_buffer_record["Orbit"]}, which is dangerous.')
        elif len(target_records):
            self.get_rule('SBW-007').add_status_dispo('PASSED', f'Target found on X-Band switch buffer orbit {switch_buffer_record["Orbit"]}, which is safe.')
        elif is_s_band:
            self.get_rule('SBW-007').add_status_dispo('PASSED', f'No target found on S-Band switch buffer orbit {switch_buffer_record["Orbit"]}, which is safe.')
        else:
            self.get_rule('SBW-007').add_status_dispo('PASSED', f'No target found on X-Band switch buffer orbit {switch_buffer_record["Orbit"]}, which is safe.')

    def check_rule_sbw_008(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        thrust_cmds_this_orbit = xats_this_orbit.eq('ACS Mode', 'THRUST')
        orbit_no = xats_this_orbit[0]['Orbit #']

        if len(thrust_cmds_this_orbit):
            self.get_rule('SBW-008').add_status_dispo('FLAGGED', f'Records in THRUST mode found on obit {orbit_no}. User must check manually to determine if they overlap with SBW.')
        else:
            self.get_rule('SBW-008').add_status_dispo('PASSED', f'No records in THRUST mode found on obit {orbit_no}.')

    def check_rule_sbw_009(self, xats_this_orbit, xats_this_orbit_last_week, switch_buffer_record):
        #I'd want to check this against both weeks, but because we don't have an AOS record
        #for last week in the case of an s-band blind acq, there's no good way to do it in
        #general. Consider whether it's worth expanding this
        aos_time = switch_buffer_record['AOS']
        sbw_to_aos_time = (switch_buffer_record['Stop Time'] - aos_time).total_seconds()
        if sbw_to_aos_time < 120:
            self.get_rule('SBW-009').add_status_dispo('VIOLATING', f'Switch buffer ends {sbw_to_aos_time}s after AOS on orbit #{switch_buffer_record["Orbit"]}. Should be at least 120.')
        else:
            self.get_rule('SBW-009').add_status_dispo('PASSED', f'Switch buffer ends {sbw_to_aos_time}s after AOS on orbit #{switch_buffer_record["Orbit"]}. Should be at least 120.')

