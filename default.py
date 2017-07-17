import sys
import os
import socket
import re
import random,xbmcplugin,xbmcgui, datetime, time, urllib,urllib2
import xml.etree.ElementTree as ET
import hashlib
import xbmcaddon
import ssl

# Shared resources

ampache = xbmcaddon.Addon("plugin.audio.ampache")

ampache_dir = xbmc.translatePath( ampache.getAddonInfo('path') )
BASE_RESOURCE_PATH = os.path.join( ampache_dir, 'resources' )
mediaDir = os.path.join( BASE_RESOURCE_PATH , 'media' )
cacheDir = os.path.join( mediaDir , 'cache' )
imagepath = os.path.join( mediaDir ,'images')


#   string to bool function : from string 'true' or 'false' to boolean True or
#   False, raise ValueError
def str_to_bool(s):
    if s == 'true':
        return True
    elif s == 'false':
        return False
    else:
        raise ValueError

def cacheArt(url):
	strippedAuth = url.split('&')
	imageID = re.search(r"id=(\d+)", strippedAuth[0])
        
        imageNamePng = imageID.group(1) + ".png"
        imageNameJpg = imageID.group(1) + ".jpg"
        pathPng = os.path.join( cacheDir , imageNamePng )
        pathJpg = os.path.join( cacheDir , imageNameJpg )
	if os.path.exists( pathPng ):
                xbmc.log("DEBUG: png cached",xbmc.LOGDEBUG)
		return pathPng
        elif os.path.exists( pathJpg ):
                xbmc.log("DEBUG: jpg cached",xbmc.LOGDEBUG)
		return pathJpg
	else:
                xbmc.log("DEBUG: File needs fetching ",xbmc.LOGDEBUG)
                ssl_certs_str = ampache.getSetting("disable_ssl_certs")
                if str_to_bool(ssl_certs_str):
                    context = ssl._create_unverified_context()
                    opener = urllib2.urlopen(url, context=context, timeout=100)
                else:
                    opener = urllib2.urlopen(url, timeout = 100)
		if opener.headers.maintype == 'image':
			extension = opener.headers['content-type']
			tmpExt = extension.split("/")
			if tmpExt[1] == "jpeg":
				fname = imageNameJpg
			else:
				fname = imageID.group(1) + '.' + tmpExt[1]
                        pathJpg = os.path.join( cacheDir , fname )
			open( pathJpg, 'wb').write(opener.read())
                        xbmc.log("DEBUG: Cached " + str(fname), xbmc.LOGDEBUG )
			return fname
		else:
                        xbmc.log("DEBUG: It didnt work", xbmc.LOGDEBUG )
                        raise NameError
			#return False

#handle albumArt and song info
def fillListItemWithSongInfo(li,node):
    try:
        albumArt = cacheArt(node.findtext("art"))
    except NameError:
        albumArt = "DefaultFolder.png"
    xbmc.log("DEBUG: albumArt - " + str(albumArt), xbmc.LOGDEBUG )
    li.setLabel(unicode(node.findtext("title")))
    li.setThumbnailImage(albumArt)
#needed by play_track to play the song, added here to uniform api
    li.setPath(node.findtext("url"))
#keep setInfo separate, old version with infoLabels list cause strange bug on
#kodi 15.2
    li.setInfo( type="music", infoLabels={ 'Title' :
        unicode(node.findtext("title")) })
    li.setInfo( type="music", infoLabels={ 'Artist' :
        unicode(node.findtext("artist")) } )
    li.setInfo( type="music", infoLabels={ 'Album' :
        unicode(node.findtext("album")) } )
    li.setInfo( type="music", infoLabels={ 'Size' :
        node.findtext("size") } )
    li.setInfo( type="music", infoLabels={ 'Duration' :
        node.findtext("time") } )
    li.setInfo( type="music", infoLabels={ 'Year' :
        node.findtext("year") } )
    li.setInfo( type="music", infoLabels={ 'Tracknumber' :
        node.findtext("track") } )
    li.setInfo( type="music", infoLabels={ 'Rating' :
        node.findtext("preciserating") } )
    
