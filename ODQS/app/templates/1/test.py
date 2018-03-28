import base64

filedata = open('5.png','rb')
fff = base64.b64encode(filedata.read())
print(type(fff))
filedata.close()
fff = fff.decode()
print(type(fff))
img = base64.b64decode(fff)
print(type(img))
file = open("8.png", "wb")
file.write(img)
file.close()

