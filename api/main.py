import os
import logging
import image
import utils
import insults
import tournament
import audiodb
import requests
import json
import threading
import random
import sys
import shutil
from datetime import datetime
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import Flask, request, send_file, Response, jsonify, render_template, make_response, after_this_request, g
from flask_restx import Api, Resource, reqparse
from flask_apscheduler import APScheduler
from chatterbot.conversation import Statement
from flask_caching import Cache
from markovipy import MarkoviPy
from pathlib import Path
from os.path import join, dirname
from dotenv import load_dotenv

dotenv_path = join(dirname(__file__), '.env')
load_dotenv(dotenv_path)

logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=int(os.environ.get("LOG_LEVEL")),
        datefmt='%Y-%m-%d %H:%M:%S')
log = logging.getLogger('werkzeug')
log.setLevel(int(os.environ.get("LOG_LEVEL")))

TMP_DIR = os.environ.get("TMP_DIR")
TMP_DIR_DISCORD = os.environ.get("TMP_DIR_DISCORD")
ADMIN_PASS = os.environ.get("ADMIN_PASS")
API_USER = os.environ.get("API_USER")
API_PASS = os.environ.get("API_PASS")

app = Flask(__name__)
class Config:    
    CACHE_TYPE = os.environ['CACHE_TYPE']
    CACHE_REDIS_HOST = os.environ['CACHE_REDIS_HOST']
    CACHE_REDIS_PORT = os.environ['CACHE_REDIS_PORT']
    CACHE_REDIS_DB = os.environ['CACHE_REDIS_DB']
    CACHE_REDIS_URL = os.environ['CACHE_REDIS_URL']
    CACHE_DEFAULT_TIMEOUT = os.environ['CACHE_DEFAULT_TIMEOUT']
    SCHEDULER_API_ENABLED = True

scheduler = APScheduler()

limiter = Limiter(
    key_func=get_remote_address,
    default_limits=["10/minute"],
    storage_uri="memory://",
)

app.config.from_object(Config())
cache = Cache(app)
api = Api(app)

nstext = api.namespace('chatbot_text', 'Accumulators Chatbot Text APIs')

parserinsult = reqparse.RequestParser()
parserinsult.add_argument("text", type=str)
parserinsult.add_argument("chatid", type=str)

def get_response_str(text: str):
    r = Response(response=text, status=200, mimetype="text/xml")
    r.headers["Content-Type"] = "text/xml; charset=utf-8"
    return r

def get_response_json(data):
    r = Response(response=data, status=200, mimetype="application/json")
    r.headers["Content-Type"] = "application/json; charset=utf-8"
    return r

@nstext.route('/repeat/<string:text>/')
@nstext.route('/repeat/<string:text>/<string:chatid>')
class TextRepeatClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    return get_response_str(text)

@nstext.route('/random/')
@nstext.route('/random/<string:chatid>')
class TextRandomClass(Resource):
  @cache.cached(timeout=2, query_string=True)
  def get (self, chatid = "000000"):
    response = get_response_str(utils.get_random_from_bot(chatid))
    return response

@nstext.route('/repeat/learn/<string:text>/')
@nstext.route('/repeat/learn/<string:text>/<string:chatid>')
class TextRepeatLearnClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    #get_chatbot_by_id(chatid).get_response(text)
    #threading.Timer(0, , args=[text]).start()
    response = get_response_str(text)
    response.call_on_close(get_chatbot_by_id(chatid).get_response(text)) 
    return response


@nstext.route('/repeat/learn/user/<string:user>/<string:text>/')
@nstext.route('/repeat/learn/user/<string:user>/<string:text>/<string:chatid>')
class AudioRepeatLearnUserClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, user: str, text: str, chatid = "000000"):
    if user in previousMessages:
      utils.learn(previousMessages[user], text, get_chatbot_by_id(chatid))
    previousMessages[user] = text
    return get_response_str(text)