# Used to populate items for songs on XBMC. Calls plugin script with mode == 9 and object_id == (ampache song id)
# TODO: Merge with addDir(). Same basic idea going on, this one adds links all at once, that one does it one at a time
#       Also, some property things, some different context menu things.
def addSongLinks(elem):
    xbmcplugin.setContent(int(sys.argv[1]), "songs")
    ok=True
    it=[]
    for node in elem.iter("song"):
        liz=xbmcgui.ListItem()
        fillListItemWithSongInfo(liz, node)   
        liz.setProperty("IsPlayable", "true")
        song_elem = node.find("song")
        song_id = int(node.attrib["id"])
        track_parameters = { "mode": 9, "object_id": song_id}
        url = sys.argv[0] + '?' + urllib.urlencode(track_parameters)
        tu= (url,liz)
        it.append(tu)
    ok=xbmcplugin.addDirectoryItems(handle=int(sys.argv[1]),items=it,totalItems=len(elem))
    return ok

# The function that actually plays an Ampache URL by using setResolvedUrl. Gotta have the extra step in order to make
# song album art / play next automatically. We already have the track URL when we add the directory item so the api
# hit here is really unnecessary. Would be nice to get rid of it, the extra request adds to song gaps. It does
# guarantee that we are using a legit URL, though, if the session expired between the item being added and the actual
# playing of that item.
def play_track(id):
    ''' Start to stream the track with the given id. '''
    elem = ampache_http_request("song",filter=id)
    for thisnode in elem:
        node = thisnode
    liz = xbmcgui.ListItem()
    fillListItemWithSongInfo(liz,node)
    xbmcplugin.setResolvedUrl(handle=int(sys.argv[1]), succeeded=True,listitem=liz)

# Main function for adding xbmc plugin elements
def addDir(name,object_id,mode,iconImage=None,elem=None):
    if iconImage == None:
        iconImage = "DefaultFolder.png"

    liz=xbmcgui.ListItem(name, iconImage=iconImage, thumbnailImage=iconImage)

    liz.setInfo( type="Music", infoLabels={ "Title": name } )
    try:
        artist_elem = elem.find("artist")
        artist_id = int(artist_elem.attrib["id"]) 
        cm = []
        cm.append( ( "Show all albums from artist", "XBMC.Container.Update(%s?object_id=%s&mode=2)" % ( sys.argv[0],artist_id ) ) )
        liz.addContextMenuItems(cm)
    except:
        pass

    u=sys.argv[0]+"?object_id="+str(object_id)+"&mode="+str(mode)+"&name="+urllib.quote_plus(name)
    ok=xbmcplugin.addDirectoryItem(handle=int(sys.argv[1]),url=u,listitem=liz,isFolder=True)
    return ok

def get_params():
    param=[]
    paramstring=sys.argv[2]
    if len(paramstring)>=2:
            params=sys.argv[2]
            cleanedparams=params.replace('?','')
            if (params[len(params)-1]=='/'):
                    params=params[0:len(params)-2]
            pairsofparams=cleanedparams.split('&')
            param={}
            for i in range(len(pairsofparams)):
                    splitparams={}
                    splitparams=pairsofparams[i].split('=')
                    if (len(splitparams))==2:
                            param[splitparams[0]]=splitparams[1]
                            
    return param
    
def getFilterFromUser():
    loop = True
    while(loop):
        kb = xbmc.Keyboard('', '', True)
        kb.setHeading('Enter Search Filter')
        kb.setHiddenInput(False)
        kb.doModal()
        if (kb.isConfirmed()):
            filter = kb.getText()
            loop = False
        else:
            return(False)
    return(filter)

def get_user_pwd_login_url(nTime):
    myTimeStamp = str(nTime)
    sdf = ampache.getSetting("password")
    hasher = hashlib.new('sha256')
    hasher.update(ampache.getSetting("password"))
    myKey = hasher.hexdigest()
    hasher = hashlib.new('sha256')
    hasher.update(myTimeStamp + myKey)
    myPassphrase = hasher.hexdigest()
    myURL = ampache.getSetting("server") + '/server/xml.server.php?action=handshake&auth='
    myURL += myPassphrase + "&timestamp=" + myTimeStamp
    myURL += '&version=350001&user=' + ampache.getSetting("username")
    return myURL

