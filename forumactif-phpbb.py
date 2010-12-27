#!/usr/bin/env python2
# -*- coding: utf-8 -*-
#
#       forumactif.py
#       
#       Copyright 2010 Roromis <admin@roromis.fr.nf>
#       
#       This program is free software; you can redistribute it and/or modify
#       it under the terms of the GNU General Public License as published by
#       the Free Software Foundation; either version 2 of the License, or
#       (at your option) any later version.
#       
#       This program is distributed in the hope that it will be useful,
#       but WITHOUT ANY WARRANTY; without even the implied warranty of
#       MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#       GNU General Public License for more details.
#       
#       You should have received a copy of the GNU General Public License
#       along with this program; if not, write to the Free Software
#       Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
#       MA 02110-1301, USA.

import sys, datetime, time, re, cookielib, urllib, urllib2, traceback, string, random, hashlib, codecs
import progressbar, htmltobbcode, phpbb
from pyquery import PyQuery

version = '0.1 alpha'

try:
	import save
except:
	open("save.py", "w+").close()
	import save
	
	save.state = 0
	
	save.nbposts = 0
	save.nbtopics = 0
	save.nbusers = 0
	
	save.forums = []
	save.topics = []
	save.users = []
	save.smileys = {}
	save.posts = []

try:
	import config
except:
	open("config.py", "w+").close()
	import config
	
	config.rooturl = ''
	config.admin_name = ''
	config.admin_password = ''
	config.table_prefix = ''

cookiejar = cookielib.CookieJar()
urlopener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cookiejar))

month = {u'Jan' : 1,
		 u'Fév' : 2,
		 u'Mar' : 3,
		 u'Avr' : 4,
		 u'Mai' : 5,
		 u'Juin' : 6,
		 u'Juil' : 7,
		 u'Aoû' : 8,
		 u'Sep' : 9,
		 u'Oct' : 10,
		 u'Nov' : 11,
		 u'Déc' : 12}

def topic_type(topic_type):
	if topic_type == None:
		return "0"
	elif u'Annonce:' in topic_type:
		return "2"
	elif u'Post-it:' in topic_type:
		return "1"
	else:
		return "0"

def fa_opener(url):
	global urlopener
	return urlopener.open(url).read()

def get_stats():
	d = PyQuery(url=config.rooturl + '/stats.htm', opener=fa_opener)

	for i in d.find("table.forumline tr"):
		e = PyQuery(i)
		
		try:
			if e("td.row2 span").eq(0).text() == "Messages":
				save.nbposts = int(e("td.row1 span").eq(0).text())
			elif e("td.row2 span").eq(0).text() == "Nombre de sujets":
				save.nbtopics = int(e("td.row1 span").eq(0).text())
			elif e("td.row2 span").eq(0).text() == "Nombre d'utilisateurs":
				save.nbusers = int(e("td.row1 span").eq(0).text())
		except:
			continue

def get_forums():
	print "Récupération des forums..."
	progress = progressbar.ProgressBar(widgets=[progressbar.SimpleProgress('/'), ' ', progressbar.Bar("#","[","]"), progressbar.Percentage()])

	d = PyQuery(url=config.rooturl + '/a-f1/', opener=fa_opener)
	
	save.forums = []
	levels = {}
	n = 1

	for i in progress([i for i in d.find("select option") if i.get("value", "-1") != "-1"]):
		id = i.get("value", "-1")
		title = re.search('(((\||\xa0)(\xa0\xa0\xa0))*)\|--([^<]+)', i.text).group(5)
		level = len(re.findall('(\||\xa0)\xa0\xa0\xa0', i.text))
		
		if level <= 0:
			parent = 0
		else:
			parent = levels[level-1]
		
		levels[level] = n
		
		d = PyQuery(url=config.rooturl+'/admin/index.forum?part=general&sub=general&mode=edit&fid=' + id + '&extended_admin=1&sid=' + sid, opener=fa_opener)
		try:
			description = d("textarea").text()
		except:
			description = ""
		
		save.forums.append({'id': int(id[1:]), 'newid': n, 'type': id[0], 'parent': parent, 'title': title, 'description': description, 'parsed': False})
		n += 1

