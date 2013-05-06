#!/usr/bin/env python
# coding=utf-8

import json
import logging
import re
import urllib
import urllib2
import urlparse

from collections import defaultdict


IPNET_URL = "http://tv.ipnet.ua/ipnet.m3u"
TVHEADEND_URL = "http://192.168.0.54:9981"
INTERFACE = "vlan3"
CHANNEL_NAME_RE = re.compile(r"^#EXTINF:\d+,(.*)")
CHANNEL_URL_RE = re.compile(r"^udp://@(\d{1,3}(?:\.\d{1,3}){3}):(\d+)/?$")
IPTV_SERVICES_URL = urlparse.urljoin(TVHEADEND_URL, "iptv/services")


logging.basicConfig()
log = logging.getLogger(__name__)
log.setLevel(logging.DEBUG)


def iter_ipnet_channels():
    """Return tuples name, channel_ip, channel_port"""
    channel_name = ""
    for line in urllib2.urlopen(IPNET_URL):
        channel_name_match = CHANNEL_NAME_RE.match(line)
        if channel_name_match:
            channel_name = channel_name_match.group(1).decode('utf-8')
        channel_url_match = CHANNEL_URL_RE.match(line)
        if channel_url_match:
            channel_ip = channel_url_match.group(1)
            channel_port = int(channel_url_match.group(2))
            yield channel_name, channel_ip, channel_port
            channel_name = ""


def tvheadend_new_channel_factory():
    data = urllib.urlencode({"op": "create"})
    http_response = urllib2.urlopen(IPTV_SERVICES_URL, data)
    response = json.load(http_response)
    assert ("id" in response and "channelname" in response
            and "interface" in response and "group" in response
            and "port" in response and "port" in response
            and "enabled" in response), response
    assert http_response.getcode() == 200, http_response.getcode()
    log.debug("Created new channel %s", response["id"])
    return response
    

def get_tvheadend_channels():
    data = urllib.urlencode({"op": "get"})
    response = json.load(urllib2.urlopen(IPTV_SERVICES_URL, data))
    return defaultdict(tvheadend_new_channel_factory,
                       [(e["channelname"], e) for e in response["entries"]])


def get_tvheadend_ids():
    data = urllib.urlencode({"op": "get"})
    response = json.load(urllib2.urlopen(IPTV_SERVICES_URL, data))
    return set([e["id"] for e in response["entries"]])


def get_update_values(tvheadend_channels, name, host, port):
    old_entry = tvheadend_channels[name]
    update_entry = {"id": old_entry["id"]}
    if name != old_entry['channelname']:
        update_entry['channelname'] = name
    if INTERFACE != old_entry['interface']:
        update_entry['interface'] = INTERFACE
    if host != old_entry['group']:
        update_entry['group'] = host
    if port != old_entry['port']:
        update_entry['port'] = port
    return update_entry


def do_tvheadend_update(update_entity_list):
    if not update_entity_list:
        log.debug("Nothing to update")
        return

    json_entity_list = json.dumps(update_entity_list, ensure_ascii=False)
    log.debug("Update entities %s", json_entity_list)
    data = urllib.urlencode({"op": "update",
                             "entries": json_entity_list.encode('utf-8')})
    response = urllib2.urlopen(IPTV_SERVICES_URL, data)
    log.debug("Update response: %s: %s", response.getcode(), response.read())


def do_tvheadend_delete(new_channel_ids):
    old_channel_ids = get_tvheadend_ids()
    expired_ids = old_channel_ids - new_channel_ids
    if not expired_ids:
        log.debug("Nothing to delete")
        return

    json_id_list = json.dumps(list(expired_ids), ensure_ascii=False)
    log.debug("IDs to delete %s", json_id_list)
    data = urllib.urlencode({"op": "delete", "entries": json_id_list})
    response = urllib2.urlopen(IPTV_SERVICES_URL, data)
    log.debug("Delete reponse: %s: %s", response.getcode(), response.read())


ipnet_channels = [entry for entry in iter_ipnet_channels()]
tvheadend_channels = get_tvheadend_channels()
update_entity_list = []
new_channel_ids = set()
for name, host, port in ipnet_channels:
    update_entity = get_update_values(tvheadend_channels, name, host, port)
    new_channel_ids.add(update_entity["id"])
    if len(update_entity) > 1:
        update_entity_list.append(update_entity)

do_tvheadend_update(update_entity_list)
do_tvheadend_delete(new_channel_ids)
