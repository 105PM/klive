# -*- coding: utf-8 -*-
#########################################################
# python
import os
import traceback
import time
from datetime import datetime
import urllib
import json
import threading
import io
import subprocess
import platform

# third-party
import requests
from flask import Blueprint, request, Response, send_file, render_template, redirect, jsonify, session, send_from_directory, stream_with_context
from flask_socketio import SocketIO, emit, send
from flask_login import login_user, logout_user, current_user, login_required

# sjva 공용
from framework.logger import get_logger
from framework import app, db, scheduler, path_data, socketio, path_app_root, check_api
from framework.util import Util

# 패키지
package_name = __name__.split('.')[0]
logger = get_logger(package_name)

from .model import ModelSetting
from .logic import Logic
from .logic_klive import LogicKlive

#########################################################


#########################################################
# 플러그인 공용                                       
#########################################################
blueprint = Blueprint(package_name, package_name, url_prefix='/%s' %  package_name, template_folder=os.path.join(os.path.dirname(__file__), 'templates'))

menu = {
    'main' : [package_name, 'KLive'],
    'sub' : [
        ['setting', '설정'], ['list', '전체채널'], ['custom_create', 'Custom 생성'], ['custom_edit', 'Custom 편집'], ['log', '로그']
    ],
    'category' : 'tv'
}

plugin_info = {
    'version' : '1.0',
    'name' : 'klive',
    'category_name' : 'tv',
    'developer' : 'soju6jan',
    'description' : '라이브 방송 플러그인',
    'home' : 'https://github.com/soju6jan/klive',
    'more' : '',
}

def plugin_load():
    try:
        logger.debug('plugin_load:%s', package_name)
        Logic.plugin_load()
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

process_list = []
def plugin_unload():
    try:
        logger.debug('plugin_unload:%s', package_name)
        Logic.plugin_unload()
        global process_list
        try:
            for p in process_list:
                if p is not None and p.poll() is None:
                    import psutil
                    process = psutil.Process(p.pid)
                    for proc in process.children(recursive=True):
                        proc.kill()
                    process.kill()
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())

    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())



#########################################################
# WEB Menu 
#########################################################
@blueprint.route('/')
def home():
    return redirect('/{package_name}/list'.format(package_name=package_name))

@blueprint.route('/{package_name}/proxy'.format(package_name=package_name))
def r1():
    return redirect('/{package_name}/proxy/discover.json'.format(package_name=package_name))

@blueprint.route('/<sub>')
@login_required
def first_menu(sub): 
    logger.debug('DETAIL %s %s', package_name, sub)
    try:
        from system.model import ModelSetting as SystemModelSetting
        arg = ModelSetting.to_dict()
        arg['package_name']  = package_name
        arg['ddns'] = SystemModelSetting.get('ddns')
        arg['auth_use_apikey'] = str(SystemModelSetting.get_bool('auth_use_apikey'))
        arg['auth_apikey'] = SystemModelSetting.get('auth_apikey')
        if sub == 'setting':
            arg['scheduler'] = str(scheduler.is_include(package_name))
            arg['is_running'] = str(scheduler.is_running(package_name))
            ddns = SystemModelSetting.get('ddns')
            arg['api_m3u'] = '{ddns}/{package_name}/api/m3u'.format(ddns=ddns, package_name=package_name)
            arg['api_m3utvh'] = '{ddns}/{package_name}/api/m3utvh'.format(ddns=ddns, package_name=package_name)
            arg['api_m3uall'] = '{ddns}/{package_name}/api/m3uall'.format(ddns=ddns, package_name=package_name)
            arg['xmltv'] = '{ddns}/epg/api/klive'.format(ddns=ddns)
            arg['plex_proxy'] = '{ddns}/{package_name}/proxy'.format(ddns=ddns, package_name=package_name)
            
            if SystemModelSetting.get_bool('auth_use_apikey'):
                apikey = SystemModelSetting.get('auth_apikey')
                arg['api_m3u'] += '?apikey={apikey}'.format(apikey=apikey)
                arg['api_m3uall'] += '?apikey={apikey}'.format(apikey=apikey)
                arg['api_m3utvh'] += '?apikey={apikey}'.format(apikey=apikey)
                arg['xmltv'] += '?apikey={apikey}'.format(apikey=apikey)
            from .source_streamlink import SourceStreamlink
            arg['is_streamlink_installed'] = 'Installed' if SourceStreamlink.is_installed() else 'Not Installed'
            from .source_youtubedl import SourceYoutubedl
            arg['is_youtubedl_installed'] = 'Installed' if SourceYoutubedl.is_installed() else 'Not Installed'
            return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
        elif sub == 'list':
            
            return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
        elif sub == 'custom_create':
            return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
        elif sub == 'custom_edit':
            return render_template('{package_name}_{sub}.html'.format(package_name=package_name, sub=sub), arg=arg)
        elif sub == 'proxy':
            return redirect('/klive/proxy/discover.json')
        elif sub == 'log':
            return render_template('log.html', package=package_name)
        return render_template('sample.html', title='%s - %s' % (package_name, sub))
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())

