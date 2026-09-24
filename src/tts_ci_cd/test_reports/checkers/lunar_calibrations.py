import pdb
from datetime import datetime
import re

from tts_tower.checkers.checker_base import CheckerBase

class LunarCalibrationChecker(CheckerBase):
    FR_IDS = [
        ('LNR-001', '3ef6ed76'),
        ('LNR-002', '3ef6ed76'),
        ('LNR-003', '3ef6ed76'),
        ('LNR-004', '2a66d6d4'),
        ('LNR-005', '3ef6ed76'),
        ('LNR-006', '3ef6ed76'),
        ('LNR-007', '3ef6ed76'),
    ]
    INPUTS = [
        ('lnr', True),
        ('abs', True),
        ('expanded_ats', True)
    ]

    OFFSET_TOLERANCE = 3

    name = 'Lunar Cals'

    def _impl_init(self, lunar_cal_client, abs_client, expanded_ats):
        pass

    def _impl_do_rulecheck(self, lunar_cal_client, abs_client, expanded_ats):
        dotlnr_cal_found = lunar_cal_client.filepath is not None
        abs_lnr_cmds = abs_client.contains('Purpose', 'Lunar')
        cal_found_in_abs = len(abs_lnr_cmds) > 0
        self.lunar_cal_client = lunar_cal_client
        self.abs_client = abs_client
        self.expanded_ats = expanded_ats

        self.lnr_cmds = None

        #it's the best we can do right now because of the way Oco2InputClient inherits
        #from both InputClient and DataContainer and because DataContainer doesn't have an easy way to filter in the
        #way we need to here.
        self.lc_abs_commands_in_ats = self.expanded_ats._copy(new_records=[self.expanded_ats.eq('Time (GPS)', abs_lnr_cmd['Time'])[0] for abs_lnr_cmd in abs_lnr_cmds if self.expanded_ats.eq('Time (GPS)', abs_lnr_cmd['Time'])])

        #collect all the ATS commands marked as LNR event type
        self.lc_lnr_commands_in_ats = self.expanded_ats.eq('Event Type', 'LNR')

        # Check that the LC file exists and that all 8 commands are in the ATS
        if dotlnr_cal_found and len(self.lc_lnr_commands_in_ats) != (dotlnr_cal_found)*8:
            for fr_id, _ in self.FR_IDS:
                self.get_rule(fr_id).add_status_dispo('VIOLATING', f'Found .lnr file with with the wrong number of LNR commands in ATS. Aborting Lunar cal checks.')
            return

        # Check that the LC commands exist in the ABS file and that all 8 commands are in the ATS
        if cal_found_in_abs and len(self.lc_abs_commands_in_ats) != (cal_found_in_abs)*8:
            for fr_id, _ in self.FR_IDS:
                self.get_rule(fr_id).add_status_dispo('VIOLATING', f'Found lunar cal in ABS with the wrong number of LNR commands in ATS. Aborting Lunar cal checks.')
            return

        # PASS test if no LC file, no LCs in ABS file, and no LC commands in ATS 
        if not cal_found_in_abs and not dotlnr_cal_found and len(self.lc_lnr_commands_in_ats) + len(self.lc_abs_commands_in_ats) == 0:
            for fr_id, _ in self.FR_IDS:
                self.get_rule(fr_id).add_status_dispo('PASSED', f'No .lnr with no lunar commands in ATS or ABS. No lunar cal found.')
            return

        #this is a little wonky because self.lc_abs_commands_in_ats is a list and not a DataContainer. This has to do with how it was generated
        #which is the best way to do it right now since DataContainers don't really have a great way to do what we need to do here.
        lnr_cal_orbits = set(self.lc_lnr_commands_in_ats.unique('Orbit #') + self.lc_abs_commands_in_ats.unique('Orbit #'))
        lnr_cal_power_table = self.expanded_ats.isin('Orbit #', lnr_cal_orbits).power_table('Orbits containing Lunar Calibration')

        #add Lunar Calibration Orbits report to all rules
        self.get_rule('LNR-001').add_report('Lunar Calibration Orbits', lnr_cal_power_table, append=True)
        for fr_id, _ in self.FR_IDS:
            self.get_rule(fr_id).add_report('Lunar Calibration Orbits', [], append=True)


        for lc_instance in [self.lc_lnr_commands_in_ats, self.lc_abs_commands_in_ats]:
            if not lc_instance:
                continue
             
            self.lnr_cmds = lc_instance

            #yes we typically care most about the GPS time for lnr command, but
            #for this before/after, we use UTC since that's the default for xats
            if self.lnr_cmds:
                ats_events_during_lnr = self.expanded_ats.between('Time (UTC)', self.lnr_cmds[0]['Time (UTC)'], self.lnr_cmds[-1]['Time (UTC)'], inclusive='both')
                self.dn_crossing = ats_events_during_lnr.eq('command note', 'Descending Node Crossing')
                if len(self.dn_crossing) != 1:
                    for fr_id, _ in self.FR_IDS:
                        self.get_rule(fr_id).add_status_dispo('FLAGGED', f'Could not determine descending node crossing. Check manually.')
                    continue_checks = False

            eclipse_events = self.expanded_ats.contains('command note', 'Eclipse')
            eclipse_events_before_dn = eclipse_events.before(self.dn_crossing[0]['Time (UTC)'])
            eclipse_events_after_dn = eclipse_events.after(self.dn_crossing[0]['Time (UTC)'])

            self.eclipse_entrance_preceding_lnr = eclipse_events_before_dn[-1]
            self.eclipse_exit_following_lnr = eclipse_events_after_dn[0]
            self.mid_eclipse_time = self.eclipse_entrance_preceding_lnr['Time (UTC)'] + (self.eclipse_exit_following_lnr['Time (UTC)'] - self.eclipse_entrance_preceding_lnr['Time (UTC)'])/2

            if self.eclipse_entrance_preceding_lnr['command note'] != 'Eclipse Entry':
                for fr_id, _ in self.FR_IDS:
                    self.get_rule(fr_id).add_status_dispo('FLAGGED', f'Eclipse event prior to Descending Node is exit. Are we in a new regime that this rule didn\'t account for?')
                continue_checks = False

            if self.eclipse_exit_following_lnr['command note'] != 'Eclipse Exit':
                for fr_id, _ in self.FR_IDS:
                    self.get_rule(fr_id).add_status_dispo('FLAGGED', f'Eclipse event after to Descending Node is entry. Are we in a new regime that this rule didn\'t account for?')
                continue_checks = False

            if len(self.expanded_ats.eq('Event Type', 'LNR')) and not(dotlnr_cal_found) and not(cal_found_in_abs):
                for fr_id, _ in self.FR_IDS:
                    self.get_rule(fr_id).add_status_dispo('FLAGGED', f'LNR commands in ATS with no .lnr for and no lnr commands in abs. How did that happen?')
                continue_checks = True
            elif dotlnr_cal_found and len(self.expanded_ats.eq('Event Type', 'LNR')) == 0:
                for fr_id, _ in self.FR_IDS:
                    self.get_rule(fr_id).add_status_dispo('FLAGGED', f'.lnr file found with no LNR commands in ATS. How did that happen?')
                continue_checks = False
            elif cal_found_in_abs and len(self.expanded_ats.eq('Event Type', 'LNR')) == 0:
                for fr_id, _ in self.FR_IDS:
                    self.get_rule(fr_id).add_status_dispo('FLAGGED', f'LNR commands in ABS and not ATS. How did that happen?')
                continue_checks = False
            else:
                continue_checks = True

            if continue_checks:
                self.check_lnr_001()
                self.check_lnr_002()
                self.check_lnr_003()
                self.check_lnr_004()
                self.check_lnr_005()
                self.check_lnr_006()
                self.check_lnr_007()


    def check_lnr_001(self):
        acs_mode_at_entry = self.eclipse_entrance_preceding_lnr['ACS Mode']
        acs_mode_at_exit = self.eclipse_exit_following_lnr['ACS Mode']
        if acs_mode_at_entry != 'NADIR':
            self.get_rule('LNR-001').add_status_dispo('VIOLATING', f'ACS mode is "{acs_mode_at_entry}" at eclipse entry prior to Lunar Calibration. Should be "NADIR".')
        if acs_mode_at_exit != 'NADIR':
            self.get_rule('LNR-001').add_status_dispo('VIOLATING', f'ACS mode is "{acs_mode_at_exit}" at eclipse exit following Lunar Calibration. Should be "NADIR".')
        if acs_mode_at_entry == 'NADIR' and acs_mode_at_exit == 'NADIR' :
            self.get_rule('LNR-001').add_status_dispo('PASSED', f'ACS mode is "NADIR" at eclipse entry preceding Lunar Calibration and eclipse exit following Lunar Calibration as expected.')


    def check_lnr_002(self):
        inst_mode_at_entry = self.eclipse_entrance_preceding_lnr['Instrument Mode']
        inst_mode_at_exit = self.eclipse_exit_following_lnr['Instrument Mode']
        if inst_mode_at_entry != 'standby':
            self.get_rule('LNR-002').add_status_dispo('VIOLATING', f'Instrument mode is "{inst_mode_at_entry}" at eclipse entry prior to Lunar Calibration. Should be "standby".')
        if inst_mode_at_exit != 'standby':
            self.get_rule('LNR-002').add_status_dispo('VIOLATING', f'Instrument mode is "{inst_mode_at_exit}" at eclipse exit following Lunar Calibration. Should be "standby".')
        if inst_mode_at_entry == 'standby' and inst_mode_at_exit == 'standby' :
            self.get_rule('LNR-002').add_status_dispo('PASSED', f'Instrument mode is "standby" at eclipse entry preceding Lunar Calibration and eclipse exit following Lunar Calibration as expected.')


    def check_lnr_003(self):
        door_pos_at_entry = self.eclipse_entrance_preceding_lnr['Door Position']
        door_pos_at_exit = self.eclipse_exit_following_lnr['Door Position']
        if door_pos_at_entry != 'SOLAR':
            self.get_rule('LNR-003').add_status_dispo('VIOLATING', f'Door position is "{door_pos_at_entry}" at eclipse entry prior to Lunar Calibration. Should be "SOLAR".')
        if door_pos_at_exit != 'SOLAR':
            self.get_rule('LNR-003').add_status_dispo('VIOLATING', f'Door position is "{door_pos_at_exit}" at eclipse exit following Lunar Calibration. Should be "SOLAR".')
        if door_pos_at_entry == 'SOLAR' and door_pos_at_exit == 'SOLAR' :
            self.get_rule('LNR-003').add_status_dispo('PASSED', f'Door position is "SOLAR" at eclipse entry preceding Lunar Calibration and eclipse exit following Lunar Calibration as expected.')


    def check_lnr_004(self):
        actual_lnr_commands = [l['command'] for l in self.lnr_cmds]

        expected_commands = [
            r'@rem:standby_cmd\s*0x0,\s*0x0,\s*0xff',
            r'@AC:select_mode\s*NadirPointing',
            r'@rem:door_command\s*CNTRL1,\s*9600',
            r'@ac:select_mode_stellar_pointing\s*StellarPointing,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*0.0,\s*0.0,\s*DitherEn_Off,\s*PointInstrumentEn_On',
            r'@rem:\b(?:single_cmd|summed_cmd|)\b\s*0x[23]4,\s*0x0,\s*0xff',
            r'@rem:standby_cmd\s*0x0,\s*0x0,\s*0xff',
            r'@rem:door_command\s*CNTRL1,\s*19200',
            r'@AC:select_mode\s*NadirPointing'
            ]

        for e, a in zip(expected_commands, actual_lnr_commands):
            if re.match(e,a):
                self.get_rule('LNR-004').add_status_dispo('PASSED', f'Actual command {a} matches {e}.')
            else:
                self.get_rule('LNR-004').add_status_dispo('VIOLATING', f'Actual command {a} does not match {e}.')


    def check_lnr_005(self):
        actual_offsets = [(l['Time (UTC)'] - self.dn_crossing[0]['Time (UTC)']).total_seconds() for l in self.lnr_cmds]

        expected_offsets = [
            -1081,
            -1080,
            -820,
            -780,
            -480,
            480,
            490,
            530
            ]
        actual_commands = [l['command'] for l in self.lnr_cmds]

        for a, e, c in zip(actual_offsets, expected_offsets, actual_commands):
            if abs(e - a) < self.OFFSET_TOLERANCE:
                self.get_rule('LNR-005').add_status_dispo('PASSED', f'Actual command offset relative to descending node time for command {c} ({a}) matches {e} within a tolerance of {self.OFFSET_TOLERANCE}.')
            else:
                self.get_rule('LNR-005').add_status_dispo('FLAGGED', f'Actual command offset relative to descending node time for command {c} ({a}) does not match {e} within a tolerance of {self.OFFSET_TOLERANCE}.')
        

    def check_lnr_006(self):
        expected_commands = [
            r'@rem:standby_cmd\s*0x0,\s*0x0,\s*0xff',
            r'@AC:select_mode\s*NadirPointing',
            r'@rem:door_command\s*CNTRL1,\s*9600',
            r'@ac:select_mode_stellar_pointing\s*StellarPointing,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*[^,]*,\s*0.0,\s*0.0,\s*DitherEn_Off,\s*PointInstrumentEn_On',
            r'@rem:\b(?:single_cmd|summed_cmd|)\b\s*0x[23]4,\s*0x0,\s*0xff',
            r'@rem:standby_cmd\s*0x0,\s*0x0,\s*0xff',
            r'@rem:door_command\s*CNTRL1,\s*19200',
            r'@AC:select_mode\s*NadirPointing'
            ]

        actual_commands = [l['command'] for l in self.lnr_cmds]

        for e, a in zip(expected_commands, actual_commands):
            if re.match(e,a):
                self.get_rule('LNR-006').add_status_dispo('PASSED', f'Actual command {a} matches {e}.')
            else:
                self.get_rule('LNR-006').add_status_dispo('VIOLATING', f'Actual command {a} does not match {e}.')


    def check_lnr_007(self):
        expected_offsets = [
            -1226,
            -1225,
            -965 ,
            -925,
            -745,
            625,
            635,
            675,
            ]
        actual_offsets = [(l['Time (UTC)'] - self.mid_eclipse_time).total_seconds() for l in self.lnr_cmds]
        actual_commands = [l['command'] for l in self.lnr_cmds]

        for a, e, c in zip(actual_offsets, expected_offsets, actual_commands):
            if abs(e - a) < self.OFFSET_TOLERANCE:
                self.get_rule('LNR-007').add_status_dispo('PASSED', f'Actual command offset relative to mid-eclipse time for command {c} ({a}) matches {e} within a tolerance of {self.OFFSET_TOLERANCE}.')
            else:
                self.get_rule('LNR-007').add_status_dispo('FLAGGED', f'Actual command offset relative to mid-eclipse time for command {c} ({a}) does not match {e} within a tolerance of {self.OFFSET_TOLERANCE}.')
