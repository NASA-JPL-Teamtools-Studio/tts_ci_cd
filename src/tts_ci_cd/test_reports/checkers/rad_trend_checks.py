import pdb
from datetime import datetime
import re

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.text import Pre
from tts_html_utils.core.components.text import Heading1 as H1
from tts_html_utils.core.components.text import Heading2 as H2
from tts_html_utils.core.components.text import Heading4 as H4

MAX_LAMP_ON_TO_DN_SECONDS = 35
MIN_LAMP_ON_TO_DN_SECONDS = 25
MAX_DN_TO_LAMP_OFF_SECONDS = 35
MIN_DN_TO_LAMP_OFF_SECONDS = 25

class CheckerCheckRadTrends(CheckerBase):
    FR_IDS = [
        ('RAD-001', '3ef6ed76'),
        # ('RAD-002', '6acb41d7'), DELETED
        ('RAD-003', '3ef6ed76'),
        ('RAD-004', '3ef6ed76'),
        ('RAD-005', '3ef6ed76'),
        ('RAD-006', '3ef6ed76'),
        ('RAD-007', '3ef6ed76'),
        ('RAD-008', '3ef6ed76'),
        ('RAD-009', '3ef6ed76'),
        ('RAD-010', '3ef6ed76'),
    ]
    INPUTS = [
        ('expanded_ats', True),
        # ('violations_table', True),
        ('abs', True),
        ('violations_table', True)
    ]

    SOUTHERN_HEMISPHERE_STATIONS = ['TR1', 'TR2', 'TR3']

    def _impl_init(self, expanded_ats_client, abs_client, violations_table_client):
        pass

    def _impl_do_rulecheck(self, expanded_ats_client, abs_client, violations_table_client):
        self.expanded_ats_client = expanded_ats_client
        self.violations_table_client = violations_table_client
        self.abs_client = abs_client
        self.rad_trend_records = abs_client.contains('Purpose', 'Radiometric Trend')
        if len(self.rad_trend_records) == 0:
            for rule_id in [
                'RAD-001',
                # 'RAD-002', DELETED
                'RAD-003',
                'RAD-004',
                'RAD-005',
                'RAD-006',
                'RAD-007',
                'RAD-008',
                'RAD-009',
                'RAD-010',
                ]:
                self.get_rule(rule_id).add_status_dispo('PASSED', f'No Rad Trends in ATS')
            return

        self.get_rule('RAD-001').add_report('ABS', 
                [
                H2(f'Raw ABS Contents'),
                H4(abs_client.filepath),
                Pre(abs_client.file_contents_as_string())],
                append=True
                )

        for orbit in abs_client.contains('Purpose', 'Radiometric Trend').unique('Orbit', exclude=[None]):
            self.orbit = orbit
            #why only one orbit if this always crosses descending node?
            #The way the ABS client is written, we just say it's all on the orbit it starts on
            #that way the ABS doesn't need to know when DN is exactly, even though it creates
            #a product that's technically wrong
            self.rad_trend_records_this_orbit = self.rad_trend_records.eq('Orbit', orbit)
            self.start_time = self.rad_trend_records_this_orbit[0]['Time'] #in GPS, don't forget
            self.stop_time = self.rad_trend_records_this_orbit[-1]['Time'] #in GPS, don't forget
            self.xats_records_during_rad_trend = self.expanded_ats_client.between('Time (GPS)', self.start_time, self.stop_time)

            self.lamp_on_record = self.rad_trend_records_this_orbit[5]
            self.descending_node_record = self.xats_records_during_rad_trend.contains('command note', 'Descending Node')[0]
            self.single_pixel_command = self.rad_trend_records_this_orbit[6]
            self.begin_orbit = self.orbit
            #if there is only one record here, it will be the descending node which marks
            #the beginning of the subsequent orbit. If there is more than one, the last
            #record will be the descending node or something after it, so it will still
            #get us the right orbit num=ber.
            self.end_orbit = self.xats_records_during_rad_trend[-1]['Orbit #']
            self.xats_records_around_rad_trend = self.expanded_ats_client.isin('Orbit #', [self.begin_orbit, self.begin_orbit+1])

            self.check_rule_rad_001()
            # self.check_rule_rad_002() DELETED
            self.check_rule_rad_003()
            self.check_rule_rad_004()
            self.check_rule_rad_005_and_rad_006()
            self.check_rule_rad_007()
            self.check_rule_rad_008()
            self.check_rule_rad_009()
            self.check_rule_rad_010()

            table = self.xats_records_around_rad_trend.power_table(f'ATS Records for Orbit {orbit}')
            header = H1(f'ATS Records for Orbit {orbit}')
            self.get_rule(self.FR_IDS[0][0]).add_report('Rad Trend xATS Records', [header, table], append=True)

        for fr_id, _ in self.FR_IDS:
            self.get_rule(fr_id).add_report('Rad Trend xATS Records', [], append=True)

    def check_rule_rad_001(self):
        #need both orbits since RAD trend crosses DN
        #sh == Southern Hemisphere
        sh_aos_records = self.expanded_ats_client.isin('Orbit #', [self.orbit, self.orbit+1]).isin('command note', [f'AOS at {s}' for s in self.SOUTHERN_HEMISPHERE_STATIONS])
        sh_los_records = self.expanded_ats_client.isin('Orbit #', [self.orbit, self.orbit+1]).isin('command note', [f'LOS at {s}' for s in self.SOUTHERN_HEMISPHERE_STATIONS])

        if sh_aos_records or sh_los_records:
            orbit_no = sh_aos_records[0]['Orbit #'] if sh_aos_records else sh_los_records[0]['Orbit #']
            self.get_rule('RAD-001').add_status_dispo('VIOLATING', f'Rad Trend occurs during TR contact on orbit {self.begin_orbit}')
        else:
            self.get_rule('RAD-001').add_status_dispo('PASSED', f'No TR pass during Rad Trend on orbit {self.begin_orbit}')


    # def check_rule_rad_002(self): DELETED
    #     #this ended up merging with #1 and being exactly the same. Consider removing one of them
    #     tr_aos_records = self.expanded_ats_client.isin('Orbit #', [self.orbit, self.orbit+1]).contains('command note', 'AOS at TR')
    #     tr_los_records = self.expanded_ats_client.isin('Orbit #', [self.orbit, self.orbit+1]).contains('command note', 'LOS at TR')
    #     if len(tr_aos_records) or len(tr_los_records):
    #         orbit_no = tr_aos_records[0]['Orbit #'] if tr_aos_records else tr_los_records[0]['Orbit #']
    #         self.get_rule('RAD-002').add_status_dispo('VIOLATING', f'Trollsat contact on orbit following rad trend ({self.end_orbit})')
    #     else:
    #         self.get_rule('RAD-002').add_status_dispo('PASSED', f'No Trollsat contact on orbit following rad trend ({self.end_orbit})')

    def check_rule_rad_003(self):
        xats_records_in_eclipse = self.xats_records_during_rad_trend.eq('in_sun', True)
        if len(xats_records_in_eclipse):
            for r in xats_records_in_eclipse:
                self.get_rule('RAD-003').add_status_dispo('FLAGGED', f'Command "{r["command"]}" on line {r["Line #"]} occurs in sun on orbit ({self.begin_orbit}). This is downgraded to FLAGGED because this branch triggers if ABS commands are not yet incorporated into the ATS.')
        else:
            self.get_rule('RAD-003').add_status_dispo('PASSED', f'No Rad Trend commands happen in sun on orbit ({self.begin_orbit})')

    def check_rule_rad_004(self):
        #this is a pretty coarse check that might fail and create a false positive.
        abs_has_lamp_2 = len(self.rad_trend_records_this_orbit.contains('Command', 'lamp_cmd 2')) == 1
        xats_has_lamp_2 = len(self.xats_records_during_rad_trend.contains('command', 'lamp_cmd 2')) == 1

        if abs_has_lamp_2 and xats_has_lamp_2:
            self.get_rule('RAD-004').add_status_dispo('PASSED', f'ABS and Extended ATS show Lamp 2 being used on orbit {self.begin_orbit}.')
        elif abs_has_lamp_2:
            self.get_rule('RAD-004').add_status_dispo('FLAGGED', f'ABS shows Lamp 2 being used on orbit {self.begin_orbit}, but ATS does not.')
        elif xats_has_lamp_2:
            self.get_rule('RAD-004').add_status_dispo('FLAGGED', f'ATS shows Lamp 2 being used on orbit {self.begin_orbit}, but ABS does not.')
        else:
            self.get_rule('RAD-004').add_status_dispo('FLAGGED', f'ABS and Extended ATS both show Lamp other than 2 being used on orbit {self.begin_orbit}.')
            
    def check_rule_rad_005_and_rad_006(self):
        lamp_on_to_dn_seconds = (self.descending_node_record['Time (GPS)'] - self.lamp_on_record['Time']).total_seconds()
        dn_to_single_pixel_seconds = (self.single_pixel_command['Time'] - self.descending_node_record['Time (GPS)']).total_seconds()

        if lamp_on_to_dn_seconds > MAX_LAMP_ON_TO_DN_SECONDS:
            self.get_rule('RAD-005').add_status_dispo('VIOLATING', f'{lamp_on_to_dn_seconds} > {MAX_LAMP_ON_TO_DN_SECONDS} seconds from lamp on to descending node on orbit {self.begin_orbit}.')
        else:
            self.get_rule('RAD-005').add_status_dispo('PASSED', f'{lamp_on_to_dn_seconds} <= {MAX_LAMP_ON_TO_DN_SECONDS} seconds from lamp on to descending node on orbit {self.begin_orbit}.')

        if lamp_on_to_dn_seconds < MIN_LAMP_ON_TO_DN_SECONDS:
            self.get_rule('RAD-005').add_status_dispo('VIOLATING', f'{lamp_on_to_dn_seconds} < {MIN_LAMP_ON_TO_DN_SECONDS} seconds from lamp on to descending node on orbit {self.begin_orbit}.')
        else:
            self.get_rule('RAD-005').add_status_dispo('PASSED', f'{lamp_on_to_dn_seconds} >= {MIN_LAMP_ON_TO_DN_SECONDS} seconds from lamp on to descending node on orbit {self.begin_orbit}.')

        if dn_to_single_pixel_seconds > MAX_DN_TO_LAMP_OFF_SECONDS:
            self.get_rule('RAD-006').add_status_dispo('VIOLATING', f'{dn_to_single_pixel_seconds} > {MAX_DN_TO_LAMP_OFF_SECONDS} seconds from descending node to single pixel command on orbit {self.begin_orbit}.')
        else:
            self.get_rule('RAD-006').add_status_dispo('PASSED', f'{dn_to_single_pixel_seconds} <= {MAX_DN_TO_LAMP_OFF_SECONDS} seconds from descending node to single pixel command on orbit {self.begin_orbit}.')

        if dn_to_single_pixel_seconds < MIN_DN_TO_LAMP_OFF_SECONDS:
            self.get_rule('RAD-006').add_status_dispo('VIOLATING', f'{dn_to_single_pixel_seconds} < {MIN_DN_TO_LAMP_OFF_SECONDS} seconds from descending node to single pixel command on orbit {self.begin_orbit}.')
        else:
            self.get_rule('RAD-006').add_status_dispo('PASSED', f'{dn_to_single_pixel_seconds} >= {MIN_DN_TO_LAMP_OFF_SECONDS} seconds from descending node to single pixel command on orbit {self.begin_orbit}.')

    def check_rule_rad_007(self):
        if len(self.xats_records_during_rad_trend.notin('Event Type', ['ABS', 'OEF', 'BCA timeout'])):
            self.get_rule('RAD-007').add_status_dispo('VIOLATING', f'Unexpected extended ATS records during rad trend on orbit {self.begin_orbit}.')
        elif len(self.xats_records_during_rad_trend.eq('Event Type', 'ABS')) > 11:
            n_abs_commands = len(self.xats_records_during_rad_trend.eq('Event Type', 'ABS'))
            self.get_rule('RAD-007').add_status_dispo('VIOLATING', f'Unexpected extended ABS records during rad trend on orbit {self.begin_orbit}. Found {n_abs_commands} records. Should be 11.')
        else:
            self.get_rule('RAD-007').add_status_dispo('PASSED', f'Extended ATS records during rad trend on orbit {self.begin_orbit} all as expected.')
   
    def check_rule_rad_008(self):
        violations_during_rad_trend_orbits = self.violations_table_client.isin('Orbit Number', [self.orbit, self.orbit + 1])
        if len(violations_during_rad_trend_orbits):
            for violation_during_rad_trend_orbits in violations_during_rad_trend_orbits:
                vid = violation_during_rad_trend_orbits['Violation ID*']
                self.get_rule('RAD-008').add_status_dispo('FLAGGED', f'{vid} found in Nephyths violations table on one of the orbits of the Rad trend on orbits {self.orbit} and {self.orbit + 1}. This may not be an issue because this rule is written very broadly. Must check manually from here.')
        else:
            self.get_rule('RAD-008').add_status_dispo('PASSED', f'No violations found in Nephyths violations table on either of the orbits of the Rad trend on obirts {self.orbit} and {self.orbit + 1}.')

    def check_rule_rad_009(self):
        expected_commands = [
            'rem:door_command CNTRL1,42',
            'rem:single_cmd 0x33, 0x0, 0xff',
            'rem:standby_cmd 0, 0x0, 0xff',
            'rem:summed_cmd 0x23,0x0, 0xff',
            'rem:standby_cmd 0, 0x0, 0xff',
            'rem:lamp_cmd 2, 330',
            'rem:single_cmd 0x32, 0x0, 0xff',
            'rem:standby_cmd 0, 0x0, 0xff',
            'rem:summed_cmd 0x22, 0x0, 0xff',
            'rem:standby_cmd 0, 0x0, 0xff',
            'rem:lamp_cmd 0, 0'
        ]

        rad_trend_records_in_ats = self.xats_records_during_rad_trend.eq('Event Type', 'ABS')

        if len(self.rad_trend_records_this_orbit) == 11 and len(rad_trend_records_in_ats) == 11:
            self.get_rule('RAD-009').add_status_dispo('PASSED', f'Correct number of commands in in the rad trend in ABS and ATS on orbit {self.begin_orbit}.')
        elif len(self.rad_trend_records_this_orbit) != 11:
            self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Incorrect number of commands in in the rad trend in ABS on orbit {self.begin_orbit}.')
        elif len(rad_trend_records_in_ats) != 11:
            self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Incorrect number of commands in in the rad trend in ATS on orbit {self.begin_orbit}.')
        else:
            self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Incorrect number of commands in in the rad trend in ABS and ATS on orbit {self.begin_orbit}.')

        for ii in range(len(self.rad_trend_records_this_orbit)):
            if ii >= len(expected_commands):
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Too many commands in the rad trend in ABS on orbit {self.begin_orbit}.')
            elif self.rad_trend_records_this_orbit[ii]['Command'] == expected_commands[ii]:
                self.get_rule('RAD-009').add_status_dispo('PASSED', f'Command {self.rad_trend_records_this_orbit[ii]["Command"]} is correct in the rad trend in ABS on orbit {self.begin_orbit}.')
            elif expected_commands[ii] == 'rem:lamp_cmd 2, 330' and self.rad_trend_records_this_orbit[ii]['Command'] in ['rem:lamp_cmd 1, 330', 'rem:lamp_cmd 4, 330']:
                self.get_rule('RAD-009').add_status_dispo('FLAGGED', f'Unexpected lamp number in ABS. Usually this isn\'t OK, but may be if you\'re doing a post-decon rad trend')
            else:
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Command {self.rad_trend_records_this_orbit[ii]["Command"]} is incorrect in the rad trend in ABS on orbit {self.begin_orbit}. Expected {expected_commands[ii]}')

        for ii in range(len(rad_trend_records_in_ats)):
            if ii >= len(expected_commands):
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Too many commands in the rad trend in ATS on orbit {self.begin_orbit}.')
            #WTF is that replace doing in there? Getting over a hurdle with
            #the way ABSs are made. I think it's an IDL bug, but apparently
            #the ABS doens't need spaces, but they'll be converted over to 
            #have whitespace by the time they show up in the expanded ATS
            elif rad_trend_records_in_ats[ii]['command'].replace(', ', ',') == '@' + expected_commands[ii].replace(', ', ','):
                self.get_rule('RAD-009').add_status_dispo('PASSED', f'Command {rad_trend_records_in_ats[ii]["command"]} is correct in the rad trend in ATS on orbit {self.begin_orbit}.')
            elif expected_commands[ii] == 'rem:lamp_cmd 2, 330' and rad_trend_records_in_ats[ii]['command'] in ['@rem:lamp_cmd 1, 330', '@rem:lamp_cmd 4, 330']:
                self.get_rule('RAD-009').add_status_dispo('FLAGGED', f'Unexpected lamp number in ATS. Usually this isn\'t OK, but may be if you\'re doing a post-decon rad trend')
            else:
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Command {rad_trend_records_in_ats[ii]["command"]} is incorrect in the rad trend in ATS on orbit {self.begin_orbit}. Expected {expected_commands[ii]}')


        time_diffs = [80, 120, 16, 90, 1, 60, 120, 16, 90, 1]

        for ii in range(len(self.rad_trend_records_this_orbit)-1):
            time_diff = (self.rad_trend_records_this_orbit[ii + 1]['Time'] - self.rad_trend_records_this_orbit[ii]['Time']).total_seconds()
            if ii >= len(time_diffs):
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Too many commands in the rad trend in ABS on orbit {self.begin_orbit}.')
            elif time_diff == time_diffs[ii]:
                self.get_rule('RAD-009').add_status_dispo('PASSED', f'Timing is correct between commands {ii+1} and {ii+2} in the rad trend in ABS on orbit {self.begin_orbit}. ({time_diffs[ii]}s)')            
            else:
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Timing is incorrect between commands {ii+1} and {ii+2} in the rad trend in ABS on orbit {self.begin_orbit}. Is: {time_diff}s. Should be: {time_diffs[ii]}s.')

        for ii in range(len(rad_trend_records_in_ats)-1):
            time_diff = (rad_trend_records_in_ats[ii + 1]['Time (GPS)'] - rad_trend_records_in_ats[ii]['Time (GPS)']).total_seconds()
            if ii >= len(time_diffs):
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Too many commands in the rad trend in ATS on orbit {self.begin_orbit}.')
            elif time_diff == time_diffs[ii]:
                self.get_rule('RAD-009').add_status_dispo('PASSED', f'Timing is correct between commands {ii+1} and {ii+2} in the rad trend in ATS on orbit {self.begin_orbit}. ({time_diffs[ii]}s)')            
            else:
                self.get_rule('RAD-009').add_status_dispo('VIOLATING', f'Timing is incorrect between commands {ii+1} and {ii+2} in the rad trend in ATS on orbit {self.begin_orbit}. Is: {time_diff}s. Should be: {time_diffs[ii]}s.')

        # Reference:
        # 2025/02/08 12:30:14.000 |rem:door_command CNTRL1,42; Not assuming that ATS has us in the lamp position
        # 2025/02/08 12:31:34.000 |rem:single_cmd 0x33, 0x0, 0xff; Wait for door, then Single Pixel dark
        # 2025/02/08 12:33:34.000 |rem:standby_cmd 0, 0x0, 0xff; Standby (to make sure)
        # 2025/02/08 12:33:50.000 |rem:summed_cmd 0x23,0x0, 0xff; Summed dark
        # 2025/02/08 12:35:20.000 |rem:standby_cmd 0, 0x0, 0xff; End Summed Dark
        # 2025/02/08 12:35:21.000 |rem:lamp_cmd 2, 330; Lamp on
        # 2025/02/08 12:36:21.000 |rem:single_cmd 0x32, 0x0, 0xff; Single (after lamp warms up one minute)
        # 2025/02/08 12:38:21.000 |rem:standby_cmd 0, 0x0, 0xff; Standby
        # 2025/02/08 12:38:37.000 |rem:summed_cmd 0x22, 0x0, 0xff; Summed Lamp
        # 2025/02/08 12:40:07.000 |rem:standby_cmd 0, 0x0, 0xff; Standby
        # 2025/02/08 12:40:08.000 |rem:lamp_cmd 0, 0; Forces Lamp off when done

    def check_rule_rad_010(self):
        rad_trend_start_orbit = self.xats_records_during_rad_trend[0]['Orbit #']
        xats_this_orbit = self.expanded_ats_client.eq('Orbit #', rad_trend_start_orbit)
        northern_hemisphere_aos_records =  xats_this_orbit.contains('command note', 'AOS at AS')
        northern_hemisphere_aos_records += xats_this_orbit.contains('command note', 'AOS at WG')

        if len(northern_hemisphere_aos_records):
            cmd_note = northern_hemisphere_aos_records[0]['command note']
            self.get_rule('RAD-010').add_status_dispo('PASSED', f'Rad trend begins on orbit with Northern Hemisphere. Command note: "{cmd_note}".')
        else:
            self.get_rule('RAD-010').add_status_dispo('VIOLATING', f'Rad trend begins on orbit without Northern Hemisphere.')