@nstext.route('/ask/<string:text>/')
@nstext.route('/ask/<string:text>/<string:chatid>')
class TextAskClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    return get_response_str(get_chatbot_by_id(chatid).get_response(text).text)


@nstext.route('/ask/nolearn/<string:text>/')
@nstext.route('/ask/nolearn/<string:text>/<string:chatid>')
class TextAskNoLearnClass(Resource):
  def get (self, text: str, chatid = "000000"):
    return get_response_str(get_chatbot_by_id(chatid).get_response(text, learn=False).text)


@nstext.route('/ask/user/<string:user>/<string:text>/')
@nstext.route('/ask/user/<string:user>/<string:text>/<string:chatid>')
class TextAskUserClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, user: str, text: str, chatid = "000000"):
    dolearn = False;
    if user not in previousMessages:
      dolearn=True
    chatbot_response = get_chatbot_by_id(chatid).get_response(text, learn=dolearn).text
    if user in previousMessages:
      utils.learn(previousMessages[user], text, get_chatbot_by_id(chatid))
    previousMessages[user] = chatbot_response
    return get_response_str(chatbot_response)


@nstext.route('/search/<string:text>/')
@nstext.route('/search/<string:text>/<string:chatid>')
class TextSearchClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    return get_response_str(utils.wiki_summary(text))


@nstext.route('/learn/<string:text>/<string:response>/')
@nstext.route('/learn/<string:text>/<string:response>/<string:chatid>')
class TextLearnClass(Resource):
  @cache.cached(timeout=10, query_string=True)
  def get (self, text: str, response: str, chatid = "000000"):
    utils.learn(text, response, get_chatbot_by_id(chatid))
    return "Ho imparato: " + text + " => " + response


@nstext.route('/insult')
class TextInsultClass(Resource):
  @api.expect(parserinsult)
  def get (self):
    sentence = insults.get_insults()
    #get_chatbot_by_id(chatid).get_response(sentence)
    chatid = request.args.get("chatid")
    if chatid is None:
      chatid = "000000"
    #threading.Timer(0, get_chatbot_by_id(chatid).get_response, args=[sentence]).start()
    text = request.args.get("text")
    if text and text != '' and text != 'none':
      sentence = text + " " + sentence
    
    response = Response(sentence)
    response.call_on_close(get_chatbot_by_id(chatid).get_response(sentence)) 
    return response



@nstext.route('/tournament')
class TextTournamentClass(Resource): 
  def post (self):
    return jsonify(tournament.generate_tournament(request.get_json()));

@nstext.route('/tournament/regen')
class TextTournamentRegenClass(Resource): 
  def post (self):
    content = request.get_json()
    return jsonify(tournament.regen_tournament(content['author'], content['name'], content['description']));


nsaudio = api.namespace('chatbot_audio', 'Accumulators Chatbot TTS audio APIs')


@nsaudio.route('/repeat/<string:text>/<string:voice>/')
@nsaudio.route('/repeat/<string:text>/<string:voice>/<string:chatid>')
class AudioRepeatClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, voice: str, chatid = "000000"):
    try:
      tts_out = utils.get_tts(text, chatid=chatid, voice=voice, timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioRepeatClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioRepeatClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/download/<int:id>')
class AudioDownloadClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, id: int):
    try:
      tts_out = utils.download_tts(id)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioDwonloadClass.get, self, int)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioDwonloadClass.get, self, int)
        return make_response(g.get('request_error'), 500)
      


@nsaudio.route('/random/')
@nsaudio.route('/random/<string:voice>/')
@nsaudio.route('/random/<string:voice>/<int:timeout>/')
@nsaudio.route('/random/<string:voice>/<int:timeout>/<string:chatid>')
class AudioRandomClass(Resource):
  @cache.cached(timeout=2, query_string=True)
  def get (self, voice = "google", timeout = 120, chatid = "000000"):
    try:
      tts_out = utils.get_tts(utils.get_random_from_bot(chatid), chatid=chatid, voice=voice, timeout=timeout, israndom=True)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioRepeatClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioRepeatClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)
      