def get_topics():
	print "Récupération des sujets..."
	progress = progressbar.ProgressBar(widgets=[progressbar.SimpleProgress('/'), ' ', progressbar.Bar("#","[","]"), progressbar.Percentage()], maxval=save.nbtopics)
	progress.start()

	n = len(save.topics)

	for forum in [i for i in save.forums if (i["type"] == "f" and i["parsed"] == False)]:
		subtopics = []
		d = PyQuery(url=config.rooturl + '/a-' + forum['type'] + str(forum['id']) + '/', opener=fa_opener)
		result = re.search('function do_pagination_start\(\)[^\}]*start = \(start > \d+\) \? (\d+) : start;[^\}]*start = \(start - 1\) \* (\d+);[^\}]*\}', d.text())

		try:
			pages = int(result.group(1))
			topicsperpages = int(result.group(2))
		except:
			pages = 1
			topicsperpages = 0
			
		for page in range(0,pages):
			if page >= 1:
				d = PyQuery(url=config.rooturl + '/a-' + forum['type'] + str(forum['id']) + '-' + str(page*topicsperpages) + '.htm', opener=fa_opener)
			
			for i in d.find('div.topictitle'):
				e = PyQuery(i)
				
				if e("strong").text() != "Annonce:" or page == 0:
					id = int(re.search("/t(\d+)-.*", e("a").attr("href")).group(1))
					f = e.parents().eq(-2)
					locked = u"verrouillé" in f("td img").eq(0).attr("alt")
					views = int(f("td").eq(5).text())
					subtopics.append({'id': id, 'type': e("strong").text(), 'parent': forum['newid'], 'title': e("a").text(), 'locked': locked, 'views': views, 'parsed': False})
					
					n += 1
					progress.update(n)
		save.topics.extend(subtopics)
		[i for i in save.forums if i == forum][0]["parsed"] = True
	progress.end()

def get_users():
	global month
	print "Récupération des membres..."
	progress = progressbar.ProgressBar(widgets=[progressbar.SimpleProgress('/'), ' ', progressbar.Bar("#","[","]"), progressbar.Percentage()], maxval=save.nbusers)
	progress.start()
	
	save.users = []
	n = 2

	d = PyQuery(url=config.rooturl+'/admin/index.forum?part=users_groups&sub=users&extended_admin=1&sid=' + sid, opener=fa_opener)
	result = re.search('function do_pagination_start\(\)[^\}]*start = \(start > \d+\) \? (\d+) : start;[^\}]*start = \(start - 1\) \* (\d+);[^\}]*\}', d.text())

	try:
		pages = int(result.group(1))
		usersperpages = int(result.group(2))
	except:
		pages = 1
		usersperpages = 0
		
	for page in range(0,pages):
		if page >= 1:
			d = PyQuery(url=config.rooturl + '/admin/index.forum?part=users_groups&sub=users&extended_admin=1&start=' + str(page*usersperpages) + '&sid=' + sid, opener=fa_opener)
		
		for i in d('tbody tr'):
			e = PyQuery(i)
			id = int(re.search("&u=(\d+)&", e("td a").eq(0).attr("href")).group(1))
			
			date = e("td").eq(3).text().split(" ")
			date = time.mktime(time.struct_time((int(date[2]),month[date[1]],int(date[0]),0,0,0,0,0,0)))
			
			lastvisit = e("td").eq(4).text()
			
			if lastvisit != "":
				lastvisit = lastvisit.split(" ")
				lastvisit = time.mktime(time.struct_time((int(lastvisit[2]),month[lastvisit[1]],int(lastvisit[0]),0,0,0,0,0,0)))
			else:
				lastvisit = 0
			
			save.users.append({'id': id, 'newid': n, 'name': e("td a").eq(0).text(), 'mail': e("td a").eq(1).text(), 'posts': int(e("td").eq(2).text()), 'date': int(date), 'lastvisit': int(lastvisit)})
			
			n += 1
			progress.update(n-2)

	progress.end()

