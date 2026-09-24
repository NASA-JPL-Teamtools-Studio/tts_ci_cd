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
		# ('TEL-023', 'aa902f8c'), DELETED
		# ('TEL-024', 'aa902f8c'), DELETED
		('TEL-025', '3ef6ed76'),
		('TEL-026', '3ef6ed76'),
	]

	INPUTS = [
		('expanded_ats', True),
        ('nephthys', True)
	]
	NAME = 'X Band Checks'

	def _impl_init(self, expanded_ats_client, nephthys_client):
		pass

	def _impl_do_rulecheck(self, expanded_ats_client, nephthys_client):
		self.expanded_ats_client = expanded_ats_client
		x_band_orbits = expanded_ats_client.get_x_band_orbits()
		for x_band_orbit in x_band_orbits:
			xats_this_orbit = expanded_ats_client.eq('Orbit #', x_band_orbit)
			# self.check_rule_tel_023(expanded_ats_client, nephthys_client, x_band_orbit, xats_this_orbit) DELETED
			# self.check_rule_tel_024(expanded_ats_client, nephthys_client, x_band_orbit, xats_this_orbit) DELETED
			self.check_rule_tel_025(expanded_ats_client, nephthys_client, x_band_orbit, xats_this_orbit)

	# def check_rule_tel_023(self, expanded_ats_client, nephthys_client, x_band_orbit, xats_this_orbit): DELETED
	# 	rts_80_records = xats_this_orbit.eq('Event Type', 'RTS #80')
	# 	rts_80_dl_records = rts_80_records.ne('ACS Mode', 'DOWNLINK')

	# 	if len(rts_80_records) != 13:
	# 		self.get_rule('TEL-023').add_status_dispo('FLAGGED', f'Unexpected number of RTS 80 commands on orbit #{x_band_orbit}') #56069
	# 	elif len(rts_80_dl_records) != 0:
	# 		self.get_rule('TEL-023').add_status_dispo('VIOLATING', f'Some RTS #80 commands issued not in downlink mode on orbit #{x_band_orbit}') #56071
	# 	else:
	# 		self.get_rule('TEL-023').add_status_dispo('PASSED', f'All RTS #80 commands occur in downlink mode on orbit #{x_band_orbit}')


	# def check_rule_tel_024(self, expanded_ats_client, nephthys_client, x_band_orbit, xats_this_orbit): DELETED
	# 	los_record = xats_this_orbit.contains('command note', 'LOS at', exactly=1)

	# 	#strictly this doesn't get if we go out of DL and back all within a contact, but that's
	# 	#a very unlikely corner case. TBD if we address it here
	# 	if los_record['ACS Mode'] != 'DOWNLINK':
	# 		self.get_rule('TEL-024').add_status_dispo('VIOLATING', f'LOS in a mode other than downlink on orbit #{x_band_orbit}') #56083
	# 	else:
	# 		self.get_rule('TEL-024').add_status_dispo('PASSED', f'OCO-2 does not leave downlink mode before LOS on orbit #{x_band_orbit}')

	def check_rule_tel_025(self, expanded_ats_client, nephthys_client, x_band_orbit, xats_this_orbit):
		acceptable_event_types = ['RTS #80', 'CAF', 'OEF']

		aos_time = xats_this_orbit.contains('command note', 'AOS at', exactly=1)['Time (UTC)']
		los_time = xats_this_orbit.contains('command note', 'LOS at', exactly=1)['Time (UTC)']
		xats_during_contact = xats_this_orbit.between('Time (UTC)', aos_time, los_time)
		unacceptable_events = xats_during_contact.notin('Event Type', acceptable_event_types)
		# if 'violating' in str(self.expanded_ats_client.filepath): pdb.set_trace()
		if len(unacceptable_events):
			#56085
			self.get_rule('TEL-025').add_status_dispo('VIOLATING', f'Unexpected commands occur during contact on orbit #{nephthys_client.get_orbit_sub_page_anchor(x_band_orbit)}')
		else:
			self.get_rule('TEL-025').add_status_dispo('PASSED', f'All commands during contact on orbit #{nephthys_client.get_orbit_sub_page_anchor(x_band_orbit)} of expected types: {acceptable_event_types}')


		first_rts_8x_command_time = xats_this_orbit.contains('Event Type', 'RTS #8')[0]['Time (UTC)']
		#TO DO: Move this out of here like we did with Trollsat checks
		xats_table = xats_this_orbit.between('Time (UTC)', first_rts_8x_command_time, los_time).power_table(f'xATS records for X-Band Orbit #{x_band_orbit}')
		self.get_rule('TEL-025').add_report('Commands During X-Band', H2(f'X-Band Orbit #{x_band_orbit}'), append=True)
		self.get_rule('TEL-025').add_report('Commands During X-Band', xats_table, append=True)

		# self.get_rule('TEL-023').add_report('Commands During X-Band', [], append=True) DELETED
		# self.get_rule('TEL-024').add_report('Commands During X-Band', [], append=True) DELETED