@nsaudio.route('/repeat/learn/<string:text>/<string:voice>/')
@nsaudio.route('/repeat/learn/<string:text>/<string:voice>/<string:chatid>')
class AudioRepeatLearnClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, voice: str, chatid = "000000"):
    #get_chatbot_by_id(chatid).get_response(text)
    #threading.Timer(0, get_chatbot_by_id(chatid).get_response, args=[text]).start()
    try:
      tts_out = utils.get_tts(text, chatid=chatid, voice=voice, timeout=120)
      if tts_out is not None:
        response = send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
        response.call_on_close(get_chatbot_by_id(chatid).get_response(text)) 
        return response
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioRepeatLearnClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioRepeatLearnClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/repeat/learn/user/<string:user>/<string:text>/<string:voice>/')
@nsaudio.route('/repeat/learn/user/<string:user>/<string:text>/<string:voice>/<string:chatid>')
class AudioRepeatLearnUserClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, user: str, text: str, voice: str, chatid = "000000"):
    try:
      tts_out = utils.get_tts(text, chatid=chatid, voice=voice, timeout=120)
      if tts_out is not None:     
        def learnthis(user: str, text: str):
          if user in previousMessages:
            utils.learn(previousMessages[user], text, get_chatbot_by_id(chatid))
          previousMessages[user] = text  
        response = send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
        response.call_on_close(learnthis(user,text)) 
        return response
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioRepeatLearnUserClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioRepeatLearnUserClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/ask/<string:text>/')
@nsaudio.route('/ask/<string:text>/<string:chatid>')
class AudioAskClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    try:
      tts_out = utils.get_tts(get_chatbot_by_id(chatid).get_response(text).text, chatid=chatid, timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioAskClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioAskClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/ask/nolearn/<string:text>/')
@nsaudio.route('/ask/nolearn/<string:text>/<string:chatid>')
class AudioAskNoLearnClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    try:
      text_response = get_chatbot_by_id(chatid).get_response(text, learn=False).text
      tts_out = utils.get_tts(text_response, chatid=chatid, timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioAskNoLearnClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioAskNoLearnClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/ask/nolearn/random/<string:text>/')
@nsaudio.route('/ask/nolearn/random/<string:text>/<string:chatid>')
class AudioAskNoLearnRandomClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, text: str, chatid = "000000"):
    try:
      text_response = get_chatbot_by_id(chatid).get_response(text, learn=False).text
      tts_out = utils.get_tts(text_response, voice="random", chatid=chatid, timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioAskNoLearnRandomClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioAskNoLearnRandomClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/ask/nolearn/nocache/google/<string:text>/')
@nsaudio.route('/ask/nolearn/nocache/google/<string:text>/<string:chatid>')
class AudioAskNoLearnNoCacheGoogleClass(Resource):
  #@cache.cached(timeout=1, query_string=True)
  def get (self, text: str, chatid = "000000"):
    try:
      text_response = get_chatbot_by_id(chatid).get_response(text, learn=False).text
      tts_out = utils.get_tts(text_response, voice="google", chatid=chatid, timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        return make_response('request_error', 500)
    except Exception as e:
      g.request_error = str(e)
      return make_response(g.get('request_error'), 500)


@nsaudio.route('/ask/user/<string:user>/<string:text>/')
@nsaudio.route('/ask/user/<string:user>/<string:text>/<string:chatid>')
class AudioAskUserClass(Resource):
  @cache.cached(timeout=7200, query_string=True)
  def get (self, user: str, text: str, chatid = "000000"):
    dolearn = False;
    if user not in previousMessages:
      dolearn=True
    chatbot_response = get_chatbot_by_id(chatid).get_response(text, learn=dolearn).text
    if user in previousMessages:
      utils.learn(previousMessages[user], text, get_chatbot_by_id(chatid))
    previousMessages[user] = chatbot_response
    try:
      tts_out = utils.get_tts(chatbot_response, chatid=chatid, timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioAskUserClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioAskUserClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)

@nsaudio.route('/search/<string:text>/')
@nsaudio.route('/search/<string:text>/<string:chatid>')
class AudioSearchClass(Resource):
  @cache.cached(timeout=10, query_string=True)
  def get (self, text: str, chatid = "000000"):
    try:
      tts_out = utils.get_tts(utils.wiki_summary(text), chatid=chatid, voice="null", timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        @after_this_request
        def clear_cache(response):
          cache.delete_memoized(AudioSearchClass.get, self, str, str, str)
          return make_response("TTS Generation Error!", 500)
    except Exception as e:
      g.request_error = str(e)
      @after_this_request
      def clear_cache(response):
        cache.delete_memoized(AudioSearchClass.get, self, str, str, str)
        return make_response(g.get('request_error'), 500)


@nsaudio.route('/insult')
class AudioInsultClass(Resource):
  @api.expect(parserinsult)
  def get (self):
    sentence = insults.get_insults()
    #get_chatbot_by_id(chatid).get_response(sentence)
    chatid = request.args.get("chatid")
    if chatid is None:
      chatid = "000000"
    #threading.Timer(0, get_chatbot_by_id(chatid).get_response, args=[sentence]).start()
    text = request.args.get("text")
    try:
      if text and text != '' and text != 'none':
        sentence = text + " " + sentence
      tts_out = utils.get_tts(sentence, chatid=chatid, voice="google", timeout=120)
      if tts_out is not None:    
        response = send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
        response.call_on_close(get_chatbot_by_id(chatid).get_response(sentence)) 
        return response
      else:
        resp = make_response("TTS Generation Error!", 500)
        return resp
    except Exception as e:
      return make_response(str(e), 500)

nsmusic = api.namespace('chatbot_music', 'Accumulators Chatbot Music APIs')

parserurl = reqparse.RequestParser()
parserurl.add_argument("url", type=str)


@nsmusic.route('/youtube/get')
class YoutubeGetClass(Resource):
  @api.expect(parserurl)
  def get(self):
    url = request.args.get("url")
    audio = utils.get_youtube_audio(url)
    return send_file(audio, attachment_filename='audio.mp3', mimetype='audio/mp3')


@nsmusic.route('/youtube/info')
class YoutubeInfoClass(Resource):
  @api.expect(parserurl)
  def get(self):
    url = request.args.get("url")
    return utils.get_youtube_info(url)

parsersearch = reqparse.RequestParser()
parsersearch.add_argument("text", type=str)
parsersearch.add_argument("onevideo", type=str)


@nsmusic.route('/youtube/search')
class YoutubeSearchClass(Resource):
  @api.expect(parsersearch)
  def get(self):
    text = request.args.get("text")
    onevideo = request.args.get("onevideo")
    return utils.search_youtube_audio(text, bool(onevideo))

nsjokestext = api.namespace('jokes_text', 'Accumulators Jokes APIs')


@nsjokestext.route('/chuck')
class TextChuckClass(Resource):
  @cache.cached(timeout=2)
  def get(self):
    return get_response_str(utils.get_joke("CHUCK_NORRIS"))


@nsjokestext.route('/random')
class TextRandomJokeClass(Resource):
  def get(self):
    return get_response_str(utils.get_joke(""))

nsjokesaudio = api.namespace('jokes_audio', 'Accumulators Jokes Audio APIs')


@nsjokesaudio.route('/chuck')
class AudioChuckClass(Resource):
  def get(self):
    try:
      text = utils.get_joke("CHUCK_NORRIS")
      tts_out = utils.get_tts(text, chatid="000000", voice="google", timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        resp = make_response("TTS Generation Error!", 500)
        return resp
    except Exception as e:
      return make_response(g.get('request_error'), 500)


@nsjokesaudio.route('/random')
class AudioRandomJokeClass(Resource):
  def get(self):
    try:
      text = utils.get_joke("")
      tts_out = utils.get_tts(text, chatid="000000", voice="google", timeout=120)
      if tts_out is not None:
        return send_file(tts_out, attachment_filename='audio.mp3', mimetype='audio/mpeg')
      else:
        resp = make_response("TTS Generation Error!", 500)
        return resp
    except Exception as e:
      return make_response(str(e), 500)


nswebtext = api.namespace('reddit', 'Accumulators Reddit APIs')


@nswebtext.route('/search/<string:word>')
class TextRedditSearchClass(Resource):
  def get(self, word: str):
    return jsonify(reddit.search(word).__dict__)



nsimages = api.namespace('images', 'Accumulators Images APIs')


@nsimages.route('/search/<string:words>')
class AudioSearchClass(Resource):
  def get (self, words: str):
    #threading.Timer(0, get_chatbot_by_id(chatid).get_response, args=[words]).start()
    bytes_img, attachment_filename, mimetype = image.search(words)
    return send_file(bytes_img, attachment_filename=attachment_filename, mimetype=mimetype)

#nswebtext = api.namespace('twitter', 'Accumulators Twitter APIs')

#@nswebtext.route('/search/random/byhashtag/<string:word>')
#class TextTwitterLocalSearchClass(Resource):
#  @cache.cached(timeout=1, query_string=True)
#  def get(self, word: str):
#    return jsonify(twitter.search_random(word, sched, 0).__dict__)

#@nswebtext.route('/search/random')
#class TextTwitterRandomSearchClass(Resource):
#  @cache.cached(timeout=1, query_string=True)
#  def get(self):
#    return jsonify(twitter.search_all_random())

#for tw_search in twitter.get_all_searches():
#  sched.add_job(twitter.scrape, 'interval', args=[tw_search,50], hours=2, id=tw_search)


#nswebhook = api.namespace('webhooks', 'Accumulators Webhooks APIs')

#@nswebhook.route('/test', methods=['POST'])
#class WebhookTest(Resource):
#  def webhook():
#    if request.method == 'POST':
#      print(str(datetime.now()) + " -","Data received from Webhook is: ", request.json)
#    return "Webhook received!"



nsutils = api.namespace('utils', 'AccumulatorsUtils APIs')


@nsutils.route('/fakeyou/get_voices_by_cat/')
@nsutils.route('/fakeyou/get_voices_by_cat/<string:category>')
class FakeYouGetVoicesByCatClass(Resource):
  def get(self, category = "Italiano"):
    return jsonify(utils.get_fakeyou_voices(category))


@nsutils.route('/download/<string:filename>')
class UtilsDownloadClass(Resource):
  def get(self, filename: str):
    try:
      filepath = TMP_DIR_DISCORD + '/' + filename
      return send_file(filepath, attachment_filename='audio.mp3', mimetype='audio/mpeg')
    except Exception as e:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
      logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)
      return get_response_str("Error downloading from server.")

@limiter.limit("1/second")
@nsutils.route('/healthcheck')
class Healthcheck(Resource):
  def get (self):
    return "Ok!"



nsdatabase = api.namespace('database', 'Accumulators Database APIs')

@nsdatabase.route('/sentence/populate/<int:count>/')
@nsdatabase.route('/sentence/populate/<int:count>/<string:chatid>')
class UtilsPopulateSentences(Resource):
  def get (self, count: int, chatid = "000000"):
    threading.Timer(0, utils.populate_new_sentences, args=[get_chatbot_by_id(chatid), count, None, False, chatid]).start()
    return "Starting thread populate_new_sentences with parameters: " + str(count) + ", None. Watch the logs."


@nsdatabase.route('/sentence/populate/parsed/<int:count>/<string:word>/')
@nsdatabase.route('/sentence/populate/parsed/<int:count>/<string:word>/<string:chatid>')
class UtilsPopulateSentencesParsed(Resource):
  def get (self, count: int, word: str, chatid = "000000"):
    threading.Timer(0, utils.populate_new_sentences, args=[get_chatbot_by_id(chatid), count, word, False, chatid]).start()
    return "Starting thread populate_new_sentences with parameters: " + str(count) + ", " + word + ". Watch the logs."


@nsdatabase.route('/sentence/populate/parsed/api/<string:word>/')
@nsdatabase.route('/sentence/populate/parsed/api/<string:word>/<string:chatid>')
class UtilsPopulateSentencesParsedApi(Resource):
  def get (self, word: str, chatid = "000000"):
    return get_response_str(utils.populate_new_sentences(get_chatbot_by_id(chatid), 5, word, True, chatid))


@nsdatabase.route('/sentence/populate/api/')
@nsdatabase.route('/sentence/populate/api/<string:chatid>')
class UtilsPopulateSentencesApi(Resource):
  def get (self, chatid = "000000"):
    return get_response_str(utils.populate_new_sentences(get_chatbot_by_id(chatid), 5, None, True, chatid))


@nsdatabase.route('/delete/bytext/<string:text>/')
@nsdatabase.route('/delete/bytext/<string:text>/<string:chatid>')
class UtilsDeleteByText(Resource):
  def get (self, text: str, chatid = "000000"):
    #return get_response_str(utils.delete_by_text(chatid, text))
    return get_response_str('Frasi con parola chiave "' + text + '" cancellate dal db chatbot!')



@nsdatabase.route('/audiodb/populate/')
@nsdatabase.route('/audiodb/populate/<int:count>/')
@nsdatabase.route('/audiodb/populate/<int:count>/<string:chatid>')
class UtilsAudiodbPopulate(Resource):
  def get (self, count = 100, chatid = "000000"):
    threading.Timer(0, utils.populate_audiodb, args=[chatid, count]).start()
    return "Starting thread populate_audiodb. Watch the logs."

	

@nsdatabase.route('/upload/trainfile/json')
class UtilsTrainFile(Resource):
  def post (self):    
    try:
      chatid = request.form.get("chatid")
      if chatid is None:
        chatid = "000000"
      threading.Timer(0, utils.train_json, args=[request.get_json(), get_chatbot_by_id(chatid)]).start()
      return get_response_str("Done. Watch the logs for errors.")
    except Exception as e:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
      logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)
      return utils.empty_template_trainfile_json()
	

@nsdatabase.route('/upload/trainfile/txt')
class UtilsTrainFile(Resource):
  def post (self):
    try:
      chatid = request.form.get("chatid")
      if chatid is None:
        chatid = "000000"
      trf=request.files['trainfile']
      if not trf and allowed_file(trf):
        return get_response_str("Error! Please upload a file name trainfile.txt with a sentence per line.")
      else:
        trainfile=TMP_DIR + '/' + utils.get_random_string(24) + ".txt"
        trf.save(trainfile)
        threading.Timer(0, utils.train_txt, args=[trainfile, get_chatbot_by_id(chatid), request.form.get("language")]).start()
        return get_response_str("Done. Watch the logs for errors.")
    except Exception as e:
      exc_type, exc_obj, exc_tb = sys.exc_info()
      fname = os.path.split(exc_tb.tb_frame.f_code.co_filename)[1]
      logging.error("%s %s %s", exc_type, fname, exc_tb.tb_lineno, exc_info=1)
      return get_response_str("Error! Please upload a file name trainfile.txt with a sentence per line.")

@nsdatabase.route('/jokes/scrape')
class ScrapeJokesObj(Resource):
  def get (self):
    threading.Timer(0, utils.scrape_jokes, args=[]).start()
    return "Starting thread scrape_jokes. Watch the logs."

@nsdatabase.route('/backup/chatbot/')
@nsdatabase.route('/backup/chatbot/<string:chatid>')
class BackupChatbot(Resource):
  def get (self, chatid = "000000"):
    utils.backupdb(chatid)
    return "Databases backed up!"

@nsdatabase.route('/restore/chatbot/')
@nsdatabase.route('/restore/chatbot/<string:text>/')
@nsdatabase.route('/restore/chatbot/<string:text>/<string:chatid>')
class RestoreChatbot(Resource):
  def get (self, text = None, chatid = "000000"):
    outtxt = utils.restore(chatid, text)
    return send_file(outtxt, attachment_filename='trainfile.txt', mimetype="text/plain")


nsadmin = api.namespace('admin', 'Accumulators Admin APIs')
@nsadmin.route('/forcedelete/bytext/<string:password>/<string:text>/')
@nsadmin.route('/forcedelete/bytext/<string:password>/<string:text>/<string:chatid>')
class AdminForceDeleteByText(Resource):
  def get (self, password: str, text: str, chatid = "000000"):
    if password == ADMIN_PASS:
      return get_response_str(utils.delete_by_text(chatid, text, force=True))
    else:
      return get_response_str("cazzo fai, non sei autorizzato a usare sto schifo di servizio! fuori dalle palle!")

@app.route('/upload')
def upload_file():
  return render_template('upload.html')

@app.route('/manager')
def manager():
  voices = utils.get_fakeyou_voices()
  datas = audiodb.select_by_chatid()
  audios = []
  for data in datas:
    key = [k for k, v in voices.items() if v == data[4]][0]
    internal = []
    internal.append(data[0])
    internal.append(data[1])
    internal.append("https://"+API_USER+":"+API_PASS+"@discord-voicebot.fabiovalentino.it/chatbot_audio/download/"+ str(data[0]))
    internal.append(key)
    internal.append(data[5])
    audios.append(internal)

  return render_template('manager.html', audios=audios)





def get_chatbot_by_id(chatid = "000000"):
  if chatid not in chatbots_dict:
    chatbots_dict[chatid] = utils.get_chatterbot(chatid, os.environ['TRAIN'] == "True")
#    scheduler.add_job(
#        func=utils.populate_new_sentences,
#        trigger="cron",
#        args=[chatbots_dict[chatid], 100, None, False, chatid],
#        hour=4,
#        minute=10,
#        second=0,
#        id="populate_sentences_chatid_"+chatid,
#        name="populate_sentences_chatid_"+chatid,
#        misfire_grace_time=900,
#        replace_existing=True
#    )
  return chatbots_dict[chatid]
  
  
  
@scheduler.task('interval', id='scrape_jokes', hours=12, misfire_grace_time=900)
def scrape_jokes():
  utils.scrape_jokes()
  
@scheduler.task('interval', id='login_fakeyou', hours=11, misfire_grace_time=900)
def login_fakeyou():
  utils.login_fakeyou()
  
@scheduler.task('interval', id='populate_audiodb', hours=5, misfire_grace_time=900)
def populate_audiodb():
  utils.populate_audiodb("000000", 20)
  
@scheduler.task('interval', id='backupdb', hours=24, misfire_grace_time=900)
def backupdb():
  utils.backupdb("000000")


#@scheduler.task('cron', id='populate_sentences', hour=4, minute=10, second=0, misfire_grace_time=900)
#def populate_sentences():
#  print(str(datetime.now()) + " -",utils.populate_new_sentences(chatbot, 1000, None, False))




#if not app.debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
previousMessages = {}
chatbots_dict = {}
audiodb.create_empty_tables()
#chatbot = utils.get_chatterbot(os.environ['TRAIN'] == "True")
#twitter.create_empty_tables()
tournament.create_empty_tables()
cache.init_app(app)
limiter.init_app(app)
scheduler.init_app(app)
scheduler.start()
utils.login_fakeyou()
threading.Timer(30, utils.backupdb, args=["000000"]).start()

if __name__ == '__main__':
  app.run()