def get_smileys():
	global n
	print "Récupération des émoticones..."

	n = 0

	d = PyQuery(url=config.rooturl+'/admin/index.forum?part=themes&sub=avatars&mode=smilies&extended_admin=1&sid=' + sid, opener=fa_opener)
	result = re.search('function do_pagination_start\(\)[^\}]*start = \(start > \d+\) \? (\d+) : start;[^\}]*start = \(start - 1\) \* (\d+);[^\}]*\}', d.text())

	try:
		pages = int(result.group(1))
		usersperpages = int(result.group(2))
	except:
		pages = 1
		usersperpages = 0
		
	progress = progressbar.ProgressBar(widgets=[BarVar(), ' ', progressbar.Bar("#","[","]"), progressbar.Percentage()], maxval=pages-1)
	progress.start()

	for page in range(0,pages):
		if page >= 1:
			d = PyQuery(url=config.rooturl + '/admin/index.forum?part=themes&sub=avatars&mode=smilies&extended_admin=1&start=' + str(page*usersperpages) + '&sid=' + sid, opener=fa_opener)
		
		for i in d('table tr'):
			e = PyQuery(i)
			if e("td").eq(0).text() != None and e("td").eq(0).attr("colspan") == None:
				save.smileys[e("td").eq(0).text()] = e("td").eq(1).text()
				n += 1
		progress.update(page)

	progress.end()

def get_posts():
	global month
	print "Récupération des messages..."
	progress = progressbar.ProgressBar(widgets=[progressbar.SimpleProgress('/'), ' ', progressbar.Bar("#","[","]"), progressbar.Percentage()], maxval=save.nbposts)
	progress.start()

	n = len(save.posts)

	for topic in [i for i in save.topics if i["parsed"] == False]:
		subposts = []
		d = PyQuery(url=config.rooturl + '/t' + str(topic['id']) + '-a', opener=fa_opener)
		result = re.search('function do_pagination_start\(\)[^\}]*start = \(start > \d+\) \? (\d+) : start;[^\}]*start = \(start - 1\) \* (\d+);[^\}]*\}', d.text())

		try:
			pages = int(result.group(1))
			topicsperpages = int(result.group(2))
		except:
			pages = 1
			topicsperpages = 0
		
		for page in range(0,pages):
			if page >= 1:
				d = PyQuery(url=config.rooturl + '/a-t' + str(topic['id']) + '-' + str(page*topicsperpages) + '.htm', opener=fa_opener)
			
			for i in d.find('tr.post'):
				e = PyQuery(i)
				
				id = int(e("td span.name a").attr("name"))
				author = e("td span.name").text()
				post = htmltobbcode.htmltobbcode(e("td div.postbody div").eq(0).html(), save.smileys)
				result = e("table td span.postdetails").text().split(" ")
				if result[-3] == "Aujourd'hui":
					title = " ".join(e("table td span.postdetails").text().split(" ")[1:-3])
					date = e("table td span.postdetails").text().split(" ")[-3:]
					timestamp = time.mktime(datetime.combine(datetime.date.today(), datetime.time(int(date[2].split(":")[0]),int(date[2].split(":")[1]))).timetuple())
				elif result[-3] == "Hier":
					title = " ".join(e("table td span.postdetails").text().split(" ")[1:-3])
					date = e("table td span.postdetails").text().split(" ")[-3:]
					timestamp = time.mktime(datetime.combine(datetime.date.today()-datetime.timedelta(1), datetime.time(int(date[2].split(":")[0]),int(date[2].split(":")[1]))).timetuple())
				else:
					title = " ".join(e("table td span.postdetails").text().split(" ")[1:-6])
					date = e("table td span.postdetails").text().split(" ")[-6:]
					timestamp = time.mktime(datetime.datetime(int(date[3]),month[date[2]],int(date[1]),int(date[5].split(":")[0]),int(date[5].split(":")[1])).timetuple())
				
				subposts.append({'id': id, 'post': post, 'title': title, 'topic': topic["id"], 'timestamp': int(timestamp), 'author': author})
				n += 1
				progress.update(n)
		save.posts.extend(subposts)
		[i for i in save.topics if i == topic][0]["parsed"] = True
	
	progress.end()

