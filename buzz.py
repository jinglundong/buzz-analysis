import cgi
import datetime
import urllib
import webapp2
import httplib
import json
import os
import string
import Queue
import logging

from urllib import urlencode
from google.appengine.ext import db
from google.appengine.api import users
from google.appengine.ext.webapp import template
from google.appengine.api import memcache


class Tweet(db.Model):
  """Models an individual Tweet entry with an id, text, and image etc."""
  created_at = db.DateTimeProperty()
  #from_user = db.StringProperty()
  #from_user_id = db.IntegerProperty()
  #from_user_id_str = db.StringProperty()
  from_user_name = db.StringProperty()
  #id = db.StringProperty()
  #id_str = db.StringProperty()
  #iso_language_code = db.StringProperty()
  profile_image_url = db.StringProperty()
  text = db.StringProperty(multiline=True)
  key_word = db.StringProperty(multiline=True)

class Word(db.Model):
    key_word = db.StringProperty(multiline=True);
    count = db.IntegerProperty();
    content = db.StringProperty();
  
class Search(db.Model):
    key_word = db.StringProperty();
    count = db.IntegerProperty();
    last_visit = db.DateTimeProperty();


class Main(webapp2.RequestHandler):
  history = Queue.Queue(10);
  
  def get(self):
    path = os.path.join(os.path.dirname(__file__), 'index.html')
    
    key_word=self.request.get('key_word').lower()
    encode_key_word = string.replace(key_word, " ", "%20")
    tweets = db.GqlQuery("SELECT * "
                            "FROM Tweet "
                            "WHERE key_word='" + encode_key_word + "' "
                            "ORDER BY from_user_name DESC LIMIT 20")
    temp_value = {
        'tweets' : tweets,
        'decode_key_word' : key_word,
    }
    self.response.out.write(template.render(path, temp_value))
    
  def post(self):
    path = os.path.join(os.path.dirname(__file__), 'index.html')

    key_word=self.request.get('key_word').lower()
    key_word_list = key_word.split(' ');
    encode_key_word = string.replace(key_word, " ", "%20")
    tweets = self.getTweets(key_word);
    
    #save this search
    for word in key_word_list:
        GQL="SELECT * FROM Search WHERE key_word='"+word+"'";
        q = db.GqlQuery(GQL);
        obj = q.get();
        if not obj:
            obj = Search(key_word=word,
                         count=1,
                         last_visit=datetime.datetime.now())
        else:
            obj.count+=1
            obj.last_visit=datetime.datetime.now()
        obj.put()
        
    #pass tweets to view                                
    temp_value = {
        'tweets' : tweets,
        'decode_key_word' : key_word,
    }
    self.response.out.write(template.render(path, temp_value))    

  def getTweets(self, key_words):
    results = memcache.get(key_words);
    #read from mencache
    if results is not None:
        return results
    #send request to twitter, save to mencache
    else:
        key_words = self.request.get('key_word')
        key_word_list = key_words.split(" ")
        encode_key_word = string.replace(key_words, " ", "%20")
        baseurl = "/search.json?"
        url = baseurl + urlencode({'q': key_words, 'rpp': 20})
        conn = httplib.HTTPConnection("search.twitter.com")
        logging.info(url)
        conn.request("GET", url)
        r1 = conn.getresponse()
        conn.close()
        data1 = r1.read()
        #save the tweets to both Tweet and Search in DB
        text_list = []
        if data1:
            data2 = json.loads(data1)
            for data in data2["results"]:
                tweet = Tweet()
                tweet.from_user_name = data["from_user_name"]
                tweet.text = data["text"]
                logging.info(data["text"])
                text_list += data["text"].split(' ')
                logging.info(text_list)
                #self.countWords(data["text"], key_words)
                tweet.key_word = encode_key_word
                tweet.profile_image_url = data["profile_image_url"]
                tweet.put()
        self.countWords(text_list, key_word_list)
        if(self.history.full()):
            replaced_key_words = self.history.get()
            memcache.delete(replaced_key_words);
        self.history.put(key_words);
        memcache.add(key_words, data2["results"]);
        return data2["results"];

  def countWords(self, text, key_words):
    #text_list = text.split(' ')
    text_list = text
    
    word_counter = {}
    for word in text_list:
        if word in word_counter:
            word_counter[word] += 1
        else:
            word_counter[word] = 1
    popular_words = sorted(word_counter, key = word_counter.get, reverse = True)
    top_10 = popular_words[:10]
    for key_word in key_words:
        for word in top_10:
            freq_word = Word()
            freq_word.key_word = key_word
            freq_word.count = word_counter[word]
            freq_word.content = word
            freq_word.put()

class Analysis(webapp2.RequestHandler):
    def get(self):
        key_word = self.request.get('key_word')
        if not key_word:
            q = db.GqlQuery("SELECT * FROM Search ORDER BY last_visit DESC LIMIT 1")
            for it in q:
                key_word = it.key_word
            if not key_word:
                key_word = "NULL"
        q = db.GqlQuery("SELECT key_word FROM Search ORDER BY last_visit DESC LIMIT 10")
        count = db.GqlQuery("SELECT content, count FROM Word WHERE key_word = :1 ORDER BY count DESC LIMIT 10", key_word)
        data = {}
        data['last'] = q
        data['count'] = count
        data['key_word'] = key_word
        path = os.path.join(os.path.dirname(__file__), 'analysis.html')
        self.response.out.write(template.render(path, data))
        
    

app = webapp2.WSGIApplication([('/', Main),
                               ('/analysis', Analysis)],
                              debug=True)