def get_auth_key_login_url():
    myURL = ampache.getSetting("server") + '/server/xml.server.php?action=handshake&auth='
    myURL += ampache.getSetting("api_key")
    myURL += '&version=350001'
    return myURL

def AMPACHECONNECT():
    socket.setdefaulttimeout(3600)
    nTime = int(time.time())
    use_api_key = ampache.getSetting("use_api_key")
    if str_to_bool(use_api_key):
        myURL = get_auth_key_login_url() 
    else: 
        myURL = get_user_pwd_login_url(nTime)
    xbmc.log(myURL,xbmc.LOGNOTICE)
    req = urllib2.Request(myURL)
    ssl_certs_str = ampache.getSetting("disable_ssl_certs")
    if str_to_bool(ssl_certs_str):
        gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        response = urllib2.urlopen(req, context=gcontext)
        xbmc.log("DEBUG: ssl",xbmc.LOGDEBUG)
    else:
        response = urllib2.urlopen(req)
        xbmc.log("DEBUG: nossl",xbmc.LOGDEBUG)
    tree=ET.parse(response)
    response.close()
    elem = tree.getroot()
    token = elem.findtext('auth')
    ampache.setSetting('token',token)
    ampache.setSetting('token-exp',str(nTime+24000))
    return elem

def ampache_http_request(action,add=None, filter=None, limit=5000, offset=0):
    thisURL = build_ampache_url(action,filter=filter,add=add,limit=limit,offset=offset)
    xbmc.log("URL " + thisURL, xbmc.LOGNOTICE)
    req = urllib2.Request(thisURL)
    ssl_certs_str = ampache.getSetting("disable_ssl_certs")
    if str_to_bool(ssl_certs_str):
        gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
        response = urllib2.urlopen(req, context=gcontext)
    else:
        response = urllib2.urlopen(req)
    contents = response.read()
    contents = contents.replace("\0", "")
    #remove bug & it is not allowed as text in tags
    
    #code useful for debugging/parser needed
    xbmc.log("DEBUG: contents " + contents, xbmc.LOGDEBUG)
    #parser = ET.XMLParser(recover=True)
    #tree=ET.XML(contents, parser = parser)
    tree=ET.XML(contents)
    response.close()
    if tree.findtext("error"):
        errornode = tree.find("error")
        if errornode.attrib["code"]=="401":
            tree = AMPACHECONNECT()
            thisURL = build_ampache_url(action,filter=filter,add=add,limit=limit,offset=offset)
            req = urllib2.Request(thisURL)
            ssl_certs_str = ampache.getSetting("disable_ssl_certs")
            if str_to_bool(ssl_certs_str):
                gcontext = ssl.SSLContext(ssl.PROTOCOL_TLSv1)
                response = urllib2.urlopen(req, context=gcontext)
            else:
                response = urllib2.urlopen(req)
            contents = response.read()
            tree=ET.XML(contents)
            response.close()
    return tree

    
