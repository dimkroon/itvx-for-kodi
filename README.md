
ITVX for Kodi
=============

Project for the development of plugin.video.viwx - an add-on for 
[Kodi media center](https://kodi.tv) enabling access to live and video 
on-demand from ITVX; the web streaming service of British broadcaster ITV. 

This is an unofficial add-on. It is not created or endorsed by ITV, nor is 
the developer in any way associated with ITV. The add-on just provides 
access to ITV's web services from Kodi, so the same limitations encountered
with a generic web browser also apply to this add-on:
  * You can only watch ITVX in the UK.
  * You need an ITVX account to watch live or VOD content. 


## Features

* Watch the main ITV live channels.
* Watch the stream-only FAST channels.
* Watch all video on-demand offered by ITVX. Premium content is of course only 
  available to users with a paid ITVX premium account.
* Search
* Play from the start for programmes on the main live channels.  
  Available from the context menu on channels in the 'Live' menu, and on 
  hero items (those shown in orange) in the main menu when that item 
  represents a live broadcast.
* Support for IPTV Manager and IPTV Merge to integrate the ITV main live 
  channels into Kodi's TV section, if you use IPTV Simple as your PVR add-on. 
  Check [the wiki page of IPTV Manager](https://github.com/add-ons/service.iptv.manager/wiki)
  for more info. IPTV Manager integration is enabled by default, but can be 
  switched off in viwX's settings.
* My ItvX with:
  * Support for ITVX's My List.  
    Add to or remove programmes from My List by using the context menu on 
    programmes in any type of listing.  
  * Continue Watching with synced status across different devices.  
    Resume watching on one device what you started on another, regardless of 
    whether it's viwX, the ITVX app or the ITVX website.
  * Because You Watched.  
    ITVX's recommendations based on a recently watched programme.
  * Recommended for You.  
    General recommendations from ITVX.
* Option to hide premium content from listings.
* Option to show subtitles on VOD content, with the option to enable/disable 
  colourisation of subtitles. Enable VOD subtitles in viwX's settings.
* Option to play VOD programmes with British Sign Language when available 
  and enabled in viwX's settings.
* Support for embedded subtitles on live streams. Use Kodi's standard 
  subtitle dialog to enable/disable live subtitles.
* Support for the experimental add-on 
  [TranslateSubs](https://github.com/dimkroon/translate_subs), which can 
  automatically translate subtitles for the hearing impaired to your 
  preferred subtitle language, and can also filter out sound descriptions 
  from these subtitles, making them usable to people in the full range of 
  hearing ability.


## Installation

Only Kodi 19 (Matrix) and higher are supported.


#### Preferred Method

ViwX is available in the official Kodi add-on repository. Installing from the 
Kodi repo is the easiest and most secure way of installing this add-on, and is 
the only method that supports automatic updates. 

To install from the official Kodi repo, select `Settings -> Add-ons -> Install 
from repository -> Kodi Add-on repository -> Video add-ons`. Scroll down to 
viwX, select and install.

After installation, open the add-on's settings to sign in to your ITVX 
account.


#### Alternative Method

For those who prefer to install add-ons manually, or want immediate access to 
new versions, this method of installing from zip remains available:

* Ensure that installing from unknown sources is enabled in Kodi. Click 
  [here for instructions](https://dimkroon.net/en/guides/enable-unknown-sources.html).
* Download the latest release. 
  You can add https://dimkroon.net/kodi-addons as file source to Kodi's file 
  manager ([instructions](https://dimkroon.net/en/guides/howto-add-file-source.html)), 
  so you can easily download the zip file from Kodi.
  Alternatively, download the latest zip file manually from the
  [GitHub releases](https://github.com/dimkroon/itvx-for-kodi/releases) 
  page to a place that is accessible by your Kodi device.
* Choose _install from zip_ from Kodi's add-on menu, browse to the file 
  source you've just created and install the latest version, or install the 
  manually downloaded zip file.
  Check [how to install from zip file](https://dimkroon.net/en/guides/install-from-zip.html) 
  for detailed instructions.


## Support

Head for support, questions and general discussions regarding this add-on to 
[this thread](https://forum.kodi.tv/showthread.php?tid=374239) on the Kodi 
forum. 
If you are confident you've found a bug, please open an issue on GitHub.

--------------------------------------------------------------------------------

### Disclaimer ###

This add-on is distributed in the hope that it will be useful, but WITHOUT ANY 
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR 
A PARTICULAR PURPOSE.