def set_left_right_id(forum=None, left=0):
	curleft = left+1
	
	if forum == None:
		forum = {'newid': 0}

	for subforum in [i for i in save.forums if i["parent"] == forum["newid"]]:
		curleft = set_left_right_id(subforum, curleft)+1
	
	if forum["newid"]:
		forum["left"] = left
		forum["right"] = curleft
	
	return curleft
	
class BarVar(progressbar.ProgressBarWidget):
	def update(self, pbar):
		global n
		return str(n)

etapes = [get_stats, get_forums, get_topics, get_users, get_smileys, get_posts]

# Connection
print "Connection au forum..."
data = urllib.urlencode({'username': config.admin_name, 'password': config.admin_password, 'autologin': 1, 'redirect': '', 'login': 'Connexion'})
request = urllib2.Request(config.rooturl + '/login.forum', data)
urlopener.open(request)

sid = None
for cookie in cookiejar:
	if cookie.name[-3:] == "sid":
		sid = cookie.value

if sid == None:
	raise ValueError('Impossible de se connecter')

try:
	for i in range(save.state,len(etapes)):
		etapes[i]()
		save.state += 1
except:
	savefile = open("save.py", "w+")
	savefile.write("# -*- coding: utf-8 -*-\n\n")
	
	savefile.write("state = " + str(save.state) + "\n\n")
	
	savefile.write("nbposts = " + str(save.nbposts) + "\n")
	savefile.write("nbtopics = " + str(save.nbtopics) + "\n")
	savefile.write("nbusers = " + str(save.nbusers) + "\n\n")
	
	savefile.write("forums = " + str(save.forums) + "\n\n")
	
	savefile.write("topics = " + str(save.topics) + "\n\n")
	
	savefile.write("posts = " + str(save.posts) + "\n\n")
	
	savefile.write("users = " + str(save.users) + "\n\n")
	
	savefile.write("smileys = " + str(save.smileys) + "\n\n")
	
	savefile.close()
	print "\n"
	traceback.print_exc(file=sys.stdout)
	sys.exit()

savefile = open("save.py", "w+")
savefile.write("# -*- coding: utf-8 -*-\n\n")

savefile.write("state = " + str(save.state) + "\n\n")

savefile.write("nbposts = " + str(save.nbposts) + "\n")
savefile.write("nbtopics = " + str(save.nbtopics) + "\n")
savefile.write("nbusers = " + str(save.nbusers) + "\n\n")

savefile.write("forums = " + str(save.forums) + "\n\n")

savefile.write("topics = " + str(save.topics) + "\n\n")

savefile.write("posts = " + str(save.posts) + "\n\n")

savefile.write("users = " + str(save.users) + "\n\n")

savefile.write("smileys = " + str(save.smileys) + "\n\n")

savefile.close()

# Génération du fichier SQL
print "Génération du fichier SQL..."
sqlfile = codecs.open('phpbb.sql', 'w+', 'utf-8')

for bbcode in phpbb.bbcodes:
	sqlfile.write('INSERT INTO ' + config.table_prefix + 'bbcodes (bbcode_id, bbcode_tag, bbcode_helpline, display_on_posting, bbcode_match, bbcode_tpl, first_pass_match, first_pass_replace, second_pass_match, second_pass_replace) VALUES ')
	sqlfile.write(bbcode)