#########################################################
# For UI 
#########################################################
@blueprint.route('/ajax/<sub>', methods=['GET', 'POST'])
@login_required
def ajax(sub):
    logger.debug('AJAX %s %s', package_name, sub)
    try:
        if sub == 'setting_save':
            #old = '%s%s%s%s%s%s' % (ModelSetting.get('use_wavve'), ModelSetting.get('use_tving'), ModelSetting.get('use_videoportal'), ModelSetting.get('use_everyon'), ModelSetting.get('use_streamlink'), ModelSetting.get('streamlink_list'))
            ret = ModelSetting.setting_save(request)
            #new = '%s%s%s%s%s%s' % (ModelSetting.get('use_wavve'), ModelSetting.get('use_tving'), ModelSetting.get('use_videoportal'), ModelSetting.get('use_everyon'), ModelSetting.get('use_streamlink'), ModelSetting.get('streamlink_list'))
            #if new != old:
            LogicKlive.get_channel_list(from_site=True)
            return jsonify(ret)
        elif sub == 'channel_list':
            ret = LogicKlive.channel_list2(request)
            return jsonify(ret)
        # 커스텀 생성
        elif sub == 'custom':
            ret = {}
            ret['list'] = LogicKlive.custom()
            ret['setting'] = ModelSetting.to_dict()
            return jsonify(ret)
        elif sub == 'custom_save':
            ret = LogicKlive.custom_save(request)
            return jsonify(ret)
        elif sub == 'get_saved_custom':
            ret = LogicKlive.get_saved_custom()
            return jsonify(ret)
        elif sub == 'custom_edit_save':
            ret = LogicKlive.custom_edit_save(request)
            return jsonify(ret)
        elif sub == 'custom_delete':
            ret = LogicKlive.custom_delete(request)
            return jsonify(ret)
        elif sub == 'install':
            target = request.form['target']
            if  target == 'youtubedl':
                from .source_youtubedl import SourceYoutubedl
                SourceYoutubedl.install()
            elif target == 'streamlink':
                from .source_streamlink import SourceStreamlink
                SourceStreamlink.install()
            return jsonify({})
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())


