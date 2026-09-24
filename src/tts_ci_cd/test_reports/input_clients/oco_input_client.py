import logging
import pdb
import re
from datetime import datetime
from copy import deepcopy
import inspect

from tts_tower.inputs.input_client import InputClient
from tts_html_utils.core.components.text import Paragraph as P
from tts_html_utils.core.components.text import Heading1 as H1
from tts_html_utils.core.components.text import Heading2 as H2
from tts_html_utils.core.components.text import Heading4 as H4
from tts_html_utils.core.components.table import PowerTable

log = logging.getLogger(__name__)


def gt(key, value):
    return lambda r: r[key] > value
def lt(key, value):
    return lambda r: r[key] < value
def gte(key, value):
    return lambda r: r[key] >= value
def lte(key, value):
    return lambda r: r[key] <= value
def eq(key, value):
    return lambda r: r[key] == value
def ne(key, value):
    return lambda r: r[key] != value
def isin(key, values):
    return lambda r: r[key] in values
def notin(key, values):
    return lambda r: r[key] not in values
def contains(key, substring, case_sensitive=True):
    if case_sensitive:
        return lambda r: substring in r[key]
    else:
        return lambda r: substring.lower() in r[key].lower()
def doesnotcontain(key, substring, case_sensitive=True):
    if case_sensitive:
        return lambda r: substring not in r[key]
    else:
        return lambda r: substring.lower() not in r[key].lower()
def before(time, time_label, inclusive=False):
    if inclusive:
        return lambda r: r[time_label] <= time
    else:
        return lambda r: r[time_label] < time
def after(time, time_label, inclusive=False):
    if inclusive:
        return lambda r: r[time_label] > time
    else:
        return lambda r: r[time_label] >= time
def between(key, lower, upper, inclusive="both"):
    if inclusive == "both":
        return lambda r: lower <= r[key] <= upper
    elif inclusive == "neither":
        return lambda r: lower < r[key] < upper
    elif inclusive == "lower":    
        return lambda r: lower <= r[key] < upper
    elif inclusive == "upper":
        return lambda r: lower < r[key] <= upper
    else:
        raise ValueError("inclusive must be 'both', 'neither', 'lower', or 'upper'")

FILTERS = {
    'gt': gt,
    'lt': lt,
    'gte': gte,
    'lte': lte,
    'eq': eq,
    'ne': ne,
    'isin': isin,
    'notin': notin,
    'contains': contains,
    'doesnotcontain': doesnotcontain,
    'before': before,
    'after': after,
    'between': between
}

