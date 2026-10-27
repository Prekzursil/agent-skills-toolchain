import urllib.request as u
name = 'urlopen'
fn = getattr(u, name)
print('dispatch', fn)