sqlfile.write('\n')

sqlfile.write('DELETE FROM ' + config.table_prefix + 'users;\n')
sqlfile.write('DELETE FROM ' + config.table_prefix + 'user_group;\n')
sqlfile.write('DELETE FROM ' + config.table_prefix + 'bots;\n')
sqlfile.write('INSERT INTO ' + config.table_prefix + "users (user_id, user_type, group_id, username, username_clean, user_regdate, user_password, user_email, user_lang, user_style, user_rank, user_colour, user_posts, user_permissions, user_ip, user_birthday, user_lastpage, user_last_confirm_key, user_post_sortby_type, user_post_sortby_dir, user_topic_sortby_type, user_topic_sortby_dir, user_avatar, user_sig, user_sig_bbcode_uid, user_from, user_icq, user_aim, user_yim, user_msnm, user_jabber, user_website, user_occ, user_interests, user_actkey, user_newpasswd, user_allow_massemail) VALUES (1, 2, 1, 'Anonymous', 'anonymous', 0, '', '', 'fr', 1, 0, '', 0, '', '', '', '', '', 't', 'a', 't', 'd', '', '', '', '', '', '', '', '', '', '', '', '', '', '', 0);\n")
sqlfile.write("INSERT INTO " + config.table_prefix + "user_group (group_id, user_id, user_pending) VALUES('1', '1', '0');\n")

for user in save.users:
	if user["name"] == config.admin_name:
		password = hashlib.md5(config.admin_password).hexdigest()
	else:
		password = hashlib.md5(''.join(random.choice(string.letters + string.digits) for i in xrange(8))).hexdigest()
	
	data = [str(user["newid"]),							#user_id
	"3" if user["name"] == config.admin_name else "0",	#user_type
	"5" if user["name"] == config.admin_name else "2",	#group_id
	"'" + phpbb.escape_var(user["name"]) + "'",			#username
	"'" + phpbb.escape_var(user["name"] .lower()) + "'",#username_clean
	str(user["date"]),									#user_regdate
	"'" + password + "'",								#user_password
	"'" + user["mail"] + "'",							#user_email
	"'" + phpbb.email_hash(user["mail"]) + "'",			#user_email_hash
	"'fr'",												#user_lang
	"1",												#user_style
	"1" if user["name"] == config.admin_name else "0",			#user_rank
	"'AA0000'" if user["name"] == config.admin_name else "''",	#user_colour
	str(user["posts"]),									#user_posts
	"''",												#user_permissions
	"''",												#user_ip
	" 0- 0-   0",										#user_birthday
	"''",												#user_lastpage
	"''",												#user_last_confirm_key
	"'t'",												#user_post_sortby_type
	"'a'",												#user_post_sortby_dir
	"'t'",												#user_topic_sortby_type
	"'d'",												#user_topic_sortby_dir
	"''",												#user_avatar
	"''",												#user_sig
	"''",												#user_sig_bbcode_uid
	"''",												#user_from
	"''",												#user_icq
	"''",												#user_aim
	"''",												#user_yim
	"''",												#user_msnm
	"''",												#user_jabber
	"'" + str(user["lastvisit"]) + "'",					#user_lastvisit
	"''",												#user_website
	"''",												#user_occ
	"''",												#user_interests
	"''",												#user_actkey
	"''",												#user_newpasswd
	"1",												#user_pass_convert
	"2"]												#user_avatar_type
	sqlfile.write("INSERT INTO " + config.table_prefix + "users(user_id, user_type, group_id, username, username_clean, user_regdate, user_password, user_email, user_email_hash, user_lang, user_style, user_rank, user_colour, user_posts, user_permissions, user_ip, user_birthday, user_lastpage, user_last_confirm_key, user_post_sortby_type, user_post_sortby_dir, user_topic_sortby_type, user_topic_sortby_dir, user_avatar, user_sig, user_sig_bbcode_uid, user_from, user_icq, user_aim, user_yim, user_msnm, user_jabber, user_lastvisit, user_website, user_occ, user_interests, user_actkey, user_newpasswd, user_pass_convert, user_avatar_type) VALUES ")
	sqlfile.write('(' + ', '.join(data) + ');\n')