def get_items(object_type, object_id=None, add=None,
        filter=None,limit=5000,useCacheArt=True ):
    xbmcplugin.setContent(int(sys.argv[1]), object_type)
    xbmc.log("DEBUG: object_type " + object_type, xbmc.LOGDEBUG)
    action = object_type
    
    if object_type == 'albums':
        if object_id:
            action = 'artist_albums'
            addDir("All Songs",object_id,12)
    if object_id:
        filter = object_id

    elem = ampache_http_request(action,add=add,filter=filter, limit=limit)

    if object_type == 'artists':
        mode = 2
        image = "DefaultFolder.png"
    elif object_type == 'albums':
        mode = 3
    elif object_type == 'playlists':
        mode = 14
        image = "DefaultFolder.png"
    if object_type == 'albums':
        allid = set()
        for node in elem.iter('album'):
            #no unicode function, cause urllib quot_plus error ( bug )
            fullname = node.findtext("name").encode("utf-8")
            fullname += " - "
            fullname += node.findtext("year").encode("utf-8")
            album_id = int(node.attrib["id"])
            #remove duplicates in album names ( workaround for a problem in server comunication )
            if album_id not in allid:
                allid.add(album_id)
            else:
                continue
            if useCacheArt:
                image = node.findtext("art")
                xbmc.log("DEBUG: object_type - " + str(object_type) , xbmc.LOGDEBUG )
                xbmc.log("DEBUG: Art - " + str(image), xbmc.LOGDEBUG )
                try:
                    image = cacheArt(image)        
                except NameError:
                    image = "DefaultFolder.png"
                else:
                    xbmc.log("DEBUG: Art Filename: " + str(image), xbmc.LOGDEBUG )
            else:
                image = "DefaultFolder.png"
            addDir(fullname,node.attrib["id"],mode,image,node)
    if object_type == 'artists':
        for node in elem.iter('artist'):
            addDir(node.findtext("name").encode("utf-8"),node.attrib["id"],mode,image,node)
    if object_type == 'playlists':
        for node in elem.iter('playlist'):
            addDir(node.findtext("name").encode("utf-8"),node.attrib["id"],mode,image,node)
    if (object_type == 'playlist_songs' or object_type == 'songs' or
            object_type == 'album_songs' or object_type == 'artist_songs' or
            object_type == 'search_songs'):
        addSongLinks(elem)


def build_ampache_url(action,filter=None,add=None,limit=5000,offset=0):
    tokenexp = int(ampache.getSetting('token-exp'))
    if int(time.time()) > tokenexp:
        xbmc.log("refreshing token...", xbmc.LOGNOTICE )
        elem = AMPACHECONNECT()

    token=ampache.getSetting('token')    
    thisURL = ampache.getSetting("server") + '/server/xml.server.php?action=' + action 
    thisURL += '&auth=' + token
    thisURL += '&limit=' +str(limit)
    thisURL += '&offset=' +str(offset)
    if filter:
        thisURL += '&filter=' +urllib.quote_plus(str(filter))
    if add:
        thisURL += '&add=' + add
    return thisURL

def get_time(time_offset):
    d = datetime.date.today()
    dt = datetime.timedelta(days=time_offset)
    nd = d + dt
    return nd.isoformat()

def do_search(object_type):
    thisFilter = getFilterFromUser()
    if thisFilter:
        get_items(object_type=object_type,filter=thisFilter)

def get_recent(object_type,object_id):   
    if object_id == 99998:
        elem = AMPACHECONNECT()
        update = elem.findtext("add")        
        xbmc.log(update[:10],xbmc.LOGNOTICE)
        get_items(object_type=object_type,add=update[:10])
    elif object_id == 99997:
        get_items(object_type=object_type,add=get_time(-7))
    elif object_id == 99996:
        get_items(object_type=object_type,add=get_time(-30))
    elif object_id == 99995:
        get_items(object_type=object_type,add=get_time(-90))

#get rid of this function in the near future and use simply get_items with limit = None
def get_all(object_type):
    elem = AMPACHECONNECT()
    limit=int(elem.findtext(object_type))
    get_items(object_type=object_type, limit=limit, useCacheArt=False)

