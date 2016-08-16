# install Meteor-Files from https://github.com/VeliovGroup/Meteor-Files
# and python-meteor from https://github.com/hharnisc/python-meteor
from MeteorClient import MeteorClient
import uuid
import math
import base64
import os
import time
import requests

class FileUploader():
  def __init__(self, client, collectionName, transport='ddp'):
    self.client = client
    self.collectionName = collectionName
    if not transport in ['ddp', 'http']:
        raise Exception('invalid transport.')
    self.transport = transport
    self.methodNames = {
      "_Abort": "_FilesCollectionAbort_" + collectionName,
      "_Write": "_FilesCollectionWrite_" + collectionName,
      "_Start": "_FilesCollectionStart_" + collectionName,
    }
  def _remove_callback(self, error, result):
    if error:
      print(error)
      return
    #print(result)

  def remove(self, selector, callback = None):
    self.client.call("_FilesCollectionRemove_" + self.collectionName, selector, self._remove_callback)

  def _upload_write_callback(self, error, result):
    if error:
      self.error = True
      print(error)
      return
    #print(result)

  def _upload_end_callback(self, error, result):
    if error:
      self.error = True
      print(error)
      return
    self.finished = True

  def _upload_start_callback(self, error, metaResult):
    if error:
      self.error = True
      print(error)
      return
    try:
      with open(self.filePath, "rb") as _file:
        for i in xrange(self.chunkCount):
          if self.error:
            raise
          print('sending: '+str(i)+'/'+str(self.chunkCount))
          encoded_string = base64.b64encode(_file.read(self.chunkSize))
          opts = {
            "eof": False,
            "fileId": self.fileId,
            "binData": encoded_string,
            "chunkId": i+1,
          }
          if self.transport == 'ddp':
              self.client.call(self.methodNames['_Write'], [opts], self._upload_write_callback)
          else:
              baseurl = self.client.ddp_client.url
              assert baseurl.startswith('ws://') and baseurl.endswith('/websocket')
              uploadRoute = 'http' + baseurl[2:-10] + metaResult['uploadRoute']
              requests.post(uploadRoute, data=opts)
    except Exception as e:
      print(e)
      self.error = True
      self.client.call(self.methodNames['_Abort'], [self.fileId])
    else:
      opts = {
      "eof": True,
      "fileId": self.fileId,
      }
      self.client.call(self.methodNames['_Write'], [opts], self._upload_end_callback)

  def upload(self, filePath, chunkSize = 'dynamic', fileType= None, fileId=None):
    self.filePath = filePath
    self.fileId = fileId or str(uuid.uuid4())
    fpath,fname = os.path.split(filePath)
    if fileType is None:
      try:
        import magic
        fileType = magic.from_file(filePath, mime=True)
      except Exception as e:
        import urllib, mimetypes
        url = urllib.pathname2url(filePath)
        fileType = mimetypes.guess_type(url)[0]
      if fileType is None:
        _, ext = os.path.splitext(fname)
        if ext != '':
          fileType = 'application/' + ext
    assert fileType, 'unknown file type'

    statinfo = os.stat(filePath)
    fileSize = statinfo.st_size
    fileBase64Size = ((4 * fileSize / 3) + 3) & ~3
    if chunkSize == 'dynamic':
      chunkSize = fileBase64Size / 1000
    if chunkSize < 327680:
      chunkSize = 327680
    elif chunkSize > 1048576:
      chunkSize = 1048576
    chunkSize = int(math.floor(1.0*chunkSize / 8) * 8);
    chunkCount = int(math.ceil(1.0*fileBase64Size / chunkSize));

    if self.transport == 'http':
        chunkSize = int(round(chunkSize / 2))

    self.fileType = fileType
    self.chunkCount = chunkCount
    self.chunkSize = chunkSize
    self.fileBase64Size = fileBase64Size
    self.fileSize = fileSize

    print('chunk size: {}, chunk count: {}'.format(chunkSize, chunkCount))
    error = False

    opts ={
      "file": {"name":fname, "type":fileType, "size":10, "meta":{}},
      "fileId": self.fileId,
      "chunkSize": chunkSize,
      "fileLength": 1 if chunkCount<=0 else chunkCount,
    }
    self.finished = False
    self.error = False
    returnMeta = self.transport == 'http'
    self.client.call(self.methodNames['_Start'], [opts, returnMeta], self._upload_start_callback)

client = MeteorClient('ws://127.0.0.1:3000/websocket')
client.connect()
# work with https://github.com/VeliovGroup/Meteor-Files/tree/master/demo-simplest-upload
client.subscribe('files.images.all');
up = FileUploader(client, 'Images', transport='http')
up.upload("test.jpeg")
while True:
  time.sleep(1)
