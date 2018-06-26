#!/usr/bin/python
# -*- coding: utf-8 -*-
#
#
# based upon a bash implementation by Michael Husar
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
import argparse
import ast

import requests
import untangle as untangle

from ldap3 import Connection, SIMPLE

__author__ = "Tom Cinbis"
__copyright__ = "Copyright 2018, University of Basel"
__credits__ = ["Michael Husar", "Jan Welker", "Tom Cinbis"]
__license__ = "Apache License 2.0"
__version__ = "1.0"
__maintainer__ = "IT-Services University of Basel"
__email__ = "its-mcs@unibas.ch"

LDAP_QUERY_USERS_TEMPLATE = "(&(memberOf:1.2.840.113556.1.4.1941:={0},{1})(objectcategory=person))"
LDAP_QUERY_GROUP_TEMPLATE = "(&(objectcategory=group)(memberOf={0},{1}))"

LDAP_USER = ''
LDAP_PW = ''

API_URL = "ENTER YOUR JAMF API URL HERE"
API_USER = ""
API_PASS = ""


def process_parse_output(process):
    """Tries to parse the output of a given process, decode it and returns it"""
    try:
        out = process.stdout.read()
        process.poll()
    except Exception:
        if process.returncode == None:  # Process is still running
            process.kill()
        print('Error with process!')

    if process.returncode == 0:
        decode_out = out.decode('utf-8')
        decode_out = decode_out.replace('\n', '')
        return decode_out
    else:
        if process.returncode == None:  # Process is still running
            process.kill()
        print('Error getting output!')
        return -1


def get_serial_number():
    """Returns the serial number of a Mac, buy starting a subprocess."""
    process_dict = ["/usr/sbin/system_profiler SPHardwareDataType | grep 'Serial Number (system)' | awk '{print $NF}'"]
    process = subprocess.Popen(process_dict, shell=True, stdout=subprocess.PIPE)

    return process_parse_output(process)


def get_first_username():
    """Get the first user (beside management admin user), who logged in on this device.

    We get this information by
    asking the JAMF API who the owner of this device is. By using authentication during enrollment the owner is
    automatically set in JAMF
    """

    # In case you use something like NoLoAD/NoMAD and no authentication during enrolling,
    # you can use this part of code to determine the first user who logged into the machine. Based on this we can
    # choose the correct JAMF site.
    #
    # process_dict = ["/usr/bin/dscl . -list /Users UniqueID | grep '502'| awk '{print $1;}'"]
    # process = subprocess.Popen(process_dict, shell=True, stdout=subprocess.PIPE)
    # return process_parse_output(process)

    r = requests.get('{}/JSSResource/computers/serialnumber/{}'.format(API_URL, get_serial_number()),
                     auth=(API_USER, API_PASS))
    xml_response = untangle.parse(r.text.encode('utf-8'))

    try:
        jamf_owner_username = xml_response.computer.location.username.cdata
        return (jamf_owner_username)
    except AttributeError:
        print('Error getting JAMF site id and/or JAMF site name. No such attribute in response')
        return -1


def get_jamf_information():
    """Returns a tuple containing jamf_id and jamf_site_name for given device, identified with its serial number"""
    r = requests.get('{}/JSSResource/computers/serialnumber/{}'.format(API_URL, get_serial_number()),
                     auth=(API_USER, API_PASS))
    xml_response = untangle.parse(r.text.encode('utf-8'))

    try:
        jamf_id = xml_response.computer.general.id.cdata
        jamf_site_name = xml_response.computer.general.site.name.cdata
        return (jamf_id, jamf_site_name)
    except AttributeError:
        print('Error getting JAMF id and/or JAMF site name. No such attribute in response')
        return -1


def get_jamf_site_information(site_name):
    """Returns a tuple containing the id of a jamf site and the corresponding jamf site name"""
    r = requests.get('{}/JSSResource/sites/name/{}'.format(API_URL, site_name), auth=(API_USER, API_PASS))
    xml_response = untangle.parse(r.text.encode('utf-8'))

    try:
        jamf_site_id = xml_response.site.id.cdata
        jamf_site_name = xml_response.site.name.cdata
        return (jamf_site_id, jamf_site_name)
    except AttributeError:
        print('Error getting JAMF site id and/or JAMF site name. No such attribute in response')
        return -1


def move_machine_to_jamf_site(site_name):
    """
    Move a device to site, identified by its name and id
    We receive the id by sending a get request to our JAMF api
    """
    site_info = get_jamf_site_information(site_name)
    current_jamf_information_for_device = get_jamf_information()

    if current_jamf_information_for_device[1] == site_info[1]:  # Check whether device is already in the correct site
        print('Device is already in the correct site. Ending here...')
        return

    if site_info is not -1:
        xml = '''<?xml version=\"1.0\" encoding=\"ISO-8859-1\"?><computer><general><site><id>{0}</id><name>{1}</name></site></general></computer>'''.format(
            site_info[0], site_info[1])
        headers = {'Content-Type': 'application/xml'}
        r = requests.put('{}/JSSResource/computers/id/{}'.format(API_URL, get_jamf_information()[0]),
                         auth=(API_USER, API_PASS), headers=headers, data=xml)
        if r.status_code is 201:
            print('Successfully moved machine to site: {0}'.format(site_name))
        else:
            print('Got error response from jamf. Response was: {0}'.format(r.text))
    else:
        print('Error getting site information about: {0}. Aborting!'.format(site_name))
        return


