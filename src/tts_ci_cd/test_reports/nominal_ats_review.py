#!/usr/bin/env python3
from pathlib import Path
import argparse
import pdb
import pandas as pd
from datetime import datetime
import getpass
import os
import sys
import subprocess

from oco2t import OCO2_Tower
import input_clients.unit_test_registry
import input_clients.rule_dictionary
from tts_tower.split_logging import log_to_file
from tts_tower.inputs.input_manager import input_get
from tts_utilities.logger import create_logger

LOG_FNAME = './nominal_ats_review.log'
logger = create_logger('nominal_ats_review')


def tower_check(module):

    oco2_tower = OCO2_Tower()

    #This comes first as a workaround for run_info because we don't need anything from last_week_ats right now
    oco2_tower.add_input_client('unit_test_registry',     input_clients.unit_test_registry.UnitTestRegistryClient, [module])
    oco2_tower.add_input_client('rule_dictionary',        input_clients.rule_dictionary.RuleDictionaryClient,       [])

    # oco2_tower.add_input_client('odf',                  input_clients.OrbitDesignationClient,     [input_get('week_directory')])
    # oco2_tower.add_input_client('nephthys',             input_clients.NephthysClient,             [Path(this_week_directory).name])
    # oco2_tower.add_input_client('acvr',                 input_clients.AttitudeConstraintClient,   [input_get('week_directory')])
    # oco2_tower.add_input_client('ccvr',                 input_clients.ComandLoadConstraintClient, [input_get('week_directory')])
    # oco2_tower.add_input_client('car',                  input_clients.CarClient,                  [input_get('week_directory')])
    # oco2_tower.add_input_client('oef',                  input_clients.OrbitEventsClient,          [input_get('week_directory')])
    # oco2_tower.add_input_client('scr',                  input_clients.RawAtsClient,               [input_get('week_directory')])
    # oco2_tower.add_input_client('expanded_ats',         input_clients.ExpandedAtsClient,          [input_get('week_directory'), input_get('odf'), True])
    # oco2_tower.add_input_client('abs',                  input_clients.AbsoluteCommandClient,      [input_get('week_directory')])
    # oco2_tower.add_input_client('mnvr',                 input_clients.ManeuverCommandClient,      [input_get('week_directory')])
    # oco2_tower.add_input_client('lnr',                  input_clients.LunarCommandClient,         [input_get('week_directory')])
    # oco2_tower.add_input_client('violations_table',     input_clients.ViolationsTableClient,      [input_get('week_directory')])
    # oco2_tower.add_input_client('mpst_team',            input_clients.MpstTeam,                   [])
    # oco2_tower.add_input_client('last_week_directory',  input_clients.WeekDirectoryClient,        [last_week_directory, None])
    # oco2_tower.add_input_client('last_expanded_ats',    input_clients.ExpandedAtsClient,          [input_get('last_week_directory'), input_get('odf'), False])
    # oco2_tower.add_input_client('switch_buffer',        input_clients.SwitchBufferClient,         [input_get('last_week_directory'), input_get('week_directory'), input_get('expanded_ats'), input_get('last_expanded_ats')])


    # oco2_tower.add_checker('oco2_tower.checkers.misc_rules')
    # oco2_tower.add_checker('oco2_tower.checkers.constraint_violation_checks')
    # oco2_tower.add_checker('oco2_tower.checkers.lunar_calibrations')
    # oco2_tower.add_checker('oco2_tower.checkers.maneuvers')
    # oco2_tower.add_checker('oco2_tower.checkers.rad_trend_checks')
    # oco2_tower.add_checker('oco2_tower.checkers.review_docx_writer')
    # oco2_tower.add_checker('oco2_tower.checkers.switch_buffer_windows')
    # oco2_tower.add_checker('oco2_tower.checkers.trollsat_checks')
    # oco2_tower.add_checker('oco2_tower.checkers.x_band_checks')
    # oco2_tower.add_checker('oco2_tower.checkers.s_band_checks')

    oco2_tower.initialize_and_populate_clients()

    oco2_tower.run()
    html_report_name = f'test_results.html'
    oco2_tower.write_reports(
        html_report_name,
        f'Test Report'
        )


def main():
    # === Parse inputs
    parser = argparse.ArgumentParser()
    # # >> Scenario flags
    parser.add_argument('module', type=str, help="The module name to test (same as import name)")
    # parser.add_argument('--email-team', action='store_true', help="Flag sends the results email to 'oco2mpst@jpl.nasa.gov'")
    # parser.add_argument('--output-directory', type=str, default='.', help="Directory to write output files to")

    args = parser.parse_args()
    # Start split logging to an output file
    log_to_file(LOG_FNAME)


    tower_check(args.module)

if __name__ == "__main__":
    main()
