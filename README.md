# BigBrotherBot !report Plugin

This plugin designed for Call of Duty 4: Modern Warfare, and allows
users to discreetly report players to online admins, as well as send
pokes and channel broadcasts to a TeamSpeak 3 server.

## Usage

### _!report (!r)_
***
#### !report \<player\> \<reason\>
![Example](http://i.imgur.com/OSloLsV.jpg)
Above, the first line is the report (to team chat), the second is the pm
to the reporter, and the rest is the pm to the admins on the server.

Reports the given player for the given reason. This works in different
ways depending on the results. The plugin will find all clients that
match the player string. If only a single player is found, they are
reported, which involves sending a pm to every admin currently in the
server, and writes an entry to the database indicating that player x
reported player y for reason z. Additionally, if enabled, the plugin
will send messages to specified TeamSpeak channels and poke specified
TeamSpeak users. If multiple clients are found, the user is presented
with a list of users, along with number associations (eg, DTR\[0\],
{zA}DTR\[1\], Dan\[2\]). The user can then do a followup !report with
either the full name or number association (!report 2 Aimbot or !report
Dan Aimbot). The main idea of this is that a user should use !report in
team chat, so the cheater isn't aware that other people are on to them,
so if a player uses !report in general chat, they'll get a pm saying to
only use it in team chat.

Also, since this has the potential to be abused (people spamming reports
to either be annoying or in an effort to slow down B3 by making it
process so many requests), there are configurable limits that are set so
that a user can only make x reports in y seconds/minutes/hours.

Sidenote: I've had some issues with name matching when special
characters are involved, since (my version of) b3 apparently just strips
them. For this reason, I've implemented some special cases to help with
name resolution. First, if there are spaces in the name, you can replace
them with underscores. So if a hacker has a name of D T R, you could
type D_T_R and get the single result, instead of it being interpreted as
a search for player "D", with "T R ..." as the reason. Secondly, if a
hacker's name consists solely of special characters, they will be
unnamed by b3, so instead you should have their name be "noname". This
prompts the plugin to search for any players with an empty name (as well
as players with "noname" in their name). I mainly went through the
hassle of all of this because, while it is easy enough to get the user's
id through !list or !lookup, !report is meant to be used by people that
don't have access to that information.

#### !report help
!help report gives a very short description of the usage, and I didn't
want to clutter people's chat with a huge help message if they don't
want it, so I make "!report help" trigger a longer explanation.

#### !report ex
Kind of a continuation of !report help, this displays some examples for
special use cases (D T R = D_T_R, Pläyer = Plyer, Çüä = noname))

***
### _!reports_
***
#### !reports
Gives a list of each online user who has a report against them, as well
as the number of unique users who have reported them.

#### !reports \<player\>
Same as above, but only lists users who match the given \<player\> string.
\<player\> can also be a cid (13) or id (@15243). If only a single player
matches, also lists the reasons they were reported.

***
### _!reportclear (!rc)_
***
#### !reportclear \<player\>
Removes all reports from a user. If more than one user matches, a list
of users and their @ids is presented so the admin can select the right
one

***
### _!reporters_
***
#### !reporters \<player\>
Displays a list of the most recent users who reported the player along
with the reason, or a list of users if multiple players match \<player\>.

***
### _!reportsby (!rb)_
***
#### !reportsby \<player\>
Displays a list of the most recent reports a user has given, or a list
of users if multiple players match.

***
### _!banreporter (!br)_
***
#### !banreporter \<player\> \[\<reason\>\]
Bans a user from reporting other players, giving an optional reason as
well. Helpful against spammers (assuming we don't just ban them from the
server itself). Displays a list of options if multiple players match.

***
### _!unbanreporter (!ubr)_
***
#### !unbanreporter \<player\>
Unbans a user from reporting other players. Displays a list of options
if multiple players match.

***
### _!tsreport_
***
#### !tsreport add \<id\> \[\<name\>\]
Add the given Teamspeak id to the list of users to be poked. Optionally
supply a name for reference. The TeamSpeak id you provide should be your
database id. I don't know how to easily find out what yours is without
installing Teamspeak's [Extended Client Info](http://addons.teamspeak.com/directory/skins/stylesheets/Extended-Client-Info.html) addon.
#### !tsreport remove \<id\>
Remove the given TeamSpeak id from the list of users to be poked.
#### !tsreport list
List the current set of users to be poked.

Example of !tsreport commands:

![tsreport command examples](http://i.imgur.com/rHZBqrz.jpg)

Example of TeamSpeak side interaction:

![TeamSpeak integration](http://i.imgur.com/5clhIEm.png)
