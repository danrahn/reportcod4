#
# Report plugin for BigBrotherBot(B3) (www.bigbrotherbot.com)
# Allows users to report other users quietly, and lets admins
# manage the reports. Optional TeamSpeak integration allows
# custom pokes and channel broadcasts as well.
#
# CHANGELOG
# 2016/06/06 - 0.4.0 - DTR     - Back support for B3 1.9.2
# 2016/06/02 - 0.3.0 - DTR     - Added cached banned status to reduce db calls
# 2016/05/29 - 0.2.0 - DTR     - Added teamspeak poking/messaging support
# 2016/05/27 - 0.1.0 - DTR     - Initial Release

__author__ = 'DTR'
__version__ = '0.3'

import b3
import b3.plugin
import b3.events
from ConfigParser import NoOptionError
from b3.functions import minutesStr
import os
import re
import telnetlib
from threading import Timer
import time


class Reportcod4Plugin(b3.plugin.Plugin):
    _adminPlugin = None

    _b3_version = None
    _client_banned_message = '^1Error^7: You\'re banned from reporting! ' \
                             'If you think this is an error, contact an administrator'
    _report_spam = '^2You have reported %s people in less than %s, ^3slow down!^7'
    _report_to_team_chat = '^1Use teamchat to report players!^7'
    _report_admins_present = '^5%s^7[^2%s^7]^5 reported ^1%s^7[^2%s^7]^1. ^5Reason: ^3%s^7'
    _num_reports_msg = '^7[^5Player has been reported by %d user%s^7]'
    _no_admins_msg = '^7Sorry, no admins are online. The report has been recorded, but no admins have been contacted.'
    _no_matches = '^1Error^5: ^7No matching players found'
    _multiple_matches = '^2Multiple matches found.^7 Use the full name or associated number and ^3!report^7 again.'
    _ts_poke_message = '%s[%s] reported %s[%s] for %s on %s.'  # Poke lengths are limited, don't do anything fancy
    _ts_channel_message = '[color=#427BC9]%s[/color][[color=#427BC9]%s[/color]] reported [color=#E39919]%s[/color]' \
                          '[[color=#E39919]%s[/color]] for [color=#EB3B3B]%s[/color] on [color=#161EFA]%s[/color]'

    _matches = {}

    _currentReports = {}

    _reportTimers = {}

    _banned_status = {}

    _report_interval = 60
    _max_report_count = 5
    _reporter_limit = 5
    _teamchat_only = True

    _query = None

    # Teamspeak related fields
    _ts_enabled = False
    _ts_match = re.compile(r'([^=]*=)(.*)')
    _ts_whoami = re.compile('.*client_id=([0-9]*)')
    _ts_con = None
    _ts_host = ''
    _ts_port = 0
    _ts_user = ''
    _ts_pass = ''
    _ts_myid = 0
    _ts_dbid = 0
    _ts_good_response = 'error id=0'
    _ts_user_fields = ['id', 'cid', 'dbid', 'name', 'type']
    _ts_channel_fields = ['id', 'pid', 'order', 'name', 'clients', 'cnsp']
    _tsreport_options = ['add', 'remove', 'list']
    _tsreport_syntax = '^3Syntax^7: ^5<^7add/remove/list^5>^7 ^8[^5<^7id^5>^8] [^5<^7name^5>^8]^7'
    _ts_channels = []
    _server_name = ''

    ####################################################################################################################
    #                                                                                                                  #
    #    STARTUP                                                                                                       #
    #                                                                                                                  #
    ####################################################################################################################

    def onLoadConfig(self):
        """
        Load the settings from the plugin configuration
        :return:
        """
        self._config_load('_report_interval', 'max_report_interval', True)
        self._config_load('_max_report_count', 'max_reports_in_interval', True)
        self._config_load('_reporter_limit', 'max_reporters_to_show', True)
        try:
            self._teamchat_only = self.config.getboolean('settings', 'teamchat_only')
            self.debug('loaded settings/teamchat_only: %s' % self._teamchat_only)
        except (NoOptionError, ValueError):
            self.warning('settings/teamchat_only is either missing or a bad value, setting to ' % self._teamchat_only)

        # Teamspeak settings
        try:
            self._ts_enabled = self.config.getboolean('settings', 'ts_enable')
            self.debug('loaded settings/ts_enable: %s' % self._ts_enabled)
        except (NoOptionError, ValueError):
            self.warning('settings/ts_enable is either missing or a bad value, disabling TS integration')
            self._ts_enabled = False
        if self._ts_enabled:
            self._config_load('_ts_host', 'ts_host', False, True)
            self._config_load('_ts_port', 'ts_port', True, True)
            self._config_load('_ts_user', 'ts_user', False, True)
            self._config_load('_ts_pass', 'ts_pass', False, True)
            self._config_load('_ts_dbid', 'ts_dbid', True, True)
            try:
                self._ts_channels = self.config.get('settings', 'ts_channels').split(',')
                self._ts_channels = [channel.strip() for channel in self._ts_channels]
                self.debug('loaded settings/ts_channels: %s' % self._ts_channels)
            except NoOptionError:
                self.warning('could not find settings/ts_channels in config file, disabling TS integration')
                self._ts_enabled = False

    def do_nothing(self):
        return

    def onStartup(self):
        """
        Initialize plugin settings
        :return: False on error
        """

        self._b3_version = b3.__version__
        self.registerEvent(b3.events.EVT_CLIENT_SAY)
        self.registerEvent(b3.events.EVT_CLIENT_TEAM_SAY)
        self.registerEvent(b3.events.EVT_CLIENT_DISCONNECT)
        self._adminPlugin = self.console.getPlugin('admin')
        if not self._adminPlugin:
            self.error('Could not load adminPlugin, aborting')
            return False
        if self._teamchat_only:
            say_id = self.console.Events.getId('EVT_CLIENT_SAY')
            del self.console._handlers[say_id][0]
        # if self.console._handlers and int(self._b3_version.split('.')[1]) < 10:
        #     del self.console._handlers[5][0]
        # elif self.console._handlers:
        #     del self.console._handlers[9][0]
        if 'commands' in self.config.sections():
            for cmd in self.config.options('commands'):
                level = self.config.get('commands', cmd)
                sp = cmd.split('-')
                alias = None
                if len(sp) == 2:
                    cmd, alias = sp
                func = self.getCmd(cmd)
                if func:
                    self._adminPlugin.registerCommand(self, cmd, level, func, alias)

        # Get the database interface
        self._query = self.console.storage.query
        self.build_database_schema()

        # Set up teamspeak connection
        if self._ts_enabled:
            try:
                self._ts_con = telnetlib.Telnet(self._ts_host, self._ts_port)
                self._ts_con.set_debuglevel(0)
                self._ts_con.open(self._ts_host, self._ts_port)
                self._ts_read()  # TS3
                self._ts_read()  # Welcome to the TeamSpeak 3...

                # Login to the ts server
                self._ts_write('login %s %s' % (self._ts_user, self._ts_pass))
                data = self._ts_read()
                if not data.startswith(self._ts_good_response):
                    raise Exception('Error logging in to TS server: %s' % data)

                # Select the correct server
                self._ts_write('use %s' % self._ts_dbid)
                data = self._ts_read()
                if not data.startswith(self._ts_good_response):
                    raise Exception('Error selecting server to use: %s' % data)

                # Get client id of our telnet client
                self._ts_write('whoami')
                data = self._ts_read()
                if data.startswith('error id='):
                    raise Exception('Error getting whoami info')
                self._ts_myid = re.match(self._ts_whoami, data).group(1)
                resp = self._ts_read()
                if not resp.startswith(self._ts_good_response):
                    raise Exception('Error getting whoami info')

                self.debug('Connected to Teamspeak server %s:%d as %s' % (self._ts_host, self._ts_port, self._ts_user))
            except Exception as e:
                self.debug('Error connecting to Teamspeak server:')
                self.debug(e)
                self._ts_enabled = False

        # Get the server name, stripping color information
        server = self.console.write('sv_hostname')
        server = re.match('"[^"]*" is: "([^"]*)"', server)
        self._server_name = re.sub('\^[0-9]', '', server.group(1))

        self.debug('ReportCod4 Plugin Started')

    def onEvent(self, event):
        if event.type == b3.events.EVT_CLIENT_SAY:
            self.on_say(event)
        elif event.type == b3.events.EVT_CLIENT_TEAM_SAY:
            # forward the message if the b3 version isn't 1.10.x
            if int(self._b3_version.split('.')[1]) < 10:
                self._adminPlugin.OnSay(event)
        elif event.type == b3.events.EVT_CLIENT_DISCONNECT:
            self.client_disconnect(event)

    def getCmd(self, cmd):
        """
        Map the given command to its correct cmd_x function
        """
        cmd = 'cmd_%s' % cmd
        if hasattr(self, cmd):
            func = getattr(self, cmd)
            return func
        return None

    def build_database_schema(self):
        """
        Build the database tables needed if not present
        """
        sql_main = os.path.join(b3.getAbsolutePath('@b3/extplugins/reportcod4/sql'), 'mysql')
        current_tables = self.get_tables()
        # current_tables = self.console.storage.getTables()
        for f in os.listdir(sql_main):
            if f[:len(f) - len('.sql')] in current_tables:
                self.debug('Table %s found' % f)
            else:
                # Attempt to create the SQL table if it doesn't exist
                self.debug('Table %s NOT found, attempting to create' % f[:len(f) - len('.sql')])
                table = open('%s\\%s' % (sql_main, f), 'r').read()
                self._query(table)
                self.debug('Table %s created' % f[:len(f) - len('.sql')])

    ####################################################################################################################
    #                                                                                                                  #
    #    COMMANDS                                                                                                      #
    #                                                                                                                  #
    ####################################################################################################################

    def cmd_report(self, data, client, cmd=None):
        """
        <player> <reason> - report a player to the admins. Surround their name in single quotes if it contains spaces.
        """
        # First check to see if the client is banned
        if client.id not in self._banned_status:
            self._banned_status[client.id] = self._is_banned(client.id)
        if self._banned_status[client.id]:
            client.message(self._client_banned_message)
            return

        if not data:
            client.message('^7You must supply a player to report and a reason')
        else:
            if client.id not in self._currentReports:
                self._currentReports[client.id] = 0
            if self._currentReports[client.id] >= self._max_report_count:
                # The client has been reporting too many players too quickly, tell them to slow down
                client.message(self._report_spam % (self._reporter_limit, minutesStr(str(self._report_interval) + 's')))
                return

            quotes = re.match(r"'(.*?)'(.*)", data)
            decoded_quotes = None
            reason = None
            if quotes:
                decoded_quotes = quotes.group(1).lower()
                reason = quotes.group(2).lower()
            data = data.split(' ', 1)
            if reason is None:
                reason = data[1]
            if len(data) == 1:
                client.message('^7You must supply a reason')
                return

            found = False
            decoded = data[0].lower()

            # Grab current admins
            # TODO: Potentially use getClientsByLevel if we want to customize level
            admins = self._adminPlugin.getAdmins()
            # Grab all clients
            clients = self.console.clients.getClientsByLevel()
            matches = []

            # The client has previously tried to report a player
            # and received multiple matches, if they enter an integer
            # assume it's to narrow down to a specific player
            if client.id in self._matches:
                matchlist = self._matches[client.id]
                try:
                    val = int(decoded)
                    if val >= len(matchlist):
                        client.message('Index out of range, please report player again')
                        self._matches.pop(client.id)  # Remove previous player indexes
                        return
                    matches = [matchlist[val]]
                    self._matches.pop(client.id)
                    found = True
                except ValueError:
                    # Client did not enter an int index, assume they're retrying with a different name
                    found = False
                    self._matches.pop(client.id)
            # Either the client has not previously attempted to report a player,
            # or the index they provided was not in range. Search again
            if not found:
                # Grab all matching names/cids/ids
                matches = [c for c in clients if decoded in c.name.lower()]

                if decoded == 'noname':
                    # If "noname" specified (all special characters=blank name), add those
                    # with an empty name/those only their @id as their name to the list
                    matches.extend([c for c in clients if c.name == '' or c.name[:1] == '@'])
                if decoded_quotes:
                    extras = [c for c in clients if decoded_quotes in c.name.lower()]
                    for extra in extras:
                        if extra not in matches:
                            matches.append(extra)
                    # matches.extend([c for c in clients if decoded_quotes in c.name.lower()])

            # No matches found
            if len(matches) == 0:
                client.message(self._no_matches)

            # Single match found, report the player
            elif len(matches) == 1:
                match = matches[0]
                self._currentReports[client.id] += 1
                cur_time = self.milli_time()
                t = Timer(self._report_interval, self.dec_count, [client.id, cur_time])
                self._reportTimers[cur_time] = t
                self._reportTimers[cur_time].start()
                no_admins = True
                if len(admins) > 0:
                    player_id = match.id
                    client.message('Reporting %s to admins.' % match.name)
                    self._send_report(client, player_id, data[1])
                    reports = self._get_report(player_id)
                    for admin in admins:
                        self._admin_report(admin, client.name, client.cid, match.name, match.cid, reason, reports)
                    no_admins = False

                # Send TS messages
                no_admins = self._send_ts_messages(client, match, data, no_admins)

                if no_admins:
                    client.message(self._no_admins_msg)
            # Multiple matches found. Present a list to the user
            else:
                self._matches[client.id] = matches
                client.message(self._multiple_matches)
                matchstring = '^7' + matches[0].name + '[^20^7]'
                for i in range(1, len(matches)):
                    matchstring += ', ' + matches[i].name + '[^2' + str(i) + '^7]'
                client.message(matchstring)

    def cmd_reportclear(self, data, client, cmd=None):
        """
        <player> - remove all reports on a player
        """
        if not data:
            client.message('You must supply a client to clear')
            return
        users = self.console.clients.getByMagic(data)
        if len(users) == 0:
            client.message('No matching clients found')
        elif len(users) > 1:
            client.message('Multiple matches found:')
            client.message(', '.join('^7%s[^3@%s^7]' % (user.name, user.id) for user in users))
        else:
            client.message('Removing all reports for player %s' % users[0].name)
            self._remove_reports(users[0].id)

    def cmd_reports(self, data, client, cmd=None):
        """
        [<player>] [reasons]- view the number of reports for the given player,
        or all players currently connected
        """
        if not data:
            data = ''
        lst = []
        clients = self.console.clients.getByMagic(data)
        for reportee in clients:
            count = self._get_report(reportee.id)
            if count != 0:
                lst.append('^7%s[^2%s^7]: ^3%d^7' % (reportee.name, reportee.cid, count))
        if len(lst) == 0:
            if data != '':
                client.message('^7No reports found for %s' % data)
            else:
                client.messsage('^7No reports found')
        else:
            if len(lst) == 1:
                reason_lst = self._get_reasons(clients[0].id)
                client.message('%s reported for: ' % clients[0].name)
                client.message(', '.join(x for x in reason_lst))
            else:
                client.message(', '.join(x for x in lst))

    def cmd_reportsby(self, data, client, cmd=None):
        """
        <player> - view reports by a given player
        """
        if not data:
            client.message('You must supply a reporter')
            return
        users = self.console.clients.getByMagic(data)
        if len(users) == 0:
            client.message('No matching clients with reports found')
        elif len(users) == 1:
            reports, additional = self._get_reports_by(users[0].id)
            msg = '(^2%d^7 not shown)' % additional if additional > 0 else ''
            client.message('^7Reports by %s: %s' % (users[0].name, msg))
            lst = []
            for report in reports:
                cli = self.console.clients.getByDB('@%d' % report['id'])[0]
                lst.append('^7%s[^2@%d^7]: ^3%s^7' % (cli.name, cli.id, report['reason']))
            client.message(', '.join(x for x in lst))
        else:
            client.message('Multiple matches found:')
            client.message(', '.join('^7%s[^3@%s^7]' % (user.name, user.id) for user in users))

    def cmd_reporters(self, data, client, cmd=None):
        """
        <player> - get a list of users who reported a player (up to 5 most recent)
        """
        if not data:
            client.message('You must supply a reported player')
            return
        users = self.console.clients.getByMagic(data)
        if len(users) == 0:
            client.message('No matching clients with reports found')
        elif len(users) == 1:
            reporters, additional = self._get_reporters(users[0].id)
            msg = '(^2%d^7 not shown)' % additional if additional > 0 else ''
            client.message('^7Reporters for %s: %s' % (users[0].name, msg))
            lst = []
            for reporter in reporters:
                cli = self.console.clients.getByDB('@%d' % reporter['id'])[0]
                lst.append('^7%s[^2@%d^7]: ^3%s^7' % (cli.name, cli.id, reporter['reason']))
            client.message(', '.join(x for x in lst))
        else:
            client.message('Multiple matches found:')
            client.message(', '.join('^7%s[^3@%s^7]' % (user.name, user.id) for user in users))

    def cmd_banreporter(self, data, client, cmd=None):
        """
        <player> - ban a player from reporting others
        """
        if not data:
            client.message('You must supply a user to ban')
            return
        data = data.split(' ', 1)
        if len(data) == 1:
            data.append('')
        users = self.console.clients.getByMagic(data[0])
        if len(users) == 0:
            client.message('No matching clients found')
        elif len(users) > 1:
            client.message('Multiple matches found:')
            client.message(', '.join('^7%s[^3@%s^7]' % (user.name, user.id) for user in users))
        else:
            banned = self._ban_user(users[0].id, client.id, data[1])
            if not banned:
                client.message('The user is already banned!')
            else:
                # self._remove_reports_by_user(users[0].id)
                client.message('Banned %s from reporting' % users[0].name)
            if users[0].id in self._banned_status:
                self._banned_status[users[0].id] = True

    def cmd_unbanreporter(self, data, client, cmd=None):
        """
        <player> - allow a player to report again
        """
        if not data:
            client.message('You must supply a user to unban')
            return
        users = self.console.clients.getByMagic(data)
        if len(users) == 0:
            client.message('No matching clients found')
        elif len(users) > 1:
            client.message('Multiple matches found:')
            client.message(', '.join('^7%s[^3@%s^7]' % (user.name, user.id) for user in users))
        else:
            unbanned = self._unban_user(users[0].id)
            if not unbanned:
                client.message('%s isn\'t banned!' % users[0].name)
            else:
                client.message('%s is unbanned from reporting' % users[0].name)
            if users[0].id in self._banned_status:
                self._banned_status[users[0].id] = False

    def cmd_tsreport(self, data, client, cmd=None):
        """
        add/remove/list [<id>] [<name>]
        """
        if not data:
            client.message(self._tsreport_syntax)
            return
        data = data.split(' ', 2)
        if len(data) < 2 and data[0] != 'list':
            client.message(self._tsreport_syntax)
            return
        command = data[0].lower()
        uid = 0
        name = '[none]'
        if command not in self._tsreport_options:
            client.message('You must supply a valid command!')
            return
        if data[0] == 'list':
            receivers = self._get_ts_receivers()
            msg = ', '.join(['^7%s: ^3%s^7' % (receivers[receiver], receiver) for receiver in receivers])
            client.message(msg)
            return
        try:
            uid = int(data[1])
        except ValueError:
            client.message('^7TS id must be a number!')
            return
        if len(data) == 3:
            name = data[2]
        self._add_ts_id(uid, name, client) if command == 'add' else self._remove_ts_id(uid, client)

    ####################################################################################################################
    #                                                                                                                  #
    #    AUXILARY FUNCTIONS                                                                                            #
    #                                                                                                                  #
    ####################################################################################################################

    def _config_load(self, var, name, is_int, ts=False):
        """
        Loads a setting from the config file
        :param var: the var to save the setting to
        :param name: the name of the setting in the config file
        :param is_int: True if the settings should be processed as an integer
        :param ts: True if this is a teamspeak setting
        """
        try:
            setattr(self, var, self.config.getint('settings', name) if is_int else self.config.get('settings', name))
            self.debug('loaded settings/%s: %s' % (name, getattr(self, var)))
        except (NoOptionError, ValueError):
            if ts:
                self.warning('bad or missing settings/%s in config file, disabling TS integration' % name)
                self._ts_enabled = False
            else:
                self.warning('Bad type or missing setting %s in config file, using default %s.' %
                             # (name, self.__getattr__(var)))
                             (name, getattr(self, var)))

    def on_say(self, event, private=False):
        """
        Whenever a player says something to general chat, make sure they aren't using
        !report or !r, as it should only be used in team chat
        """
        if event.data[:8] == '!report ' or event.data[:3] == '!r '\
                or event.data == '!report' or event.data == '!r':
            event.client.message(self._report_to_team_chat)
        elif self._teamchat_only:
            self._adminPlugin.OnSay(event)

    def client_disconnect(self, event, private=False):
        data = int(event.data)
        client = self.console.clients.getByCID(data)
        if client and client.id in self._banned_status:
            self._banned_status.pop(client.id)

    def _admin_report(self, admin, reporter, rcid, name, cid, reason, num_reports):
        """
        Tells the admin that the given user has reported another user
        :return:
        """
        admin.message(self._report_admins_present % (reporter, rcid, name, cid, reason))
        msg = 's' if num_reports > 1 else ''
        admin.message(self._num_reports_msg % (num_reports, msg))

    def temp_encode_data(self, data, source):
        """
        This function overrides rcon's encode_data, since it strips
        special chars
        """
        return data

    def dec_count(self, pid, cur_time):
        """
        Called when a timer expires, basically allowing a user to report
        an additional player
        """
        if pid in self._currentReports:
            if self._currentReports[pid] - 1 == 0:
                self._currentReports.pop(pid)
            else:
                self._currentReports[pid] -= 1
        self._reportTimers.pop(cur_time)

    def milli_time(self):
        return int(round(time.time() * 1000))

    ####
    #   TS related aux functions
    ####
    def _send_ts_messages(self, client, match, data, no_admins):
        """
        Send pokes to admins registered to receive them, and send mass messages
        to requested channels
        :param client: the client making the report
        :param match: the matching client
        :param data: the data the client supplied
        :param no_admins: whether or not admins have been found to contact
        :return: no_admins original value, or False if an admin was found to poke
        """
        if self._ts_enabled:
            ts_users = self._get_current_ts_clients()
            ts_receivers = self._get_ts_receivers()
            ts_channels = self._get_current_ts_channels()
            # Poke all admins who have signed up for pokes
            if ts_users:
                for user in ts_users:
                    if ts_users[user]['dbid'] in ts_receivers:
                        msg = (self._ts_poke_message %
                               (client.name, '@' + str(client.id), match.name,
                                '@' + str(match.id), data[1], self._server_name)).replace(' ', '\s')
                        # msg = self._ts_parse(msg)
                        command = 'clientpoke clid=%s msg=%s' % (user, msg)
                        self._ts_write(command)
                        response = self._ts_read()
                        if not response.startswith(self._ts_good_response):
                            self.debug('Error sending poke to ts user %s' % user)
                        no_admins = False
            # Send a message to all ts channels requested
            if ts_channels:
                for channel in ts_channels:
                    if ts_channels[channel]['name'] in self._ts_channels:
                        self._ts_write('clientmove clid=%s cid=%s' % (self._ts_myid, channel))
                        resp = self._ts_read()
                        if not resp.startswith(self._ts_good_response) and not resp.startswith('error id=770'):
                            self.warning('Error moving channels: %s' % resp)
                            continue
                        self._ts_write('sendtextmessage targetmode=2 target=%s msg=%s' %
                                       (channel, (self._ts_channel_message %
                                                  (client.name, '@' + str(client.id), match.name,
                                                   '@' + str(match.id), data[1],
                                                   self._server_name)).replace(' ', '\s')))
                        if not self._ts_read().startswith(self._ts_good_response):
                            self.debug('Error writing message to channel')
        return no_admins

    def _ts_read(self):
        """
        read a response from the teamspeak server
        :return: the response received
        """
        recv = self._ts_con.read_until('\n\r')
        return recv  # .replace('\\s', '')

    def _ts_write(self, message):
        """
        write a command to the teamspeak server
        :param message: the command to send
        """
        self._ts_con.read_lazy()  # Make sure nothing is in the receiving queue
        self._ts_con.write(('%s\n\r' % message).encode('ascii'))

    def _get_current_ts_clients(self):
        """
        return a list of clients currently connected to the teamspeak server
        """
        return self._get_ts_helper('clientlist', self._ts_user_fields)

    def _get_current_ts_channels(self):
        """
        return a list of the current channels in the teamspeak server
        """
        return self._get_ts_helper('channellist', self._ts_channel_fields)

    def _get_ts_helper(self, cmd, field_list):
        """
        helper function that retrieves the specified list of items
        from the teamspeak server
        :param cmd: the list command (eg clientlist or channellist)
        :param field_list: the list of fields for the given command
        """
        self._ts_write(cmd)
        data = self._ts_read()
        status = self._ts_read()
        if not status.startswith(self._ts_good_response):
            self.warning('Error getting list from TeamSpeak, returning None')
            return None
        items = {}
        data = data.split('|')  # Entries separated by pipes TODO: what if person's name contains pipe?
        for item in data:
            item = item.split(' ')
            myid = 0
            count = 0
            for entry in item:
                field = field_list[count]
                val = re.match(self._ts_match, entry)
                if field == 'id':
                    myid = int(val.group(2))
                    items[myid] = {}
                else:
                    if field != 'name':
                        items[myid][field] = int(val.group(2))
                    else:
                        items[myid][field] = val.group(2).replace('\\s', ' ')
                count += 1
        return items

    def _ts_parse(self, msg):
        """
        make a string teamspeak friendly by replacing spaces with the
        general whitespace character \s
        :param msg:
        :return:
        """
        return msg.replace(' ', '\\s')

    # Import from future b3: mysql.getTables()
    def get_tables(self):
        """
        List the tables of the current database.
        :return: list of strings.
        """
        tables = []
        cursor = self._query("SHOW TABLES")
        if cursor and not cursor.EOF:
            while not cursor.EOF:
                row = cursor.getRow()
                tables.append(row.values()[0])
                cursor.moveNext()
        cursor.close()
        return tables

    ####################################################################################################################
    #                                                                                                                  #
    #    SQL FUNCTIONS                                                                                                 #
    #                                                                                                                  #
    ####################################################################################################################

    # TODO: Handle the case where the query was not successful. At this point I assume everything just works

    def _send_report(self, client, reportee, reason):
        reason = reason.replace("\"", "\\\"")
        q = 'SELECT * FROM reports WHERE reporter = %d AND reportee = %d' % (client.id, reportee)
        cursor = self._query(q)
        if not cursor or cursor.EOF:
            q = 'INSERT INTO reports (reporter, reportee, reason, times_reported, time) ' \
                'VALUES (%d, %d, "%s", times_reported + 1, UNIX_TIMESTAMP())' % (client.id, reportee, reason)
            self._query(q)
        elif cursor:
            q = 'UPDATE reports SET reason = "%s", times_reported = times_reported + 1, time = UNIX_TIMESTAMP()' \
                ' WHERE reporter = %d AND reportee = %d' % \
                (reason, client.id, reportee)
            self._query(q)
            client.message('You have already reported this player. Updating reason')

    def _get_report(self, reportee):
        q = 'SELECT COUNT(*) AS count FROM reports WHERE reportee = %d' % reportee
        cursor = self._query(q)
        if cursor and not cursor.EOF:
            return cursor.getRow()['count']

    def _get_reports_by(self, reporter):
        q = 'SELECT reportee, reason FROM reports WHERE reporter = %d ORDER BY time DESC' % reporter
        return self._reports_helper(self._query(q), 'reportee')

    def _get_reporters(self, reportee):
        q = 'SELECT reporter, reason FROM reports WHERE reportee = %d ORDER BY time DESC' % reportee
        return self._reports_helper(self._query(q), 'reporter')

    def _reports_helper(self, cursor, col):
        count = 0
        rowcount = 0
        res = []
        if cursor and not cursor.EOF:
            rowcount = cursor.rowcount - self._reporter_limit
            while not cursor.EOF and count != self._reporter_limit:
                row = cursor.getRow()
                res.append({'id': row[col], 'reason': row['reason']})
                cursor.moveNext()
                count += 1
        return res, rowcount

    def _remove_reports(self, reportee):
        q = "DELETE FROM reports WHERE reportee=%d" % reportee
        self._query(q)

    def _remove_reports_by_user(self, reporter):
        q = "DELETE FROM reports WHERE reporter = %d" % reporter
        self._query(q)

    def _ban_user(self, banned_id, banner_id, reason):
        reason = reason.replace("\"", "\\\"")
        q = "SELECT * FROM reports_banned WHERE banned_id=%d" % banned_id
        cursor = self._query(q)
        if cursor and not cursor.EOF:
            return False
        if reason == '':
            reason = '[none given]'
        q = 'INSERT INTO reports_banned (banned_id, banner_id, reason, time) ' \
            'VALUES (%d, %d, "%s", UNIX_TIMESTAMP())' % (banned_id, banner_id, reason)
        self._query(q)
        return True

    def _unban_user(self, banned_id):
        q = "SELECT * FROM reports_banned WHERE banned_id=%d" % banned_id
        cursor = self._query(q)
        if cursor and cursor.EOF:
            return False
        q = "DELETE FROM reports_banned WHERE banned_id=%d" % banned_id
        self._query(q)
        return True

    def _is_banned(self, id):
        q = "SELECT * FROM reports_banned WHERE banned_id=%d" % id
        cursor = self._query(q)
        return cursor and not cursor.EOF

    def _get_reasons(self, id):
        q = "SELECT reason FROM reports WHERE reportee = %d" % id
        cursor = self._query(q)
        lst = []
        if cursor and not cursor.EOF:
            while not cursor.EOF:
                lst.append(cursor.getRow()['reason'])
                cursor.moveNext()
        return lst

    def _get_ts_receivers(self):
        q = "SELECT ts_id, nick FROM reports_teamspeak"
        cursor = self._query(q)
        receivers = {}
        if cursor and not cursor.EOF:
            while not cursor.EOF:
                row = cursor.getRow()
                receivers[row['ts_id']] = row['nick']
                cursor.moveNext()
        return receivers

    def _add_ts_id(self, tsid, name, client):
        name = name.replace("\"", "\\\"")
        q = "SELECT * FROM reports_teamspeak WHERE ts_id=%d" % tsid
        cursor = self._query(q)
        if cursor and not cursor.EOF:
            client.message('^7TS client with id ^2%d^7 already in the database, updating name' % tsid)
            q = 'UPDATE reports_teamspeak SET nick="%s" WHERE ts_id = %d' % (name, tsid)
            self._query(q)
        else:
            q = 'INSERT INTO reports_teamspeak (ts_id, nick, time) VALUES (%d, "%s", UNIX_TIMESTAMP())' % (tsid, name)
            self._query(q)
            client.message('^7TS client id ^2%d^7 added' % tsid)

    def _remove_ts_id(self, tsid, client):
        q = "SELECT * FROM reports_teamspeak WHERE ts_id=%d" % tsid
        cursor = self._query(q)
        if not cursor or cursor.EOF:
            client.message('^7TS client with id ^2%d^7 not in the database!' % tsid)
        else:
            q = 'DELETE FROM reports_teamspeak WHERE ts_id=%d' % tsid
            self._query(q)
            client.message('^7TS client id ^2%d^7 removed' % tsid)
