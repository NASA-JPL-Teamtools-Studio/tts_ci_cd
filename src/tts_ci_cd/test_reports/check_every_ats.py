#!/usr/bin/env python3
import pdb
from glob import glob
from pathlib import Path
from copy import deepcopy

from ats_review_tower_check import tower_check

if __name__ == "__main__":
    as_flown_week_dirs = []
    for line in open('/groups/MOS/ATS/ATS_Log.txt','r'): 
        line = line.strip().split()
        if len(line) != 2: continue
        ats_path = line[1]
        if not ats_path.startswith('/groups'): continue
        _, _, _, _, week_dir, _ = ats_path.split('/')
        as_flown_week_dirs.append(week_dir)

    as_planned_week_dirs = [Path(x).name for x in glob('/groups/MOS/ATS/*') if Path(x).name.startswith('20')]

    review_pairs = []
    as_planned_week_dirs.sort(reverse=True)
    as_flown_week_dirs.sort(reverse=True)
    for week_dir in as_planned_week_dirs:
        if week_dir in as_flown_week_dirs:
            this_week_dir_idx = as_flown_week_dirs.index(week_dir)
            try:
                review_pairs.append((week_dir, as_flown_week_dirs[this_week_dir_idx + 1]))
            except:
                #week dirs for either the first ATS flown or prior to launch are ignored
                pass
        else:
            tmp_as_flown_week_dirs = deepcopy(as_flown_week_dirs)
            tmp_as_flown_week_dirs.append(week_dir)
            tmp_as_flown_week_dirs.sort(reverse=True)
            this_week_dir_idx = tmp_as_flown_week_dirs.index(week_dir)
            try:
                review_pairs.append((week_dir, tmp_as_flown_week_dirs[this_week_dir_idx + 1]))
            except:
                #week dirs for either the first ATS flown or prior to launch are ignored
                pass

    for review_pair in review_pairs:
        this_ats = f'/groups/calibration/cal_reports/ATS/{review_pair[0]}'
        last_ats = f'/groups/calibration/cal_reports/ATS/{review_pair[1]}'
        invalid_ats = False
        # if f'{review_pair[0]}_{review_pair[1]}' in SUCCESSFUL_CHECKS: 
        #     print(f'Skipping previously successful pair {review_pair}')
        #     continue
        if this_ats == last_ats:
            invalid_ats = True
        if len(glob(this_ats)) == 0:
            print(f'Could not find {this_ats}')
            invalid_ats = True
        if len(glob(last_ats)) == 0:
            print(f'Could not find {last_ats}')
            invalid_ats = True
        if invalid_ats: continue

        try:
            with open(f'../META_TOWER_TEST/tower_ATS_rulecheck_summary_{review_pair[0]}_{review_pair[1]}.html','r') as f:
                file_str = f.read()
                if 'Error running checker WriteAtsReport, check manually' in file_str:
                    expected_errors = 2
                else:
                    expected_errors = 0
                if file_str.count('>ERROR<') <= expected_errors:
                    print(f'Skipping previously successful review pair {review_pair}')
                    continue
        except FileNotFoundError:
            pass

        print(f'Testing review pair {review_pair}')

        tower_check([this_ats, last_ats])
        # pdb.set_trace()

    pdb.set_trace()