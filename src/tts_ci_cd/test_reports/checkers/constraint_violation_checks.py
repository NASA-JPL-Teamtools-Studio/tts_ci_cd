import pdb
from datetime import datetime

from tts_tower.checkers.checker_base import CheckerBase
from tts_tower.rule_results import RULE_REVISION_SPECIAL
from tts_html_utils.core.components.misc import Link
from tts_html_utils.core.components.text import Pre
from tts_html_utils.core.components.text import Paragraph as P
from tts_html_utils.core.components.text import Heading2 as H2


# ===================================================================
# :: Checker Class
# ===================================================================
class CheckerConstraintViolations(CheckerBase):
	FR_IDS = [
		('OCO-ABS-001', '3ef6ed76'),
		('OCO-ABS-002', '3ef6ed76'),
		('OCO-ABS-003', '3ef6ed76'),
		('OCO-AC-001',  '3ef6ed76'),
		('OCO-AC-002',  '3ef6ed76'),
		('OCO-AC-003',  '3ef6ed76'),
		('OCO-AC-004',  '3ef6ed76'),
		('OCO-AC-005',  '3ef6ed76'),
		('OCO-AC-006',  '3ef6ed76'),
		('OCO-AC-007',  '3ef6ed76'),
		('OCO-AC-008',  '3ef6ed76'),
		('OCO-AC-009',  '3ef6ed76'),
		('OCO-AC-010',  '3ef6ed76'),
		('OCO-INS-001', '3ef6ed76'),
		('OCO-INS-002', '3ef6ed76'),
		('OCO-INS-003', '3ef6ed76'),
		('OCO-INS-004', '3ef6ed76'),
		('OCO-INS-005', '3ef6ed76'),
		('OCO-INS-006', '3ef6ed76'),
		('OCO-INS-007', '3ef6ed76'),
		('OCO-INS-008', '3ef6ed76'),
		('OCO-INS-009', '3ef6ed76'),
		('OCO-INS-010', '3ef6ed76'),
		('OCO-INS-011', '3ef6ed76'),
		('OCO-INS-012', '3ef6ed76'),
		('OCO-INS-013', '3ef6ed76'),
		('OCO-INS-014', '3ef6ed76'),
		('OCO-INS-015', '3ef6ed76'),
		('OCO-INS-016', '3ef6ed76'),
		('OCO-INS-017', '3ef6ed76'),
		('OCO-INS-018', '3ef6ed76'),
		('OCO-INS-019', '3ef6ed76'),
		('OCO-INS-020', '3ef6ed76'),
		('OCO-INS-021', '3ef6ed76'),
		('OCO-INS-022', '3ef6ed76'),
		('OCO-INS-023', '3ef6ed76'),
		('OCO-INS-024', '3ef6ed76'),
		('OCO-INS-025', '3ef6ed76'),
		('OCO-INS-026', '3ef6ed76'),
		('OCO-INS-027', '3ef6ed76'),
		('OCO-INS-028', '3ef6ed76'),
		('OCO-INS-029', '3ef6ed76'),
		('OCO-INS-030', 'a3ac6e33'),
		('OCO-INS-031', 'a3ac6e33'),
	]

	INPUTS = [
		('violations_table', True),
        ('acvr', True),
        ('ccvr', True),
        ('expanded_ats', True),
        ('nephthys', True),
	]

	def _impl_init(self, violations_table_client, acvr_client, ccvr_client, expanded_ats_client, nephthys_client):
		pass

	def _impl_do_rulecheck(self, violations_table_client, acvr_client, ccvr_client, expanded_ats_client, nephthys_client):
		self.violations_table_client = violations_table_client
		self.acvr_client = acvr_client
		self.ccvr_client = ccvr_client
		self.expanded_ats_client = expanded_ats_client


		nephthys_link = Link('Nephthys Violations', nephthys_client.get_ats_report_link())
		nephthys_violations_table = self.violations_table_client.power_table('Nephthys Violations')
		self.get_rule(self.FR_IDS[0][0]).add_report('Nephthys/ACVR/CCVR', [nephthys_link, nephthys_violations_table], append=True)

		ccvr_link = Link(nephthys_client.get_raw_file_link(self.ccvr_client.filepath.name))
		self.get_rule(self.FR_IDS[0][0]).add_report('Nephthys/ACVR/CCVR', [H2(ccvr_client.filepath), ccvr_link, Pre(ccvr_client.file_contents_as_string())], append=True)

		acvr_link = Link(nephthys_client.get_raw_file_link(self.acvr_client.filepath.name))
		self.get_rule(self.FR_IDS[0][0]).add_report('Nephthys/ACVR/CCVR', [H2(acvr_client.filepath), acvr_link, Pre(acvr_client.file_contents_as_string())], append=True)


		for rule in self.FR_IDS:
			self.get_rule(rule[0]).add_report('Nephthys/ACVR/CCVR', [], append=True)

		self.check_oco_ac_010()
		self.check_acvr()
		self.check_ccvr()
		self.check_nephthys()


	def check_oco_ac_010(self):
		for orbit in [r['Orbit Number'] for r in self.violations_table_client.eq(self.violations_table_client.violation_id_label, 'OCO-AC-010')]:
			xats_this_orbit = self.expanded_ats_client.eq('Orbit #', orbit)
			begin_target_records = xats_this_orbit.contains('command note', 'Begin target')
			if len(begin_target_records):
				self.get_rule('OCO-AC-010').add_status_dispo('VIOLATING', f'{len(begin_target_records)} target(s) found on orbit {orbit}. Should be no targets on orbits with OCO-AC-010 violations')
			else:
				self.get_rule('OCO-AC-010').add_status_dispo('PASSED', f'Orbit {orbit} has glint spot violation (OCO-AC-010), but no targets found on orbit.')

 
	def check_acvr(self):
		for rule in self.FR_IDS:
			rule_id = rule[0]
			if len(self.acvr_client.eq('Rule ID', rule_id)):
				if rule_id == 'OCO-AC-008':
					self.get_rule(rule_id).add_status_dispo('PASSED', f'{rule_id} found in ACVR, but is only a problem if flagged by ART in the Nephthys violation table, which is in the violation table check.')
				elif rule_id == 'OCO-AC-010':
					self.get_rule(rule_id).add_status_dispo('PASSED', f'{rule_id} found in ACVR, but is only a problem if associated targets are not removed, which is checked elsewhere')
				else:
					self.get_rule(rule_id).add_status_dispo('VIOLATING', f'{rule_id} found in ACVR')
			else:
				self.get_rule(rule_id).add_status_dispo('PASSED', f'{rule_id} not found in ACVR')

	def check_ccvr(self):
		for rule in self.FR_IDS:
			rule_id = rule[0]
			if len(self.ccvr_client.hard_violations):
				self.get_rule(rule_id).add_status_dispo('FLAGGED', f'No confirmation of no hard violations in CCVR. TOWER check is weak, so manual check of CCVR is needed.')
			elif len(self.ccvr_client.soft_violations):
				self.get_rule(rule_id).add_status_dispo('FLAGGED', f'No confirmation of no soft violations in CCVR. TOWER check is weak, so manual check of CCVR is needed.')
			elif len(self.ccvr_client.other_messages):
				self.get_rule(rule_id).add_status_dispo('FLAGGED', f'No confirmation of no other messages in CCVR. TOWER check is weak, so manual check of CCVR is needed.')
			elif len(self.ccvr_client.unexpected_lines):
				self.get_rule(rule_id).add_status_dispo('FLAGGED', f'Found unexpected lines in CCVR. TOWER check is weak, so manual check of CCVR is needed.')
			else:
				self.get_rule(rule_id).add_status_dispo('PASSED', f'{rule_id} not found in CCVR')

	def check_nephthys(self):
		for rule in self.FR_IDS:
			rule_id = rule[0]
			if len(self.violations_table_client.eq(self.violations_table_client.violation_id_label, rule_id)):
				if rule_id in ['OCO-AC-010']:
					self.get_rule(rule_id).add_status_dispo('PASSED', f'{rule_id} found in Nephthys violation table, but is only a problem if associated targets are not removed, which is checked elsewhere')
				else:
					self.get_rule(rule_id).add_status_dispo('VIOLATING', f'{rule_id} found in Nephthys violation table')
			else:
				self.get_rule(rule_id).add_status_dispo('PASSED', f'{rule_id} not found in Nephthys violation table')
