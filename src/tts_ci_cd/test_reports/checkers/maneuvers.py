import pdb
from datetime import datetime, timedelta
import re

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.text import Paragraph
from tts_html_utils.core.components.text import Pre
from tts_html_utils.core.components.text import Heading2 as H2
from tts_html_utils.core.components.text import Heading4 as H4

class CheckerCheckManeuvers(CheckerBase):
    FR_IDS = [
        ('MAN-001', 'f54593aa'),
        ('MAN-002', 'f54593aa'),
        ('MAN-003', 'a04ae28b'),
        ('MAN-004', '3ef6ed76'),
        ('MAN-005', '3ef6ed76'),
        # ('MAN-006', 'aa902f8c'), DELETED
        ('MAN-007', 'd10fbb64'),
        # ('MAN-008', 'b9007ba6'), DELETED
        ('MAN-009', 'd10fbb64'),
        ('MAN-010', 'd10fbb64'),
    ]
    INPUTS = [
        ('mnvr', True),
        ('expanded_ats', True)
    ]
    name = 'Manuevers'

    def _impl_init(self, maneuver_client, expanded_ats_client):
        pass

    def _impl_do_rulecheck(self, maneuver_client, expanded_ats_client):
        self.maneuver_client = maneuver_client
        self.xats = expanded_ats_client


        if len(self.xats.eq('ACS Mode', 'THRUST')) == 0 and maneuver_client.filepath is None:
            for rule_id, _ in self.FR_IDS:
                self.get_rule(rule_id).add_status_dispo('PASSED', f'No THRUST mode found! No burns to be verified.')
        elif maneuver_client.filepath is None and len(self.xats.eq('ACS Mode', 'THRUST')) != 0:
            for rule_id, _ in self.FR_IDS:
                self.get_rule(rule_id).add_status_dispo('FLAGGED', f'THRUST Mode found, but no mnvr file. How did that happen?')
        elif maneuver_client.filepath is not None and len(self.xats.eq('ACS Mode', 'THRUST')) == 0:
            for rule_id, _ in self.FR_IDS:
                self.get_rule(rule_id).add_status_dispo('VIOLATING', f'No THRUST mode found with mnvr file present.')
        else:
            self.thrust_begin_time = self.xats.contains('command', '@ac:select_mode_thrust ThrustPrimary', exactly=1)['Time (UTC)']
            records_before_thrust = self.xats.before(self.thrust_begin_time)
            last_door_to_solar_diffuser = records_before_thrust.contains('command note', 'Ensure door is in diffuser position')[-1]
            self.door_to_solar_diffuser_time = last_door_to_solar_diffuser['Time (UTC)']
            self.polar_cal_records = self.xats.isin('Event Type', ['RTS #127', 'RTS #128'])
            self.floating_dark_records = self.xats.eq('Event Type', 'Macro #15')
            self.burn_command_records = self.xats.contains('command', 'select_mode_thrust ThrustPrimary')

            burn_orbit = self.burn_command_records[0]['Orbit #']
            
            self.check_man_001()
            self.check_man_002()
            self.check_man_003()
            self.check_man_004()
            self.check_man_005()
            # self.check_man_006() DELETED
            self.check_man_007()
            # self.check_man_008() DELETED
            self.check_man_009()
            self.check_man_010()

            records_during_burn = self.xats.isin('Orbit #', [burn_orbit-1, burn_orbit, burn_orbit+1])
            burn_orbits_table = records_during_burn.power_table('Burn Orbits')
            self.get_rule('MAN-001').add_report('Burn Orbits', [burn_orbits_table], append=True)
            for rule_id, _ in self.FR_IDS:
                if rule_id != 'MAN-001':
                    self.get_rule(rule_id).add_report('Burn Orbits', [], append=True)

    def check_man_001(self):
        polar_cal_to_burn_delta = [(r['Time (UTC)'] - self.door_to_solar_diffuser_time).total_seconds() for r in self.polar_cal_records]
        untimely_commands = [t for t in polar_cal_to_burn_delta if t > -50*60 and t < 0]
        if len(untimely_commands):
            self.get_rule('MAN-001').add_status_dispo('VIOLATING', f'{len(untimely_commands)} command(s) from polar cals found less than 50 minutes prior to burn')
        else:
            self.get_rule('MAN-001').add_status_dispo('PASSED', f'No commands from polar cals found less than 50 minutes prior to burn')

    def check_man_002(self): 
        floating_dark_to_burn_delta = [(r['Time (UTC)'] - self.door_to_solar_diffuser_time).total_seconds() for r in self.floating_dark_records]
        untimely_commands = [t for t in floating_dark_to_burn_delta if t > -50*60 and t < 0]
        if len(untimely_commands):
            self.get_rule('MAN-002').add_status_dispo('VIOLATING', f'{len(untimely_commands)} command(s) from floating darks found less than 50 minutes prior to burn')
        else:
            self.get_rule('MAN-002').add_status_dispo('PASSED', f'No commands from floating darks found less than 50 minutes prior to burn')
            
    def check_man_003(self):
        stellar_point_record = self.xats.contains('command', 'select_mode_stellar_pointing')
        records_5min_before_stellar = self.xats.between(
            'Time (UTC)', 
            stellar_point_record[0]['Time (UTC)']-timedelta(seconds=5*60), 
            stellar_point_record[0]['Time (UTC)'], inclusive='lower'
            )
        records_5min_before_stellar_in_nadir = records_5min_before_stellar.eq('ACS Mode', 'NADIR')

        if len(records_5min_before_stellar_in_nadir) == len(records_5min_before_stellar):
            self.get_rule('MAN-003').add_status_dispo('PASSED', f'All records in NADIR within 5 minutes of stellar point.')
        else:
            self.get_rule('MAN-003').add_status_dispo('VIOLATING', f'Some records not in NADIR within 5 minutes of stellar point.')

    def check_man_004(self):
        #Significantly changed after talking with Richard, re-vet tests carefully
        xats_after_burn_start = self.xats.after(self.burn_command_records[0]['Time (UTC)'])
        nadir_records_after_burn_start = xats_after_burn_start.eq('ACS Mode', 'NADIR')
        records_80s_before_burn_to_5min_after_nadir = self.xats.between(
            'Time (UTC)', 
            self.burn_command_records[0]['Time (UTC)']-timedelta(seconds=80), 
            nadir_records_after_burn_start[0]['Time (UTC)']+timedelta(seconds=300), inclusive='lower'
            )
        if len(records_80s_before_burn_to_5min_after_nadir.ne('Door Position', 'SOLAR')):
            self.get_rule('MAN-004').add_status_dispo('VIOLATING', f'Door is not in solar diffuser sometime between 80s before burn and 5min after ruturn to nadir.')
        else:
            self.get_rule('MAN-004').add_status_dispo('PASSED', f'Door is solar diffuser from 80s before burn until 5min after ruturn to nadir.')


    def check_man_005(self):
        #Significantly changed after talking with Richard, re-vet tests carefully
        records_during_burn = self.xats.eq('ACS Mode', 'THRUST')

        if len(records_during_burn.ne('Instrument Mode', 'standby')):
            self.get_rule('MAN-005').add_status_dispo('FLAGGED', f'Some records during burn not in standby.')
        else:
            self.get_rule('MAN-005').add_status_dispo('PASSED', f'All records during burn in standby.')

    # def check_man_006(self): DELETED
    #     records_6h_after_burn = self.xats.between('Time (UTC)', 
    #         self.burn_command_records[0]['Time (UTC)'],
    #         self.burn_command_records[0]['Time (UTC)'] + timedelta(hours=6)
    #         )
    #     standby_records_6h_after_burn = records_6h_after_burn.eq('Instrument Mode', 'standby')
    #     if len(standby_records_6h_after_burn) != len(records_6h_after_burn):
    #         self.get_rule('MAN-006').add_status_dispo('PASSED', f'Some records not in standby within 6h, therefore mode must have changed.')
    #     else:
    #         self.get_rule('MAN-006').add_status_dispo('FLAGGED', f'All records in standby within 6h, therefore mode must not have changed.')

    def check_man_007(self):
        nadir_cmds_after_burn = self.xats.eq('command', '@AC:select_mode NadirPointing').after(self.thrust_begin_time)
        first_nadir_time_after_burn = nadir_cmds_after_burn[0]['Time (UTC)']
        burn_to_nadir_time = (first_nadir_time_after_burn - self.thrust_begin_time).total_seconds()


        min_seconds = self.maneuver_client.maneuver_parameters['MAN_DUR_S'] + 120
        if burn_to_nadir_time < min_seconds:
            self.get_rule('MAN-007').add_status_dispo('VIOLATING', f'NADIR command occurs {burn_to_nadir_time}s after burn. Should be minimum of {min_seconds}s.')
        else:
            self.get_rule('MAN-007').add_status_dispo('PASSED', f'NADIR command occurs {burn_to_nadir_time}s after burn. Should be minimum of {min_seconds}s.')

    # def check_man_008(self): DELETED
    #     door_open_cmds_after_burn = self.xats.eq('command', '@rem:door_command CNTRL1, 9600').after(self.thrust_begin_time)
    #     first_door_open_time_after_burn = door_open_cmds_after_burn[0]['Time (UTC)']
    #     burn_to_door_open_time = (first_door_open_time_after_burn - self.thrust_begin_time).total_seconds()

    #     min_seconds = 300
    #     if burn_to_door_open_time < min_seconds:
    #         self.get_rule('MAN-008').add_status_dispo('VIOLATING', f'Door Open command occurs {burn_to_door_open_time}s after burn. Should be minimum of {min_seconds}s.')
    #     else:
    #         self.get_rule('MAN-008').add_status_dispo('PASSED', f'Door Open command occurs {burn_to_door_open_time}s after burn. Should be minimum of {min_seconds}s.')

    def check_man_009(self):
        eclipse_events_after_burn = self.xats.contains('command note', 'Eclipse E').after(self.thrust_begin_time)
        first_eclipse_event_after_burn = eclipse_events_after_burn[0]

        if first_eclipse_event_after_burn['Door Position'] == 'SOLAR':
            self.get_rule('MAN-009').add_status_dispo('PASSED', f'Door is in solar diffuser at next eclipse event after burn. This is safe.')
        elif first_eclipse_event_after_burn['ACS Mode'] == 'NADIR':
            self.get_rule('MAN-009').add_status_dispo('PASSED', f'Door is not in solar diffuser at next eclipse event after burn, but ACS is in NADIR. This is safe.')
        else:
            self.get_rule('MAN-009').add_status_dispo('VIOLATING', f'Door is not in solar diffuser and ACS mode is not NADIR at first eclipse event after burn. This is unsafe.')
        #Note that the NADIR branch of this (the second one above) isn't tested. Deemed low risk not to test since it's such a simple check
        #and many other rules depend on NADIR being reported in the way ART reports it.

    def check_man_010(self):
        thrust_commands = self.xats.eq('ACS Mode', 'THRUST')
        xats_after_burn_end = self.xats.after(thrust_commands[-1]['Time (UTC)'], inclusive=False)
        acs_mode_at_transition_out = xats_after_burn_end[0]['ACS Mode']
        if acs_mode_at_transition_out != 'THRUST --> NADIR':
            self.get_rule('MAN-010').add_status_dispo('VIOLATING', f'First slew after THRUST is "{acs_mode_at_transition_out}".')
        else:
            self.get_rule('MAN-010').add_status_dispo('PASSED', f'First slew after THRUST is to NADIR.')

