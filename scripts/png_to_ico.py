"""Simple helper to convert repository PNG icons to ICO files used on Windows."""

from PIL import Image

img = Image.open('images/moshi-connect.png')
img.save('images/moshi-connect.ico')

img = Image.open('images/moshi-connect_connected.png')
img.save('images/moshi-connect_connected.ico')