sqlfile.write("\n")

n = max([i["newid"] for i in save.users])

for bot in phpbb.bots:
	n += 1
	
	sqlfile.write("INSERT INTO " + config.table_prefix + "users(user_id, user_type, group_id, username, username_clean, user_regdate, user_password, user_colour, user_email, user_email_hash, user_lang, user_style, user_timezone, user_dateformat, user_allow_massemail) VALUES ")
	sqlfile.write("(" + str(n) + ", 2, 6, '" + bot["name"] + "', '" + bot["name"].lower() + "', " + str(int(time.time())) + ", '', '9E8DA7', '', '00', 'french', 1, 0, 'D M d, Y g:i a', 0);\n")
	
	sqlfile.write("INSERT INTO " + config.table_prefix + "user_group (group_id, user_id, user_pending, group_leader) VALUES ")
	sqlfile.write("(6, " + str(n) + ", 0, 0);\n")
	
	sqlfile.write("INSERT INTO " + config.table_prefix + "bots (bot_active, bot_name, user_id, bot_agent, bot_ip) VALUES ")
	sqlfile.write("(1, '" + bot["name"] + "', " + str(n) + ", '" + bot["agent"] + "', '" + bot["ip"] + "');\n")


sqlfile.write("\n")

for user in save.users:
	sqlfile.write("INSERT INTO " + config.table_prefix + "user_group (group_id, user_id, user_pending) VALUES ")
	sqlfile.write("(2, " + str(user['newid']) + ", 0);\n")

sqlfile.write("\n")

for user in [i for i in save.users if i["name"] == config.admin_name]:
	sqlfile.write("INSERT INTO " + config.table_prefix + "user_group (group_id, user_id, user_pending, group_leader) VALUES (4, " + str(user['newid']) + ", 0, 0);\n")
	sqlfile.write("INSERT INTO " + config.table_prefix + "user_group (group_id, user_id, user_pending, group_leader) VALUES (5, " + str(user['newid']) + ", 0, 1);\n\n")

sqlfile.write('DELETE FROM ' + config.table_prefix + 'forums;\n')
sqlfile.write('DELETE FROM ' + config.table_prefix + 'acl_groups WHERE forum_id > 0;\n')

set_left_right_id()

for forum in save.forums:
	sqlfile.write('INSERT INTO ' + config.table_prefix + 'forums (forum_id, parent_id, left_id, right_id, forum_name, forum_desc, forum_type) VALUES ')
	sqlfile.write("(" + str(forum["newid"]) + ", " + str(forum["parent"]) + ", " + str(forum["left"]) + ", " + str(forum["right"]) + ", '" + phpbb.escape_var(forum["title"]) + "', '" + phpbb.escape_var(forum["description"]) + "', " + str(int(forum["type"] == "f")) + ");\n")

sqlfile.write("\n")

for forum in save.forums:
	sqlfile.write('INSERT INTO ' + config.table_prefix + 'acl_groups (group_id, forum_id, auth_option_id, auth_role_id, auth_setting) VALUES ')
	sqlfile.write(','.join(phpbb.default_forum_acl(forum["newid"])) + ";\n")

sqlfile.write("\n")

sqlfile.write('DELETE FROM ' + config.table_prefix + 'topics;\n')
sqlfile.write('DELETE FROM ' + config.table_prefix + 'topics_posted;\n')
sqlfile.write('DELETE FROM ' + config.table_prefix + 'posts;\n\n')

