import pdb
from datetime import datetime, timedelta

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.text import Paragraph as P
from tts_html_utils.core.components.text import Heading1 as H1
from tts_html_utils.core.components.text import Heading2 as H2
from tts_html_utils.core.components.text import Heading4 as H4

# ===================================================================
# :: Checker Class
# ===================================================================

MINUTES_BETWEEN_CONTACT_STOP_AND_GLINT_MODE = 9
MINUTES_BETWEEN_CONTACT_STOP_AND_NADIR_MODE = 7
MINUTES_BETWEEN_DOOR_OPEN_AND_GLINT_START = 5
MINUTES_BETWEEN_GLINT_ATTITUDE_COMMAND_AND_GLINT_DATA_COLLECTION = 3
MINUTES_BETWEEN_DOOR_OPEN_AND_NADIR_START = 2

class TrollsatOrbit:
	def __init__(self, orbit_no, glint_orbits, expanded_ats_records, oef_client):
		self.orbit_no = orbit_no
		#Get all the Extended ATS records for just this orbit
		self.xats = expanded_ats_records.eq('Orbit #', orbit_no)
		self.xats_previous_orbit = expanded_ats_records.eq('Orbit #', orbit_no-1)
		
		self.is_glint_orbit = orbit_no in glint_orbits
		self.is_burn_orbit = len(self.xats.contains('ACS Mode', 'THRUST')) > 0
		self.is_nadir_orbit = not(self.is_glint_orbit) and not(self.is_burn_orbit)
		if self.is_burn_orbit:
			self.orbit_type = 'Burn'
		elif self.is_glint_orbit:
			self.orbit_type = 'Glint'
		else:
			self.orbit_type = 'Nadir'
		# self.expanded_ats_records = expanded_ats_records


		#find the AOS record for this orbit, assert there is exactly 1 record
		self.ats_record_aos = self.xats.contains('command note', 'AOS at', exactly=1)
		self.ats_record_los = self.xats.contains('command note', 'LOS at', exactly=1)
		#Get all the OEF records for just this orbit
		self.oef = oef_client.between('Time', oef_client.eq('orbit', orbit_no)[0]['Time']-timedelta(seconds=60*140), oef_client.eq('orbit', orbit_no)[-1]['Time'], inclusive='both')
		
	@property
	def aos_time(self):
		return self.ats_record_aos['Time (UTC)']

	@property
	def los_time(self):
		return self.ats_record_los['Time (UTC)']
 
