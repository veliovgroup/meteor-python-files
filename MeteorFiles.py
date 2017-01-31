from MeteorClient import MeteorClient
import uuid
import math
import base64
import os
import time
import requests


class Uploader():

    def __init__(self, client, collectionName, transport='ddp', callbacks={}, verbose=False):
        assert isinstance(client, MeteorClient)
        self.client = client
        self.collectionName = collectionName
        self.callbacks = callbacks
        self.verbose = verbose
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
        # print(result)

    def remove(self, selector, callback=None):
        self.client.call("_FilesCollectionRemove_" +
                         self.collectionName, selector, self._remove_callback)

    def _upload_write_callback(self, error, result):
        if error:
            self.error = True
            print(error)
            return
        # print(result)

    def _upload_end_callback(self, error, result):
        try:
            if self.callbacks.has_key('ended'):
                self.callbacks['ended'](error, result)
        except Exception as e:
            if self.verbose:
                print('error occured in ended callback')
        if error:
            self.error = True
            print(error)
            return
        self.finished = True
        if self.verbose:
            print('upload finished.')

    def _upload_start_callback(self, error, metaResult):
        try:
            if self.callbacks.has_key('started'):
                self.callbacks['started'](error, metaResult)
        except Exception as e:
            if self.verbose:
                print('error occured in started callback')

        if error:
            self.error = True
            print(error)
            return
        try:
            with open(self.filePath, "rb") as _file:
                for i in xrange(self.chunkCount):
                    try:
                        if self.callbacks.has_key('progress'):
                            self.callbacks['progress'](i, self.fileId)
                    except Exception as e:
                        if self.verbose:
                            print('error occured in progress callback')
                    if self.error:
                        raise
                    if self.verbose:
                        print('sending: ' + str(i + 1) +
                              '/' + str(self.chunkCount))
                    encoded_string = base64.b64encode(
                        _file.read(self.chunkSize))
                    if self.transport == 'ddp':
                        opts = {
                            "eof": False,
                            "fileId": self.fileId,
                            "binData": encoded_string,
                            "chunkId": i + 1,
                        }
                        self.client.call(self.methodNames['_Write'], [
                                         opts], self._upload_write_callback)
                    else:
                        baseurl = self.client.ddp_client.url
                        assert (baseurl.startswith('ws://') or baseurl.startswith('wss://')) and baseurl.endswith('/websocket')

                        uploadRoute = 'http' + \
                            baseurl[2:-10] + metaResult['uploadRoute']
                        headers = {
                            "x-eof": 0,
                            "x-fileid": self.fileId,
                            "x-chunkId": i + 1,
                            'content-type': 'text/plain'
                        }
                        r = requests.post(
                            uploadRoute, headers=headers, data=encoded_string)
                        r.raise_for_status()
        except:
            import traceback
            traceback.print_exc()
            self.error = True
            self.client.call(self.methodNames['_Abort'], [self.fileId])
        else:
            if self.verbose:
                print('sending EOF.')
            if self.transport == 'ddp':
                opts = {
                    "eof": True,
                    "fileId": self.fileId,
                }
                self.client.call(self.methodNames['_Write'], [
                                 opts], self._upload_end_callback)
            else:
                headers = {
                    "x-eof": 1,
                    "x-fileid": self.fileId,
                    'content-type': 'text/plain'
                }
                r = requests.post(uploadRoute, headers=headers, data='')
                r.raise_for_status()
                self.finished = True
                try:
                    if self.callbacks.has_key('ended'):
                        self.callbacks['ended'](r.status_code != requests.codes.ok, r)
                except Exception as e:
                    if self.verbose:
                        print('error occured in ended callback')
                if self.verbose:
                    print('upload finished.')

    def upload(self, filePath, chunkSize='dynamic', meta={}, fileType=None, fileId=None):
        self.filePath = filePath
        self.fileId = fileId or str(uuid.uuid4())
        fpath, fname = os.path.split(filePath)
        if fileType is None:
            try:
                import magic
                fileType = magic.from_file(filePath, mime=True)
            except Exception as e:
                import urllib
                import mimetypes
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
        chunkSize = int(math.floor(1.0 * chunkSize / 8) * 8)
        if self.transport == 'http':
            chunkSize = int(round(1.0 * chunkSize / 2))
        chunkCount = int(math.ceil(1.0 * fileBase64Size / chunkSize))

        self.fileType = fileType
        self.chunkCount = chunkCount
        self.chunkSize = chunkSize
        self.fileBase64Size = fileBase64Size
        self.fileSize = fileSize
        if self.verbose:
            print('file size: {}, chunk size: {}, chunk count: {}'.format(
                fileSize, chunkSize, chunkCount))
        error = False
        if self.verbose:
            print('start upload')
        opts = {
            "file": {"name": fname, "type": fileType, "size": fileSize, "meta": meta},
            "fileId": self.fileId,
            "chunkSize": chunkSize,
            "fileLength": 1 if chunkCount <= 0 else chunkCount,
        }
        self.finished = False
        self.error = False
        returnMeta = self.transport == 'http'
        self.client.call(self.methodNames['_Start'], [
                         opts, returnMeta], self._upload_start_callback)
        return self.fileId

if __name__ == '__main__':
    client = MeteorClient('ws://127.0.0.1:3000/websocket')
    client.connect()

    # upload example, work with Meteor-Files example: demo-simplest-upload
    # server code: https://github.com/VeliovGroup/Meteor-Files/tree/master/demo-simplest-upload
    client.subscribe('files');
    uploader = Uploader(client, 'files', transport='ddp', verbose=True)

    #import time
    #t0 = time.time()

    uploader.upload("test.jpeg")
    while not uploader.finished:
        time.sleep(0.1)

    #t1 = time.time()
    #print( 'time elapsed:%.1fs'%(t1-t0))
