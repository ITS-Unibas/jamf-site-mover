#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#      https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import subprocess
import sys

__author__ = "Tom Cinbis"
__copyright__ = "Copyright 2018, University of Basel"
__license__ = "Apache License 2.0"
__version__ = "1.0"
__maintainer__ = "IT-Services University of Basel"
__email__ = "its-mcs@unibas.ch"

def install_pip():
    """In case pip is not installed, the method tries to utilize easy_install to install pip"""
    if sys.version_info[0] < 3:  # We are running python 2.x
        cmd = ['python -m easy_install pip']
    process = subprocess.Popen(cmd, shell=True)
    process.wait()
    process.poll()
    if process.returncode is 0:
        print('Successfully installed pip')
        return 0
    else:
        print('Error installing pip!')
        return -1


def install_pip_requirements():
    """Tries to install the requirements using a local pip version"""
    if install_pip() is 0:
        if sys.version_info[0] < 3:  # We are running python 2.x
            cmd = ['/usr/local/bin/pip install ldap3==2.4.1 requests==0.13.5 untangle==1.1.1']

        process = subprocess.Popen(cmd, shell=True)
        process.wait()
        process.poll()
        if process.returncode is 0:
            print('Successfully installed requirements')
            return 0
        else:
            print('Error installing requirements! Found python 3, but python 2 is required.')
            return -1
    else:
        print('No pip found to install requirements!')
        return -1

if __name__ == '__main__':
    install_pip_requirements()