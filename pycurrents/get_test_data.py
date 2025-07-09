
# this program is created during the install process.
# DO NOT edit by hand.

import os

error_msg = '''
-Test data could not be found-
PYCURRENTS_TEST_DATA environment variable is not defined.
DOWNLOAD the pycurrents test data set,
EXPORT its path as PYCURRENTS_TEST_DATA env. var. and
TRY AGAIN
'''

def get_test_data_path():
    if 'PYCURRENTS_TEST_DATA' in os.environ:
        test_data_path = os.environ['PYCURRENTS_TEST_DATA']
    else:
        test_data_path = '/Users/gunnar/software/currents/programs/pycurrents_test_data'

    if not os.path.isdir(test_data_path):
        raise RuntimeError(error_msg)
    return test_data_path