def setup_parser():
    """Setup our argument parser to get all needed variables"""
    parser = argparse.ArgumentParser(
        description='Check whether a user is part of a specified group in the AD. Based on this group we will move a device to another department in JAMF.')
    parser.add_argument('-d', '--ad-domain',
                        help='AD Domain to reach your AD server(s) Example: youAdServer.ads.yourDomain.ch', type=str,
                        required=True, metavar='domain')
    parser.add_argument('-b', '--ldap-base',
                        help='The ldap base to search in. Example: DC=unibasel,DC=ads,DC=unibas,DC=ch', type=str,
                        required=True, metavar='ldap-base')
    parser.add_argument('-g', '--group',
                        help='The distinguished name (DN) of your group to check. NOTE: Your ldap base will be appended! So do not add it to your DN \n Example: CN=MacEnrolment,OU=Mac,OU=IT,OU=Institutes',
                        type=str, required=True, metavar='group-dn')
    parser.add_argument('-t', '--timeout',
                        help='Timeout for the connection to the ldap. Should me multiple seconds because of a recursive search. Default: 20',
                        type=int, required=False, metavar='seconds', default=20)
    parser.add_argument('-s', '--site-list',
                        help='List with all JAMF site names and their corresponding group name in your AD.',
                        type=str, required=True, metavar='site-name-list')
    return parser


def open_connection_to_server(ad_domain):
    """Setup a connection to our LDAP server with given credentials."""

    connection = Connection(ad_domain, authentication=SIMPLE,
                            user=LDAP_USER, password=LDAP_PW, receive_timeout=20)
    connection.bind()

    return connection


def get_users_in_group(connection, ldap_base, ldap_group):
    """Returns a list() of users which are part of the ldap_group specified."""
    ldap_query = LDAP_QUERY_USERS_TEMPLATE.format(ldap_group, ldap_base)
    connection.search(ldap_base, ldap_query, attributes=['uid'])

    users = list()

    for LDAP_RESULT in connection.entries:
        users.append(str(LDAP_RESULT.uid))

    return users


def get_sub_groups(connection, ldap_base, ldap_group):
    """Returns a list() of groups which are part of the ldap_group specified."""
    ldap_query = LDAP_QUERY_GROUP_TEMPLATE.format(ldap_group, ldap_base)
    connection.search(ldap_base, ldap_query, attributes=['cn'])

    groups = dict()

    for LDAP_RESULT in connection.entries:
        groups[str(LDAP_RESULT.cn)] = str(LDAP_RESULT.entry_dn)

    return groups


def check_user_in_groups(connection, ldap_base, user, groups):
    """Based on our user on the machine and the groups (input argument) we check in which group the user is member."""
    for key, value in groups.items():
        ldap_query = '(&(memberOf:1.2.840.113556.1.4.1941:={0})(sAMAccountName={1})(objectcategory=person))'.format(
            value, user)
        connection.search(ldap_base, ldap_query, attributes=['cn'])
        if connection.entries.__len__() != 0:
            print('User is part of following AD group: ', key)
            return key
    return -1  # No group for user found


def main(ad_domain, ldap_base, ldap_group, jamf_site_name_dict_string):
    """The main method is responsible for opening the connection, checking for the first user on the machine,
    checking the groups which are allowed to enroll and in the end move the device to the correct JAMF site. In case we
    couldn't find a matching user or group we won't move the device.
    """
    con = open_connection_to_server(ad_domain)

    user_on_machine = get_first_username()
    jamf_site_name_dict = ast.literal_eval(jamf_site_name_dict_string)

    groups = get_sub_groups(con, ldap_base, ldap_group)
    group_of_user = check_user_in_groups(con, ldap_base, user_on_machine, groups)

    con.unbind()  # perform the Unbind operation

    if group_of_user is not -1:  # We found a group for our user
        jamf_site_to_move = jamf_site_name_dict[group_of_user]
        print('Machine will be moved to {0}'.format(jamf_site_to_move))
        move_machine_to_jamf_site(jamf_site_to_move)
        return 0
    else:
        print('''Couldn't find group for user: {0}. We can't move this machine!'''.format(user_on_machine))
        return -1


#
# sys.argv[4] contains AD Domain
# sys.argv[5] contains LDAP Base
# sys.argv[6] contains Group to check membership
# sys.argv[7] contains dictionary in string representation to translate your AD group names to JAMF Sites
# sys.argv[8] contains LDAP Username
# sys.argv[9] contains LDAP password
# sys.argv[10] contains JAMF API User
# sys.argv[11] contains JAMF API Password
#

if (sys.argv[4] is not None) and (sys.argv[5] is not None) and (sys.argv[6] is not None) and (
        sys.argv[7] is not None) and (sys.argv[8] is not None) and (sys.argv[9] is not None) and (
        sys.argv[10] is not None) and (sys.argv[11] is not None):
    LDAP_USER = sys.argv[8]
    LDAP_PW = sys.argv[9]
    API_USER = sys.argv[10]
    API_PASS = sys.argv[11]
    main(sys.argv[4], sys.argv[5], sys.argv[6], sys.argv[7])
else:
    print('Missing args!')
