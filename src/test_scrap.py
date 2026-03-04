import urllib.request
import re
import json
req = urllib.request.Request('https://brawlify.com/player/GY9G0V98J', headers={'User-Agent': 'Mozilla/5.0'})
try:
    html = urllib.request.urlopen(req, timeout=5).read().decode('utf-8')
    match = re.search(r'"brawlers":(\[.+?\]),"club"', html)
    if match:
        brawlers = json.loads(match.group(1))
        print('Found brawlers:', len(brawlers))
        for b in brawlers[:3]: print(b['name'], b['trophies'])
    else:
        print('No brawlers JSON found in HTML')
except Exception as e:
    print(e)