class CheckerCheckTrollsat(CheckerBase):
	FR_IDS = [
		('TEL-001', 'a3ac6e33'),
		('TEL-002', 'a3ac6e33'),
		('TEL-003', '3ef6ed76'),
		('TEL-004', '3ef6ed76'),
		('TEL-005', '3ef6ed76'),
		('TEL-006', '3ef6ed76'),
		('TEL-007', '3ef6ed76'),
		('TEL-008', '3ef6ed76'),
		('TEL-009', '3ef6ed76'),
		('TEL-010', '3ef6ed76'),
		('TEL-011', '3ef6ed76'),
		('TEL-012', '3ef6ed76'),
		('TEL-013', '3ef6ed76'),
		('TEL-014', '3ef6ed76'),
		('TEL-015', '3ef6ed76'),
		# ('TEL-016', '1f8e34cc'), DELETED
		# ('TEL-017', '22cce1dd'), DELETED
		('TEL-018', '3ef6ed76'),
		# ('TEL-019', '1f8e34cc'),Downgraded to idio. Nothing to check anymore.
		# ('TEL-021', 'aa902f8c'), DELETED
	]

	INPUTS = [
		('expanded_ats', True),
		('oef', True),
        ('nephthys', True)
	]

	NAME = 'Trollsat Checks'
	def _impl_init(self, expanded_ats_records, oef_client, nephthys_client):
		self.name = 'Trollsat Checks'
		#Strictly I don't need this init, but I had played around with
		#different ways of making this code easier to read, and this
		#was part of the iteration before I created the TrollsatOrbit class
		#I'm going to leave it here because I changed the core to account
		#for this and I think that there might be other use cases out there
		self.glint_orbits = expanded_ats_records.get_glint_orbits()
		self.trollsat_orbits = [TrollsatOrbit(
									orbit_no, 
									self.glint_orbits, 
									expanded_ats_records, 
									oef_client
									) for orbit_no in expanded_ats_records.get_trollsat_orbits()]

	def oef_table_for_orbit(self, trollsat_orbit, subscribed_rules):
		title = f'Trollsat {trollsat_orbit.orbit_type} Orbit {trollsat_orbit.orbit_no}'
		header = H1(title)
		aos_time = H2(f'AOS: {trollsat_orbit.aos_time}')
		los_time = H2(f'LOS: {trollsat_orbit.los_time}')
		oef_records = trollsat_orbit.oef.records
		oef_table = trollsat_orbit.oef.power_table(f'{title} OEF Records')
		self.get_rule(subscribed_rules[0]).add_report('Trollsat Orbit OEFs', [header, aos_time, los_time, oef_table], append=True)

		for subscribed_rule in subscribed_rules:
			self.get_rule(subscribed_rule).add_report('Trollsat Orbit OEFs', [], append=True)

	def ats_table_for_orbit(self, trollsat_orbit, subscribed_rules):
		title = f'Trollsat {trollsat_orbit.orbit_type} Orbit {trollsat_orbit.orbit_no}'
		header = H1(title)
		aos_time = H2(f'AOS: {trollsat_orbit.aos_time}')
		los_time = H2(f'LOS: {trollsat_orbit.los_time}')
		expanded_ats_records = trollsat_orbit.xats
		expanded_ats_records = sorted(expanded_ats_records, key=lambda x: x['Time (UTC)'])

		xats_table = trollsat_orbit.xats.power_table(f'{title} Extended ATS Records')
		self.get_rule(subscribed_rules[0]).add_report('Trollsat Orbit xATSs', [header, aos_time, los_time, xats_table], append=True)

		for subscribed_rule in subscribed_rules:
			self.get_rule(subscribed_rule).add_report('Trollsat Orbit xATSs', [], append=True)


	def _impl_do_rulecheck(self, expanded_ats_records, oef_client, nephthys_client):
		self.expanded_ats_records = expanded_ats_records
		self.oef_client = oef_client
		self.nephthys_client = nephthys_client

		for trollsat_orbit in self.trollsat_orbits:
			#TO DO: Generalize this function. There's a lot of copy-paste in there
			self.oef_table_for_orbit(trollsat_orbit, ['TEL-001', 'TEL-002', 'TEL-003', 'TEL-004', 'TEL-005', 'TEL-006', 'TEL-007', 'TEL-008'])
			self.ats_table_for_orbit(trollsat_orbit, ['TEL-009', 'TEL-010', 'TEL-011', 'TEL-012', 'TEL-013', 'TEL-014', 'TEL-015'])
			self.check_rule_tel_001(trollsat_orbit, nephthys_client)
			self.check_rule_tel_002(trollsat_orbit, nephthys_client)
			self.check_rule_tel_003(trollsat_orbit, nephthys_client)
			self.check_rule_tel_004(trollsat_orbit, nephthys_client)
			self.check_rule_tel_005(trollsat_orbit, nephthys_client)
			self.check_rule_tel_006(trollsat_orbit, nephthys_client)
			self.check_rule_tel_007(trollsat_orbit, nephthys_client)
			self.check_rule_tel_008(trollsat_orbit, nephthys_client)
			self.check_rule_tel_009(trollsat_orbit, nephthys_client)
			self.check_rule_tel_010(trollsat_orbit, nephthys_client)
			self.check_rule_tel_011(trollsat_orbit, nephthys_client)
			self.check_rule_tel_012(trollsat_orbit, nephthys_client)
			self.check_rule_tel_013_through_16(trollsat_orbit, nephthys_client)
			# self.check_rule_tel_017(trollsat_orbit, nephthys_client) DELETED
			self.check_rule_tel_018(trollsat_orbit, nephthys_client)
			# self.check_rule_tel_019(trollsat_orbit, nephthys_client) #Converted to idio, nothing to check
			# self.check_rule_tel_021(trollsat_orbit, nephthys_client) DELETED
			
	def check_rule_tel_001(self, trollsat_orbit, nephthys_client):
		#Check if Floating Dark, Polar Cal, and Exlipse Exit removed from ANY orbits
		floating_dark_records = trollsat_orbit.oef.eq('Event', 'FloatingDarkCal')
		floating_dark_records_before_aos = floating_dark_records.between('Time', trollsat_orbit.aos_time-timedelta(seconds=50*60), trollsat_orbit.los_time)
		uncommented_records = floating_dark_records_before_aos.eq('Removed', False)

		if len(uncommented_records): 
			self.get_rule('TEL-001').add_status_dispo('VIOLATING', f'At least one uncommented Floating Dark event exists within 50 minutes before AOS in the OEF during Trollsat orbit #{trollsat_orbit.orbit_no}')
		else:
			self.get_rule('TEL-001').add_status_dispo('PASSED', f'All Floating Dark events within 50 minutes before start of Trollsat contact on orbit #{trollsat_orbit.orbit_no} commented out.')


	def check_rule_tel_002(self, trollsat_orbit, nephthys_client):
		polar_cal_records = trollsat_orbit.oef.eq('Event', 'PolarCalSequence')
		polar_cal_records_before_aos = polar_cal_records.between('Time', trollsat_orbit.aos_time-timedelta(seconds=50*60), trollsat_orbit.los_time)
		uncommented_records = polar_cal_records_before_aos.eq('Removed', False)
		if len(uncommented_records):
			self.get_rule('TEL-002').add_status_dispo('VIOLATING', f'At least one uncommented Polar Calibration event exists within 50 minutes before AOS in the OEF during Trollsat orbit #{trollsat_orbit.orbit_no}')
		else:
			self.get_rule('TEL-002').add_status_dispo('PASSED', f'All Polar Calibration events within 50 minutes before start of Trollsat contact on orbit #{trollsat_orbit.orbit_no} commented out.')

	def check_rule_tel_003(self, trollsat_orbit, nephthys_client):
		eclipse_exit_records = trollsat_orbit.oef.eq('Event', 'EclipseExit').eq('orbit', trollsat_orbit.orbit_no)
		uncommented_records = eclipse_exit_records.eq('Removed', False)

		if len(uncommented_records):
			self.get_rule('TEL-003').add_status_dispo('VIOLATING', f'At least one uncommented Eclipse Exit event exists in the OEF during Trollsat orbit #{trollsat_orbit.orbit_no}')
		else:
			self.get_rule('TEL-003').add_status_dispo('PASSED', f'All Eclipse Exit events commented out during Trollsat orbit #{trollsat_orbit.orbit_no}')

	def check_rule_tel_004(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_glint_orbit: 
			self.get_rule('TEL-004').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a GLINT orbit')
			return

		nadir_start_records = trollsat_orbit.oef.eq('Event', 'NadirModeSZAStart')
		uncommented_records_this_orbit = nadir_start_records.eq('Removed', False).eq('orbit', trollsat_orbit.orbit_no)
		#Check if Nadir Start/Stop are removed from all GLINT orbits
		if len(uncommented_records_this_orbit):
			self.get_rule('TEL-004').add_status_dispo('VIOLATING', f'At least one uncommented Nadir Start event exists in the OEF during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')
		else:
			self.get_rule('TEL-004').add_status_dispo('PASSED', f'All Nadir Start events commented out during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')

	def check_rule_tel_005(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_glint_orbit: 
			self.get_rule('TEL-005').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a GLINT orbit')
			return

		nadir_stop_records = trollsat_orbit.oef.eq('Event', 'NadirModeSZAStop')
		uncommented_records_this_orbit = nadir_stop_records.eq('Removed', False).eq('orbit', trollsat_orbit.orbit_no)

		if len(uncommented_records_this_orbit):
			self.get_rule('TEL-005').add_status_dispo('VIOLATING', f'At least one uncommented Nadir Stop event exists in the OEF during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')
		else:
			self.get_rule('TEL-005').add_status_dispo('PASSED', f'All Nadir Stop events commented out during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')	

	def check_rule_tel_006(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_nadir_orbit: 
			self.get_rule('TEL-006').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a NADIR orbit')
			return

		glint_start_records = trollsat_orbit.oef.eq('Event', 'GlintModeSZAStart').eq('orbit', trollsat_orbit.orbit_no)
		uncommented_records_this_orbit = glint_start_records.eq('Removed', False)
		#Check if Glint Start/Stop are removed from all NADIR orbits
		if len(uncommented_records_this_orbit):
			datetimes = [datetime.strftime(x["Time"], '%Y/%m/%dT%H:%M:%S.%f') for x in glint_start_records.records]
			self.get_rule('TEL-006').add_status_dispo('VIOLATING', f'Uncommented Glint Start event(s) exist in the OEF during Trollsat NADIR orbit #{trollsat_orbit.orbit_no} at times: {datetimes}')
		else:
			self.get_rule('TEL-006').add_status_dispo('PASSED', f'All Glint Start events commented out during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}')

	def check_rule_tel_007(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_nadir_orbit: 
			self.get_rule('TEL-007').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a NADIR orbit')
			return

		glint_stop_records = trollsat_orbit.oef.eq('Event', 'GlintModeSZAStop').eq('orbit', trollsat_orbit.orbit_no)
		uncommented_records_this_orbit = glint_stop_records.eq('Removed', False)
		if len(uncommented_records_this_orbit):
			datetimes = [datetime.strftime(x["Time"], '%Y/%m/%dT%H:%M:%S.%f') for x in uncommented_records_this_orbit.records]
			self.get_rule('TEL-007').add_status_dispo('VIOLATING', f'Uncommented Glint Stop event(s) exist in the OEF during Trollsat NADIR orbit #{trollsat_orbit.orbit_no} at times: {datetimes}')
		else:
			self.get_rule('TEL-007').add_status_dispo('PASSED', f'All Glint Stop events commented out during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}')


	def check_rule_tel_008(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_glint_orbit: 
			self.get_rule('TEL-008').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a GLINT orbit')
			return

		glint_start_xats_record = trollsat_orbit.xats.contains('command note', 'Start glint data collection')
		if len(glint_start_xats_record) == 1:
			acs_in_glint = glint_start_xats_record[0]['ACS Mode'] == 'GLINT'
			door_open = glint_start_xats_record[0]['Door Position'] == 'OPEN'
			if acs_in_glint and door_open:
				self.get_rule('TEL-008').add_status_dispo('PASSED', f'Glint observation begins with door open and ACS in glint mode during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')
			elif not acs_in_glint and not door_open:
				self.get_rule('TEL-008').add_status_dispo('VIOLATING', f'Glint observation begins with door *NOT* open and ACS *NOT* in glint mode during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')
			elif not acs_in_glint:
				self.get_rule('TEL-008').add_status_dispo('VIOLATING', f'Glint observation begins with ACS *NOT* in glint mode during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')
			elif not door_open:
				self.get_rule('TEL-008').add_status_dispo('VIOLATING', f'Glint observation begins with door *NOT* open during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}')
			else:
				self.get_rule('TEL-008').add_status_dispo('FLAGGED', f'How did I get here?')
			#Note, these last three branches above are untested, but deemed OK not to be as they made testing
			#significantly more complex and are logically very similar to the branches that are tested
				
		else:
			self.get_rule('TEL-008').add_status_dispo('FLAGGED', f'Incorrect number of glint start records during Trollsat GLINT orbit #{trollsat_orbit.orbit_no}. Please check manually because there\'s probably something wrong with Tower.')


	def check_rule_tel_009(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_glint_orbit:
			self.get_rule('TEL-009').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a GLINT orbit')
			return

		glint_start_records = trollsat_orbit.oef.eq('Event', 'GlintModeSZAStart').eq('Removed', False).eq('orbit', trollsat_orbit.orbit_no)
		door_commands = trollsat_orbit.xats.contains('command', 'door_command').eq('Orbit #', trollsat_orbit.orbit_no)
		abs_door_commands = door_commands.eq('Event Type', 'ABS')

		#Note, these first two are untested, but deemed OK not to be as they made testing
		#significantly more complex and are highly unlikely to ever happen in isolation
		#(e.g. they will cause other problems of their own)
		if len(glint_start_records) != 1:
			self.get_rule('TEL-009').add_status_dispo('FLAGGED', f'Should be exactly 1 glint command per glint orbit. Found {len(glint_start_records)} on orbit {trollsat_orbit.orbit_no}.')
		elif len(abs_door_commands) != 1:
			self.get_rule('TEL-009').add_status_dispo('FLAGGED', f'Should be exactly 1 door open command per glint orbit. Found {len(abs_door_commands)} on orbit {trollsat_orbit.orbit_no}.')
		elif (glint_start_records[0]['Time'] - abs_door_commands[0]['Time (UTC)']).total_seconds() < MINUTES_BETWEEN_DOOR_OPEN_AND_GLINT_START*60:
			self.get_rule('TEL-009').add_status_dispo('VIOLATING', f'Glint collection begins less than {MINUTES_BETWEEN_DOOR_OPEN_AND_GLINT_START} minutes after door command on orbit {trollsat_orbit.orbit_no}.')
		else:
			self.get_rule('TEL-009').add_status_dispo('PASSED', f'Glint collection begins at least {MINUTES_BETWEEN_DOOR_OPEN_AND_GLINT_START} minutes after door command on orbit {trollsat_orbit.orbit_no}.')

	def check_rule_tel_010(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_glint_orbit: 
			self.get_rule('TEL-010').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a GLINT orbit')
			return

		glint_start_records = trollsat_orbit.oef.eq('Event', 'GlintModeSZAStart').eq('Removed', False).eq('orbit', trollsat_orbit.orbit_no)
		#needs to be contains and not eq because there's whitespace :-(
		slew_to_glint_records = trollsat_orbit.xats.contains('command note', 'Slew to glint').eq('Orbit #', trollsat_orbit.orbit_no)


		#Note, these first two are untested, but deemed OK not to be as they made testing
		#significantly more complex and are highly unlikely to ever happen in isolation
		#(e.g. they will cause other problems of their own)
		if len(glint_start_records) != 1:
			self.get_rule('TEL-010').add_status_dispo('FLAGGED', f'Should be exactly 1 glint command per glint orbit. Found {len(glint_start_records)} on orbit {trollsat_orbit.orbit_no}.')
		elif len(slew_to_glint_records) != 1:
			self.get_rule('TEL-010').add_status_dispo('FLAGGED', f'Should be exactly 1 slew to glint command per glint orbit. Found {len(slew_to_glint_records)} on orbit {trollsat_orbit.orbit_no}.')
		elif (glint_start_records[0]['Time'] - slew_to_glint_records[0]['Time (UTC)']).total_seconds() < MINUTES_BETWEEN_GLINT_ATTITUDE_COMMAND_AND_GLINT_DATA_COLLECTION*60:
			self.get_rule('TEL-010').add_status_dispo('VIOLATING', f'Glint collection begins less than {MINUTES_BETWEEN_GLINT_ATTITUDE_COMMAND_AND_GLINT_DATA_COLLECTION} minutes after commanding to glint attitude on orbit {trollsat_orbit.orbit_no}.')
		else:
			self.get_rule('TEL-010').add_status_dispo('PASSED', f'Glint collection begins at least {MINUTES_BETWEEN_GLINT_ATTITUDE_COMMAND_AND_GLINT_DATA_COLLECTION} minutes after commanding to glint attitude on orbit {trollsat_orbit.orbit_no}.')

	def check_rule_tel_011(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_nadir_orbit: 
			self.get_rule('TEL-011').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a NADIR orbit')
			return

		nadir_start_xats_record = trollsat_orbit.xats.contains('command note', 'Start nadir data collection')
		if len(nadir_start_xats_record) == 1:
			acs_in_nadir = nadir_start_xats_record[0]['ACS Mode'] == 'NADIR'
			door_open = nadir_start_xats_record[0]['Door Position'] == 'OPEN'
			if acs_in_nadir and door_open:
				self.get_rule('TEL-011').add_status_dispo('PASSED', f'Nadir observation begins with door open and ACS in nadir mode during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}')
			elif not acs_in_nadir and not door_open:
				self.get_rule('TEL-011').add_status_dispo('VIOLATING', f'Nadir observation begins with door *NOT* open and ACS *NOT* in nadir mode during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}')
			elif not acs_in_nadir:
				self.get_rule('TEL-011').add_status_dispo('VIOLATING', f'Nadir observation begins with ACS *NOT* in nadir mode during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}')
			elif not door_open:
				self.get_rule('TEL-011').add_status_dispo('VIOLATING', f'Nadir observation begins with door *NOT* open during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}')
			else:
				self.get_rule('TEL-011').add_status_dispo('FLAGGED', f'How did I get here?')
			#Note, these last three branches above are untested, but deemed OK not to be as they made testing
			#significantly more complex and are logically very similar to the branches that are tested
			#Note taht we also don't test the single failure branches. Only if both fail. But between the added complexity of the test and the little gain in testing robustness there due
			#to the very simple logic above, we deemed it to be worth the risk.
				
		else:
			self.get_rule('TEL-011').add_status_dispo('FLAGGED', f'Incorrect number of nadir start records during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}. Please check manually because there\'s probably something wrong with Tower.')

	def check_rule_tel_012(self, trollsat_orbit, nephthys_client):
		if not trollsat_orbit.is_nadir_orbit: 
			self.get_rule('TEL-012').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a NADIR orbit')
			return

		nadir_mode_start_records = trollsat_orbit.oef.eq('Event', 'NadirModeSZAStart').eq('Removed', False).eq('orbit', trollsat_orbit.orbit_no)
		door_commands = trollsat_orbit.xats.contains('command', 'door_command').eq('Orbit #', trollsat_orbit.orbit_no)
		abs_door_commands = door_commands.eq('Event Type', 'ABS')

		#Note, these first two are untested, but deemed OK not to be as they made testing
		#significantly more complex and are highly unlikely to ever happen in isolation
		#(e.g. they will cause other problems of their own)
		if len(abs_door_commands) == 0:
			self.get_rule('TEL-012').add_status_dispo('FLAGGED', f'No door open commands from ABS during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}. TEL-012 assumes exactly 1')
		elif len(abs_door_commands) > 1:
			self.get_rule('TEL-012').add_status_dispo('FLAGGED', f'More than one open command from ABS during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}. TEL-012 assumes exactly 1')
		elif len(nadir_mode_start_records) != 1:
			self.get_rule('TEL-012').add_status_dispo('FLAGGED', f'{nadir_mode_start_records} nadir command(s) from ABS during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}. TEL-012 assumes exactly 1')
		elif (nadir_mode_start_records[0]['Time'] - abs_door_commands[0]['Time (UTC)']).total_seconds() < MINUTES_BETWEEN_DOOR_OPEN_AND_NADIR_START*60:
			self.get_rule('TEL-012').add_status_dispo('VIOLATING', f'Door open command starts less than {MINUTES_BETWEEN_DOOR_OPEN_AND_NADIR_START} minutes before nadir mode start during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}.')
		else:
			self.get_rule('TEL-012').add_status_dispo('PASSED', f'Door open command starts greater than or equal to {MINUTES_BETWEEN_DOOR_OPEN_AND_NADIR_START} minutes before nadir mode start during Trollsat NADIR orbit #{trollsat_orbit.orbit_no}.')


	def check_rule_tel_013_through_16(self, trollsat_orbit, nephthys_client):
		if trollsat_orbit.xats[0]['command note'] == 'Descending Node Crossing':
			if trollsat_orbit.xats[0]['ACS Mode'] == 'NADIR':
				self.get_rule('TEL-013').add_status_dispo('PASSED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} begins in NADIR mode as expected.')
			else:
				self.get_rule('TEL-013').add_status_dispo('VIOLATING', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin in NADIR mode.')					

			if trollsat_orbit.xats[0]['Instrument Mode'] == 'standby':
				self.get_rule('TEL-014').add_status_dispo('PASSED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} begins in standby mode as expected.')
			else:
				self.get_rule('TEL-014').add_status_dispo('VIOLATING', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin in standby mode.')					

			if trollsat_orbit.xats[0]['Door Position'] == 'SOLAR':
				self.get_rule('TEL-015').add_status_dispo('PASSED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} begins in SOLAR mode as expected.')
			else:
				self.get_rule('TEL-015').add_status_dispo('VIOLATING', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin in SOLAR mode.')					

			# DELETED
			# if trollsat_orbit.xats[0]['Lamp Status'] == 'Lamps OFF':
			# 	self.get_rule('TEL-016').add_status_dispo('PASSED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} begins in Lamps Off mode as expected.')
			# else:
			# 	self.get_rule('TEL-016').add_status_dispo('VIOLATING', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin in Lamps Off mode.')					

		else:
			#This is in here as a hedge. I'm not sure it has to be in here, but 
			#until I understand expanded ATSs a bit more, it'll stay.
			#If it creates too much noise, then we can take a closer look at this guy.
			self.get_rule('TEL-013').add_status_dispo('FLAGGED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin with a descending node crossing.')
			self.get_rule('TEL-014').add_status_dispo('FLAGGED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin with a descending node crossing.')
			self.get_rule('TEL-015').add_status_dispo('FLAGGED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin with a descending node crossing.')
			# DELETED
			# self.get_rule('TEL-016').add_status_dispo('FLAGGED', f'Trollsat orbit #{nephthys_client.get_orbit_sub_page_anchor(trollsat_orbit.orbit_no)} does not begin with a descending node crossing.')

	# def check_rule_tel_017(self, trollsat_orbit, nephthys_client): DELETED
	# 	#Note, I think we may be able to remove this rule in favor of the one
	# 	#that says we need to be in Nadir by DN. Think on that.
	# 	previous_orbit_glint_records = trollsat_orbit.xats_previous_orbit.eq('ACS Mode', 'GLINT')
	# 	previous_orbit_xband_rts_records = trollsat_orbit.xats_previous_orbit.isin('Event Type', ['RTS #80','RTS #81'])
	# 	previous_orbit_nadir_records = trollsat_orbit.xats_previous_orbit.eq('command', '@AC:select_mode NadirPointing')
	# 	previous_orbit_nadir_records_abs = previous_orbit_nadir_records.eq('Event Type', 'ABS')
	# 	previous_orbit_target_records = trollsat_orbit.xats_previous_orbit.contains('command note', 'Begin target')

	# 	self.get_rule('TEL-017').add_status_dispo('FLAGGED', f'Consider for removal. This seems redundant to other rules we already have here')

	# 	if len(previous_orbit_glint_records) == 0:
	# 		self.get_rule('TEL-017').add_status_dispo('PASSED', f'Orbit prior to {trollsat_orbit.orbit_no} was not a glint orbit.')
	# 	elif len(previous_orbit_xband_rts_records) != 0:
	# 		self.get_rule('TEL-017').add_status_dispo('PASSED', f'Orbit prior to {trollsat_orbit.orbit_no} had an X-band contact and does not need ABS Nadir command.')
	# 	elif len(previous_orbit_nadir_records_abs) == 1:
	# 		self.get_rule('TEL-017').add_status_dispo('PASSED', f'One NADIR command from ABS orbit prior to trollsat orbit {trollsat_orbit.orbit_no}')
	# 	elif len(previous_orbit_nadir_records) and len(previous_orbit_target_records) and trollsat_orbit.xats_previous_orbit[-1]['ACS Mode'] == 'NADIR':
	# 		self.get_rule('TEL-017').add_status_dispo('PASSED', f'No ABS NADIR command on {trollsat_orbit.orbit_no}, but there is a target, which should puts us in Nadir afterwards.')
	# 		self.get_rule('TEL-017').add_status_dispo('PASSED', f'No ABS NADIR command on {trollsat_orbit.orbit_no}, but we also hedge and make sure descending note is in Nadir here.')
	# 	elif len(previous_orbit_nadir_records_abs) > 1:
	# 		self.get_rule('TEL-017').add_status_dispo('VIOLATING', f'Multiple NADIR commands from ABS orbit prior to trollsat orbit {trollsat_orbit.orbit_no}')
	# 	else:
	# 		self.get_rule('TEL-017').add_status_dispo('VIOLATING', f'No NADIR commands from ABS orbit prior to trollsat orbit {trollsat_orbit.orbit_no}')

	def check_rule_tel_018(self, trollsat_orbit, nephthys_client):
		door_open_records = trollsat_orbit.xats.eq('command', '@rem:door_command CNTRL1, 9600')
		door_open_abs_records = door_open_records.eq('Event Type', 'ABS')

		if len(door_open_abs_records) == 0:
			self.get_rule('TEL-018').add_status_dispo('VIOLATING', f'No door open command from ABS in trollsat orbit {trollsat_orbit.orbit_no}')
		elif len(door_open_abs_records) > 1:
			self.get_rule('TEL-018').add_status_dispo('VIOLATING', f'More than one door open command from ABS in trollsat orbit {trollsat_orbit.orbit_no}')
		else:
			self.get_rule('TEL-018').add_status_dispo('PASSED', f'One door open command from ABS in trollsat orbit {trollsat_orbit.orbit_no}')

	# Downgraded to idio. Nothing to check anymore.
	# def check_rule_tel_019(self, trollsat_orbit, nephthys_client):
	# 	if not trollsat_orbit.is_nadir_orbit: 
	# 		self.get_rule('TEL-019').add_status_dispo('PASSED', f'Trollsat orbit #{trollsat_orbit.orbit_no} is not a NADIR orbit')
	# 		return

	# 	door_open_records = trollsat_orbit.xats.eq('command', '@rem:door_command CNTRL1, 9600')
	# 	door_open_abs_records = door_open_records.eq('Event Type', 'ABS')

	# 	for door_open_abs_record in door_open_abs_records:
	# 		if door_open_abs_record['ACS Mode'] == 'NADIR':
	# 			self.get_rule('TEL-019').add_status_dispo('PASSED', f'ACS Mode is NADIR for ABS door open command on trollsat orbit {trollsat_orbit.orbit_no}')
	# 		else:
	# 			self.get_rule('TEL-019').add_status_dispo('VIOLATING', f'ACS Mode is NOT NADIR for ABS door open command on trollsat orbit {trollsat_orbit.orbit_no}')


	# def check_rule_tel_021(self, trollsat_orbit, nephthys_client): DELETED

	# 	rts_80_records_last_orbit = trollsat_orbit.xats_previous_orbit.eq('Event Type', 'RTS #80')
		
	# 	if rts_80_records_last_orbit:
	# 		los_time = trollsat_orbit.xats_previous_orbit.contains('command note', 'LOS at', exactly=1)['Time (UTC)']
	# 		slew_to_nadir_records = trollsat_orbit.xats_previous_orbit.after(los_time).contains('command note', 'slew to nadir')
	# 		if len(slew_to_nadir_records):
	# 			self.get_rule('TEL-021').add_status_dispo('PASSED', f'Nadir slew occurs between LOS and Descending note on orbit with X-Band found prior to trollsat orbit {trollsat_orbit.orbit_no}.')
	# 		else:
	# 			self.get_rule('TEL-021').add_status_dispo('VIOLATING', f'No nadir slew between LOS and Descending note on orbit with X-Band found prior to trollsat orbit {trollsat_orbit.orbit_no}.')
	# 	else:
	# 		self.get_rule('TEL-021').add_status_dispo('PASSED', f'No X-Band on orbit prior to trollsat orbit {trollsat_orbit.orbit_no}')