class Oco2InputClient(InputClient):
    def resolve_kwargs(self, time_label, records):
        if time_label is None: time_label = self.default_time_label
        if time_label is None: raise ValueError("No time label defined for this class. Cannot examine records based on time.")
        if records is None: records = self.records
        if records is None: raise ValueError("No records defined.")
        return time_label, records

    def __len__(self):
        return len(self.records)

    def __getitem__(self, ii):
        return self.records[ii]

    def _filter(self, condition, minimum=None, maximum=None, exactly=None):
        #Note that this uses private methods from InputClient, but I propose
        #we move all of this down into InputClient, so that won't be a big
        #deal anymore once we do.        

        #what the heck is going on here? Glad you asked.
        #I'm basically doing a deep copy of self. In fact, when
        #I originally did this, that's exactly what I did.
        #but it was slooooooooooow. So instead I loop through the
        #attributes of the copy one at a time and only copy them
        #if they're NOT the records attribute.
        #
        #That way we don't waste time copying a huge amount of data
        #that we're not going to use most of anyway. Instead of copying
        #I just do the filterign that we want to do right there.

        #TO DO: EXPLAIN WTF YOU ARE DOING HERE
        new_obj = type(self)(*(None for x in inspect.signature(type(self)._impl_init).parameters.values() if x.name != 'self'))
        for key, value in self.__dict__.items():
            new_obj._unlock()
            if key == 'records':
                setattr(new_obj, key, [r for r in self.records if condition(r)])
            else:                
                setattr(new_obj, key, deepcopy(value))
        new_obj._lock()

        if exactly is not None and minimum is not None:
            log.warning('"exactly" and "minimum" kwargs are both set. Only "exactly" will be honored.')
        if exactly is not None and maximum is not None:
            log.warning('"exactly" and "maximum" kwargs are both set. Only "exactly" will be honored.')
        if exactly is not None and len(new_obj) != exactly:
            raise Exception(f'Filtered length is not exactly {exactly} as specified')
        if minimum is not None and len(new_obj) < minimum:
            raise Exception(f'Filtered length is not at least {minimum} as specified')
        if maximum is not None and len(new_obj) > maximum:
            raise Exception(f'Filtered length is not less than or equal to {maximum} as specified')
        if exactly == 1:
            new_obj._unlock()
            new_obj.records = new_obj.records[0]
            new_obj._lock()
        return new_obj

    def __repr__(self):
        return str(self.records)

    def __add__(self, other, sort_by=None):
        if sort_by is None: sort_by = self.default_time_label
        new_obj = type(self)(*(None for x in inspect.signature(type(self)._impl_init).parameters.values() if x.name != 'self'))
        for key, value in self.__dict__.items():
            new_obj._unlock()
            if key == 'records':
                setattr(new_obj, key, self.records + other.records)
            else:                
                setattr(new_obj, key, deepcopy(value))
        new_obj._lock()
        new_obj.sort(by=sort_by)
        return new_obj


    def unique(self, key, exclude=[], sort=True):
        if not isinstance(exclude, list): exclude = [exclude]
        unique = list(set([x[key] for x in self.records if x[key] not in exclude]))
        unique.sort()
        return unique

    def gt(self, key, value, minimum=None, maximum=None, exactly=None):
        return self._filter(gt(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def lt(self, key, value, minimum=None, maximum=None, exactly=None):
        return self._filter(lt(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def gte(self, key, value, minimum=None, maximum=None, exactly=None):
        return self._filter(gte(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def lte(self, key, value, minimum=None, maximum=None, exactly=None):
        return self._filter(lte(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def eq(self, key, value, minimum=None, maximum=None, exactly=None):
        return self._filter(eq(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def ne(self, key, value, minimum=None, maximum=None, exactly=None):
        return self._filter(ne(key, value), minimum=minimum, maximum=maximum, exactly=exactly)

    def isin(self, key, values, minimum=None, maximum=None, exactly=None):
        return self._filter(isin(key, values), minimum=minimum, maximum=maximum, exactly=exactly)

    def notin(self, key, values, minimum=None, maximum=None, exactly=None):
        return self._filter(notin(key, values), minimum=minimum, maximum=maximum, exactly=exactly)

    def contains(self, key, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        return self._filter(contains(key, substring, case_sensitive=case_sensitive), minimum=minimum, maximum=maximum, exactly=exactly)

    def doesnotcontain(self, key, substring, case_sensitive=True, minimum=None, maximum=None, exactly=None):
        return self._filter(doesnotcontain(key, substring, case_sensitive=case_sensitive), minimum=minimum, maximum=maximum, exactly=exactly)

    def before(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        if time_label is None: time_label = self.default_time_label
        return self._filter(before(time, time_label, inclusive=inclusive), minimum=minimum, maximum=maximum, exactly=exactly)

    def after(self, time, time_label=None, inclusive=False, minimum=None, maximum=None, exactly=None):
        if time_label is None: time_label = self.default_time_label
        return self._filter(after(time, time_label, inclusive=inclusive), minimum=minimum, maximum=maximum, exactly=exactly)

    def between(self, key, lower, upper, inclusive="both", minimum=None, maximum=None, exactly=None):
        return self._filter(between(key, lower, upper, inclusive=inclusive), minimum=minimum, maximum=maximum, exactly=exactly)


    def record_times_to_datetime(self):
        for record in self.records:
            for time_label in self.time_labels:
                record[time_label['name']] = datetime.strptime(record[time_label['name']].strip(), time_label['format'])

    def record_times_to_string(self):
        for record in self.records:
            for time_label in self.time_labels:
                record[time_label['name']] = record[time_label['name']].strftime(time_label['format'])

    def normalize_columns(self, records):
        unique_keys = []
        for record in records:
            unique_keys += list(record.keys())
            unique_keys = list(set(unique_keys))

        unique_keys.sort() #otherwise order isn't deterministic, which we need for how we handle tests...

        for record in records:
            missing_keys = [k for k in unique_keys if k not in record.keys()]
            for missing_key in missing_keys: record[missing_key] = None

        return records

    def file_contents_as_string(self):
        with open(self.filepath, 'r') as f:
            return f.read()

    def simple_record_table(self, title, css_rules=[]):
        for record in self.records: 
            record['CSS Style'] = None
        for css_rule in css_rules:
            aargs = css_rule['args']
            if 'kwargs' in css_rule.keys():
                kwargs = css_rule['kwargs']
            else:
                kwargs = {}
            comparison = FILTERS[css_rule['comparison']](*aargs, **kwargs)

            for record in self.records: 
                if comparison(record): record['CSS Style'] = css_rule['style']

        if len(self.records):
            output_table = PowerTable(column_fields=[k for k in self.records[0].keys() if k != 'CSS Style'])
            output_table.add_header(column_names=[k for k in self.records[0].keys() if k != 'CSS Style'])
            for record in self.records:
                output_table.add_row(record, style=record['CSS Style'])
        else:
            output_table = PowerTable(row_data=self.records)
        output_table.add_superheader(title)
        return output_table



    def append(self, item):
        self._unlock()
        self.records.append(item)
        self._lock()

    def sort(self, by=None, ascending=True):
        if by is None: by = self.default_time_label
        self._unlock()
        self.records = sorted(self.records, key=lambda x: x[by], reverse=not(ascending))
        self._lock()

    def inject_error(self, func):
        #THIS ISN'T BEING USED BUT I'M LEAVING
        #IT IN BECAUSE I LIKE THE IDEA
        def wrapper():
            self._unlock()
            func(self)
            self._lock()
        return wrapper