def get_random(object_type):
    xbmc.log("DEBUG: object_type " + object_type, xbmc.LOGDEBUG)
    #object type can be : albums, artists, songs, playlists
    
    if object_type == 'albums':
        settings = "random_albums"
    elif object_type == 'artists':
        settings = "random_artists"
    elif object_type == 'playlists':
        settings = "random_playlists"
    elif object_type == 'songs':
        settings = "random_songs"

    xbmcplugin.setContent(int(sys.argv[1]), object_type)
    elem = AMPACHECONNECT()
    items = int(elem.findtext(object_type))
    xbmc.log("DEBUG: items " + str(items), xbmc.LOGDEBUG )
    random_items = (int(ampache.getSetting(settings))*3)+3
    xbmc.log("DEBUG: random_items " + str(random_items), xbmc.LOGDEBUG )
    seq = random.sample(xrange(items),random_items)
    for item_id in seq:
        elem = ampache_http_request(object_type,offset=item_id,limit=1)
        if object_type == 'albums':
            for node in elem.iter("album"):
                #same urllib bug
                fullname = node.findtext("name").encode("utf-8")
                fullname += " - "
                fullname += node.findtext("artist").encode("utf-8")
                fullname += " - "
                fullname += node.findtext("year").encode("utf-8")
                try:
                    image = cacheArt(node.findtext("art"))
                except NameError:
                    image = "DefaultFolder.png"
                addDir(fullname,node.attrib["id"],3,image,node)        
        elif object_type == 'artists':
            image = "DefaultFolder.png"
            for node in elem.iter("artist"):
                fullname = node.findtext("name").encode("utf-8")
                addDir(fullname,node.attrib["id"],2,image,node)        
        elif object_type == 'playlists':
            image = "DefaultFolder.png"
            for node in elem.iter("playlist"):
                fullname = node.findtext("name").encode("utf-8")
                addDir(fullname,node.attrib["id"],14,image,node)        
        elif object_type == 'songs':
            addSongLinks(elem)


params=get_params()
name=None
mode=None
object_id=None

try:
        name=urllib.unquote_plus(params["name"])
        xbmc.log("DEBUG: name " + name, xbmc.LOGDEBUG)
except:
        pass
try:
        mode=int(params["mode"])
        xbmc.log("DEBUG: mode " + str(mode), xbmc.LOGDEBUG)
except:
        pass
try:
        object_id=int(params["object_id"])
        xbmc.log("DEBUG: object_id " + str(object_id), xbmc.LOGDEBUG)
except:
        pass


if mode==None:
    elem = AMPACHECONNECT()
    addDir("Search...",0,4,"DefaultFolder.png")
    addDir("Recent...",0,5,"DefaultFolder.png")
    addDir("Random...",0,7,"DefaultFolder.png")
    addDir("Artists (" + str(elem.findtext("artists")) + ")",None,1,"DefaultFolder.png")
    addDir("Albums (" + str(elem.findtext("albums")) + ")",None,2,"DefaultFolder.png")
    addDir("Playlists (" + str(elem.findtext("playlists")) + ")",None,13,"DefaultFolder.png")

#   artist list ( called from main screen  ( mode None ) , search
#   screen ( mode 4 ) and recent ( mode 5 )  )

elif mode==1:
    #artist, album, songs, playlist follow the same structure
    #search function
    if object_id == 99999:
        do_search("artists")
    #recent function
    elif object_id > 99994 and object_id < 99999:
        get_recent( "artists", object_id )
    #all artists list
    else:
        get_all("artists")
       
#   albums list ( called from main screen ( mode None ) , search
#   screen ( mode 4 ) and recent ( mode 5 )  )

elif mode==2:
    if object_id == 99999:
        do_search("albums")
    elif object_id > 99994 and object_id < 99999:
        get_recent( "albums", object_id )
    elif object_id:
        get_items(object_type="albums",object_id=object_id)
    else:
        get_all("albums")

#   song mode ( called from search screen ( mode 4 ) and recent ( mode 5 )  )
        
elif mode==3:
        if object_id == 99999:
            do_search("songs")
        elif object_id > 99994 and object_id < 99999:
            get_recent( "songs", object_id )
        else:
            get_items(object_type="album_songs",object_id=object_id)


# search screen ( called from main screen )

elif mode==4:
    addDir("Search Artists...",99999,1,"DefaultFolder.png")
    addDir("Search Albums...",99999,2,"DefaultFolder.png")
    addDir("Search Songs...",99999,3,"DefaultFolder.png")
    addDir("Search Playlists...",99999,13,"DefaultFolder.png")
    addDir("Search All...",99999,11,"DefaultFolder.png")

# recent additions screen ( called from main screen )