for topic in save.topics:
	subposts = [i for i in save.posts if i["topic"] == topic["id"]]
	first_post = subposts[0]
	first_poster = [i for i in save.users if i["name"] == first_post["author"]][0]["newid"]
	last_post = subposts[-1]
	last_poster = [i for i in save.users if i["name"] == last_post["author"]][0]["newid"]
	data = [str(topic["id"]),							#topic_id
	topic_type(topic["type"]),							#topic_type
	str(topic["parent"]),								#forum_id
	str(first_post["id"]),								#topic_first_post_id
	"'" + phpbb.escape_var(first_post["author"]) + "'",	#topic_first_poster_name
	str(last_post["id"]),								#topic_last_post_id
	str(last_poster),									#topic_last_poster_id
	"'" + phpbb.escape_var(last_post["author"]) + "'",	#topic_last_poster_name
	"'" + phpbb.escape_var(last_post["title"]) + "'",	#topic_last_post_subject
	str(last_post["timestamp"]),						#topic_last_post_time
	str(last_poster),									#topic_poster
	str(first_post["timestamp"]),						#topic_time
	"'" + phpbb.escape_var(topic["title"]) + "'",		#topic_title
	str(len(subposts)-1),								#topic_replies
	str(len(subposts)-1),								#topic_replies_real
	str(topic["views"]),								#topic_views
	str(int(topic["locked"]))]							#topic_status
	sqlfile.write('INSERT INTO ' + config.table_prefix + 'topics (topic_id,topic_type,forum_id,topic_first_post_id,topic_first_poster_name,topic_last_post_id,topic_last_poster_id,topic_last_poster_name,topic_last_post_subject,topic_last_post_time,topic_poster,topic_time,topic_title,topic_replies,topic_replies_real,topic_views,topic_status) VALUES ')
	sqlfile.write('(' + ', '.join(data) + ');\n')

sqlfile.write("\n")

for topic in save.topics:
	l = []
	for poster in [i["author"] for i in save.posts if i["topic"] == topic["id"]]:
		id = [i for i in save.users if i["name"] == poster][0]["newid"]
		if not id in l:
			sqlfile.write("INSERT INTO " + config.table_prefix + "topics_posted (user_id, topic_id, topic_posted) VALUES ")
			sqlfile.write("(" + str(id) + ", " + str(topic["id"]) + ", 1);\n")
			l.append(id)

sqlfile.write("\n")

for post in save.posts:
	topic = [i for i in save.topics if i["id"] == post["topic"]][0]
	poster = [i for i in save.users if i["name"] == post["author"]][0]
	
	bbcode_uid = ''.join([random.choice('abcdefghijklmnopqrstuvwxyz0123456789') for i in xrange(8)])
	bbcode_bitfield = phpbb.makebitfield(post["post"]).strip()
	post["post"] = post["post"].replace(":<UID>]",":" + bbcode_uid + "]")
	checksum = hashlib.md5(post["post"].encode("utf-8")).hexdigest()
	
	data = [str(post["id"]),						#post_id
	str(post["topic"]),								#topic_id
	str(topic["parent"]),							#forum_id
	str(poster["newid"]),							#poster_id
	str(post["timestamp"]),							#post_time
	"'127.0.0.1'",									#poster_ip
	"'" + phpbb.escape_var(post["author"]) + "'",	#post_username
	"'" + phpbb.escape_var(post["title"]) + "'",	#post_subject
	"'" + phpbb.escape_var(post["post"]) + "'",		#post_text
	"'" + bbcode_uid + "'",							#bbcode_uid
	"'" + str(checksum) + "'",						#post_checksum
	"'" + bbcode_bitfield + "'"]					#bbcode_bitfield
	sqlfile.write("INSERT INTO " + config.table_prefix + "posts (post_id,topic_id,forum_id,poster_id,post_time,poster_ip,post_username,post_subject,post_text,bbcode_uid,post_checksum,bbcode_bitfield) VALUES ")
	sqlfile.write('(' + ', '.join(data) + ');\n')

sqlfile.write("\n")