#########################################################
# API
#########################################################
@blueprint.route('/api/<sub>', methods=['GET', 'POST'])
@check_api
def api(sub):
    #logger.debug('API %s %s', package_name, sub)
    # 설정 저장
    """
    logger.debug('XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
    logger.debug(request.remote_addr)
    headers_list = request.headers.getlist("X-Forwarded-For")
    user_ip = headers_list[0] if headers_list else request.remote_addr
    logger.debug("user_ip : %s", user_ip)
    logger.debug('access_route : %s', request.access_route[-1])
    """
    
    if sub == 'url.m3u8':
        try:
            mode = request.args.get('m')
            #if mode == 'web_play':
            #    pass
            #else:
            #   
            
            mode = request.args.get('m')
            source = request.args.get('s')
            source_id = request.args.get('i')
            quality = request.args.get('q')
            logger.debug('m:%s, s:%s, i:%s', mode, source, source_id)
            action, ret = LogicKlive.get_url(source, source_id, quality, mode)
            logger.debug('action:%s, url:%s', action, ret)
            
            if mode == 'plex':
                #logger.debug(ret)
                from system.model import ModelSetting as SystemModelSetting
                new_url = '%s/klive/api/url.m3u8?m=web_play&s=%s&i=%s&q=%s' % (SystemModelSetting.get('ddns'), source, source_id, quality)
                def generate():
                    startTime = time.time()
                    buffer = []
                    sentBurst = False
                    
                    if platform.system() == 'Windows':
                        path_ffmpeg = os.path.join(path_app_root, 'bin', platform.system(), 'ffmpeg.exe')
                    else:
                        path_ffmpeg = 'ffmpeg'

                    #ffmpeg_command = [path_ffmpeg, "-i", new_url, "-c", "copy", "-f", "mpegts", "-tune", "zerolatency", "pipe:stdout"]
                    ffmpeg_command = [path_ffmpeg, "-i", new_url, "-c:v", "copy", "-c:a", "aac", "-b:a", "128k", "-f", "mpegts", "-tune", "zerolatency", "pipe:stdout"]

                    logger.debug('command : %s', ffmpeg_command)
                    process = subprocess.Popen(ffmpeg_command, stdout = subprocess.PIPE, stderr = subprocess.STDOUT, bufsize = -1)
                    global process_list
                    process_list.append(process)
                    while True:
                        # Get some data from ffmpeg
                        line = process.stdout.read(1024)

                        # We buffer everything before outputting it
                        buffer.append(line)

                        # Minimum buffer time, 3 seconds
                        if sentBurst is False and time.time() > startTime + 1 and len(buffer) > 0:
                            sentBurst = True

                            for i in range(0, len(buffer) - 2):
                                yield buffer.pop(0)

                        elif time.time() > startTime + 1 and len(buffer) > 0:
                            yield buffer.pop(0)

                        process.poll()
                        if isinstance(process.returncode, int):
                            if process.returncode > 0:
                                logger.debug('FFmpeg Error :%s', process.returncode)
                            break

                #return Response(stream_with_context(generate()), mimetype = "video/mpeg") 
                return Response(stream_with_context(generate()), mimetype = "video/MP2T")
                #return Response(stream_with_context(generate())) 




            if action == 'redirect':
                return redirect(ret, code=302)
            elif action == 'return_after_read':
                data = LogicKlive.get_return_data(source, source_id, ret, mode)
                logger.debug('Data len : %s', len(data))
                #return data
                return data, 200, {'Content-Type': 'application/vnd.apple.mpegurl'}
                """
                #return Response(data, mimetype='application/octet-stream', as_attachment=True, attachment_filename='url.m3u8')
                #return LogicKlive.get_return_data(source, source_id, ret)
                from io import StringIO
                output_stream = StringIO(unicode(data))
                response = Response(
                    output_stream.getvalue(), 
                    mimetype='application/vnd.apple.mpegurl', 
                    content_type='application/octet-stream',
                )
                response.headers["Content-Disposition"] = "attachment; filename=url.m3u8"
                return response 
                
                ret = LogicKlive.get_return_data(source, source_id, ret)
                byteio = io.BytesIO()
                byteio.write(ret)

                filedata = byteio.getvalue()
                logger.debug('LENGTH : %s', len(filedata))
                
                
                return send_file(
                    io.BytesIO(filedata),
                    mimetype='application/octet-stream',
                    as_attachment=True,
                    attachment_filename='stream.m3u8')
                """
            elif action == 'return':
                return ret


            if ret == None: return
            if mode == 'url.m3u8':
                return redirect(ret, code=302)
            elif mode == 'lc':
                return ret

        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())  
    elif sub == 'm3uall':
        return LogicKlive.get_m3uall()
    elif sub == 'm3u':
        return LogicKlive.get_m3u()
    elif sub == 'm3utvh':
        return LogicKlive.get_m3u(for_tvh=True)
    elif sub == 'redirect':
        try:
            url = request.args.get('url')
            url = urllib.unquote(url)
            #logger.debug('REDIRECT %s', url)
            #data = requests.get(url).content
            res = requests.get(url)
            #logger.debug(res.headers)
            data = res.content
            return data, 200, {'Content-Type':res.headers['Content-Type']}
        
        except Exception as e: 
            logger.error('Exception:%s', e)
            logger.error(traceback.format_exc())


#########################################################
# Proxy
#########################################################
@blueprint.route('/proxy/<sub>', methods=['GET', 'POST'])
def proxy(sub):
    logger.debug('proxy %s %s', package_name, sub)
    try:
        if sub == 'discover.json':
            from system.model import ModelSetting as SystemModelSetting
            ddns = SystemModelSetting.get('ddns')
            data = {"FriendlyName":"HDHomeRun CONNECT","ModelNumber":"HDHR4-2US","FirmwareName":"hdhomerun4_atsc","FirmwareVersion":"20190621","DeviceID":"104E8010","DeviceAuth":"UF4CFfWQh05c3jROcArmAZaf","BaseURL":"%s/klive/proxy" % ddns,"LineupURL":"%s/klive/proxy/lineup.json" % ddns,"TunerCount":20}
            return jsonify(data)
        elif sub == 'lineup_status.json':
            data = {"ScanInProgress":0,"ScanPossible":1,"Source":"Cable","SourceList":["Antenna","Cable"]}
            return jsonify(data)
        elif sub == 'lineup.json':
            lineup = []
            custom_list = LogicKlive.get_saved_custom_instance()
            ddns = SystemModelSetting.get('ddns')
            apikey = None
            if SystemModelSetting.get_bool('auth_use_apikey'):
                apikey = SystemModelSetting.get('auth_apikey')
            for c in custom_list:
                tmp = c.get_m3u8(ddns, 'plex', apikey)
                lineup.append({'GuideNumber': str(c.number), 'GuideName': c.title, 'URL': tmp})
            return jsonify(lineup)
    except Exception as e: 
        logger.error('Exception:%s', e)
        logger.error(traceback.format_exc())