elif mode==5:
    addDir("Recent Artists...",99998,6,"DefaultFolder.png")
    addDir("Recent Albums...",99997,6,"DefaultFolder.png")
    addDir("Recent Songs...",99996,6,"DefaultFolder.png")
    addDir("Recent Playlists...",99995,6,"DefaultFolder.png")

#   screen with recent time possibilities ( subscreen of recent artists,
#   recent albums, recent songs ) ( called from mode 5 )

elif mode==6:
    #not clean, but i don't want to change too much the old code
    if object_id > 99995:
        addDir("Last Update",99998,99999-object_id,"DefaultFolder.png")
        addDir("1 Week",99997,99999-object_id,"DefaultFolder.png")
        addDir("1 Month",99996,99999-object_id,"DefaultFolder.png")
        addDir("3 Months",99995,99999-object_id,"DefaultFolder.png")
    #object_id for playlists is 99995 so 99999-object_id is 4 that is search function
    else:
        addDir("Last Update",99998,13,"DefaultFolder.png")
        addDir("1 Week",99997,13,"DefaultFolder.png")
        addDir("1 Month",99996,13,"DefaultFolder.png")
        addDir("3 Months",99995,13,"DefaultFolder.png")

# general random mode screen ( called from main screen )

elif mode==7:
    addDir("Random Artists...",99999,8,"DefaultFolder.png")
    addDir("Random Albums...",99998,8,"DefaultFolder.png")
    addDir("Random Songs...",99997,8,"DefaultFolder.png")
    addDir("Random Playlists...",99996,8,"DefaultFolder.png")


#   random mode screen ( display artists, albums or songs ) ( called from mode
#   7  )

elif mode==8:
    #   artists
    if object_id == 99999:
        addDir("Refresh..",99999,8,os.path.join(imagepath, 'refresh_icon.png'))
        get_random('artists')
    #   albums
    if object_id == 99998:
        addDir("Refresh..",99998,8,os.path.join(imagepath, 'refresh_icon.png'))
        get_random('albums')
    #   songs
    if object_id == 99997:
        addDir("Refresh..",99997,8,os.path.join(imagepath, 'refresh_icon.png'))
        get_random('songs')
    # playlists
    if object_id == 99996:
        addDir("Refresh..",99996,8,os.path.join(imagepath, 'refresh_icon.png'))
        get_random('playlists')

#   play track mode  ( mode set in add_links function )

elif mode==9:
    play_track(object_id)

# mode 11 : search all
elif mode==11:
    do_search("search_songs")

# mode 12 : artist_songs
elif mode==12:
    get_items(object_type="artist_songs",object_id=object_id )

#   playlist full list ( called from main screen )

elif mode==13:
        if object_id == 99999:
            do_search("playlists")
        elif object_id > 99994 and object_id < 99999:
            get_recent( "playlists", object_id )
        elif object_id:
            get_items(object_type="playlists",object_id=object_id)
        else:
            get_items(object_type="playlists")

#   playlist song mode

elif mode==14:
    get_items(object_type="playlist_songs",object_id=object_id)
#        "Ampache Playlists"
# search for playlist song or recent playlist song ( this one for sure ) will
# be implemented if i will find a valid reason ( now i have no one )
#    get_items(object_type="playlists")
#        if object_id == 99999:
#            thisFilter = getFilterFromUser()
#            if thisFilter:
#                get_items(object_type="playlist_songs",filter=thisFilter)
#        elif object_id == 99998:
#            elem = AMPACHECONNECT()
#            update = elem.findtext("add")        
#            xbmc.log(update[:10],xbmc.LOGNOTICE)
#            get_items(object_type="playlist_songs",add=update[:10])
#        elif object_id == 99997:
#            get_items(object_type="playlist_songs",add=get_time(-7))
#        elif object_id == 99996:
#            get_items(object_type="playlist_songs",add=get_time(-30))
#        elif object_id == 99995:
#            get_items(object_type="playlist_songs",add=get_time(-90))
#        else:
#           get_items(object_type="playlist_songs",object_id=object_id)

if mode < 19:
    xbmcplugin.endOfDirectory(int(sys.argv[1]))
