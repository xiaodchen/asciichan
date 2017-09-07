# Copyright 2016 Google Inc. All rights reserved.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import webapp2, os, jinja2, re, sys, urllib2
from xml.dom import minidom
import logging
from google.appengine.ext import db
from google.appengine.api import memcache

template_dir = os.path.join(os.path.dirname(__file__), 'template')
jinja_env = jinja2.Environment(loader = jinja2.FileSystemLoader(template_dir), 
								autoescape = True)
IP_URL = 'http://api.hostip.info/?ip='
def get_coords(ip): 
	ip = '4.2.2.2'
	url = IP_URL + ip
	content = None
	try: 
		content = urllib2.urlopen(url).read()
	except urllib2.URLError: 
		return 

	if content: 
		#parse xml find coordinates 
		d = minidom.parseString(content)
		coords = d.getElementsByTagName('gml:coordinates')
		if coords and coords[0].childnodes[0].nodeValue: 
			lon, lat = coords[0].childnodes[0].nodeValue.split(',')
			return db.GeoPt(lat, lon)

GMAPS_URL = "http://maps.googleapis.com/maps/api/staticmap?size=380x263&sensor=false&"
def gmaps_url(points): 
	markers = '&'.join('markers=%s,%s' %(p.lat, p.lon) for p in points)
	return GMAPS_URL+ markers

class Art(db.Model): 
	title = db.StringProperty(required = True)
	art = db.TextProperty(required = True)
	created = db.DateTimeProperty(auto_now_add = True)
	coords = db.GeoPtProperty()


class Handler(webapp2.RequestHandler): 
	def write(self, *a, **kw): 
		self.response.out.write(*a, **kw)

	def render_str(self, template, **params): 
		t = jinja_env.get_template(template)
		return t.render(params)

	def render(self, template, **kw): 
		self.write(self.render_str(template, **kw))

def top_arts(update = False): 
	key = 'top'
	arts = memcache.get(key)
	if arts is None or update: 
		logging.error('db query')
		arts = db.GqlQuery('SELECT * FROM Art ORDER BY created DESC LIMIT 10')
		arts = list(arts)
		memcache.set(key, arts)
	return arts		

class MainPage(Handler): 
	def render_front(self, title = '', art = '', error = ''): 
		arts = top_arts()

		points = filter(None, (a.coords for a in arts))
		img_url = None
		if points: 
			img_url = gmaps_img(points)

		self.render('front.html', title = title, art = art, error = error, arts = arts)

	def get(self):
		self.write(repr(get_coords(self.request.remote_addr)))
		self.render_front()

	def post(self): 
		title = self.request.get('title')
		art = self.request.get('art')
		if title and art: 
			a = Art(title = title, art = art)
			# look up coordinate using IP
			# add coordinates to art 
			coords = get_coords(self.request.remote_addr)
			if coords: 
				a.coords = coords 
			a.put()
			top_arts(True)
			self.redirect('/')
		else: 
			error = 'we need both a title and some artwork!'
			self.render_front(title, art, error)

app = webapp2.WSGIApplication([('/', MainPage),
							  ], debug = True)

 